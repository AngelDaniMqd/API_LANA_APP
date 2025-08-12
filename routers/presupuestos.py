from fastapi import APIRouter, Depends, HTTPException, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, Float, cast
from typing import List, Optional
from datetime import datetime, date
import os

from models.database import get_db, Presupuesto, Categoria, Usuario, Registro, Subcategoria
from auth.auth import get_current_user

# --- NUEVO: Resend SDK ---
import resend

router = APIRouter(prefix="/presupuestos", tags=["Presupuestos"])

# ===============================
# Config & thresholds
# ===============================

# Enviar 1 correo al llegar a 90% y otro al llegar/exceder 100%
NEAR_THRESHOLD_PCT = 90.0
EXCEEDED_THRESHOLD_PCT = 100.0

# Evitar spam: cache en memoria por proceso (marca si ya notificamos HOY por nivel)
# NOTA: si corres varios workers, conviene persistir esto en BD.
_NOTIFY_CACHE: dict[int, dict[str, str]] = {}  # {presupuesto_id: {'near':'YYYY-MM-DD','exceeded':'YYYY-MM-DD'}}

# ===============================
# Email helpers (Resend)
# ===============================

def _resend_from() -> str:
    # Usa RESEND_FROM si existe; si no, cae a FROM_EMAIL; si no, usa onboarding@resend.dev
    return os.getenv("RESEND_FROM") or os.getenv("FROM_EMAIL") or "onboarding@resend.dev"

def send_email(to: str, subject: str, body: str) -> None:
    """
    Envío de email usando Resend (SDK oficial).
    - Requiere: RESEND_API_KEY
    - Remitente: RESEND_FROM (o FROM_EMAIL) o 'onboarding@resend.dev' como fallback
    """
    if not to:
        print("[EMAIL] Sin destinatario, se omite envío")
        return

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        # No rompemos el endpoint si falta config: modo DRYRUN
        print(f"[EMAIL:DRYRUN] Falta RESEND_API_KEY. to={to}\nsubject={subject}\nbody=\n{body}\n")
        return

    try:
        resend.api_key = api_key
        resend.Emails.send({
            "from": _resend_from(),
            "to": [to],
            "subject": subject,
            "text": body,  # texto plano (puedes cambiar a 'html' si quieres)
        })
        print(f"[EMAIL] Enviado via Resend a {to}")
    except Exception as e:
        # Log y seguimos (no lanzamos excepción para no romper la respuesta del endpoint)
        print(f"[EMAIL] Resend falló: {e}. to={to} subject={subject}")

def _get_user_email(user: Usuario) -> Optional[str]:
    # Intenta varias convenciones de campo en tu modelo Usuario
    for attr in ("correo", "email", "mail", "correo_electronico"):
        val = getattr(user, attr, None)
        if val:
            return str(val)
    return None

# ===============================
# Cálculo de métricas
# ===============================

def _sum_gastos_desde(db: Session, usuarios_id: int, categorias_id: int, desde: datetime) -> float:
    """
    Suma de GASTOS (registros negativos) para una categoría (por subcategorías),
    desde 'desde' hasta ahora. Registro.monto es varchar; se castea a Float.
    """
    total = (
        db.query(func.sum(func.abs(cast(Registro.monto, Float))))
        .join(Subcategoria, Registro.subCategorias_id == Subcategoria.id)
        .filter(
            Registro.usuarios_id == usuarios_id,
            Subcategoria.categorias_id == categorias_id,
            cast(Registro.monto, Float) < 0,
            Registro.fecha_registro >= (desde or datetime.min),
        )
        .scalar()
        or 0.0
    )
    return float(total)

def _hydrate_presupuesto(db: Session, p: Presupuesto) -> dict:
    gastado = _sum_gastos_desde(db, p.usuarios_id, p.categorias_id, p.fecha_creacion)
    limite = float(p.monto_limite or 0)
    restante = limite - gastado
    pct = round((gastado / limite * 100), 2) if limite > 0 else 0.0
    excedido = gastado >= limite and limite > 0

    categoria_nombre = (
        db.query(Categoria.descripcion)
        .filter(Categoria.id == p.categorias_id)
        .scalar()
    )

    return {
        "id": p.id,
        "usuarios_id": p.usuarios_id,
        "categorias_id": p.categorias_id,
        "monto_limite": limite,
        "estado": p.estado,
        "fecha_creacion": p.fecha_creacion,
        "categoria_nombre": categoria_nombre,
        "gastado": gastado,
        "restante": restante,
        "porcentaje_usado": pct,
        "excedido": excedido,
    }

# ===============================
# Notificaciones
# ===============================

def _should_notify_once_per_day(presupuesto_id: int, level: str) -> bool:
    """
    level: 'near' | 'exceeded'
    Marca y devuelve True si aún no se notificó HOY por ese nivel.
    """
    today = date.today().isoformat()
    levels = _NOTIFY_CACHE.get(presupuesto_id) or {}
    last = levels.get(level)
    if last == today:
        return False
    # marcar
    levels[level] = today
    _NOTIFY_CACHE[presupuesto_id] = levels
    return True

def _maybe_notify(background_tasks: BackgroundTasks, user_email: Optional[str], payload: dict) -> None:
    """
    Dispara notificación si el presupuesto ACTIVO está cerca (>= 90%) o excedido (>=100%).
    Se envía uno por día por nivel para evitar spam en cada GET.
    """
    if not user_email:
        return
    if payload.get("estado") != "activo":
        return

    pct = float(payload.get("porcentaje_usado") or 0.0)
    limite = float(payload.get("monto_limite") or 0.0)
    gastado = float(payload.get("gastado") or 0.0)
    categoria_nombre = payload.get("categoria_nombre") or f"Categoría {payload.get('categorias_id')}"
    presupuesto_id = int(payload.get("id"))

    # EXCEDIDO (>=100%)
    if pct >= EXCEEDED_THRESHOLD_PCT and _should_notify_once_per_day(presupuesto_id, "exceeded"):
        subject = f"Presupuesto EXCEDIDO: {categoria_nombre}"
        body = (
            f"Has excedido tu presupuesto activo para '{categoria_nombre}'.\n\n"
            f"Límite: MXN {limite:,.2f}\n"
            f"Gastado: MXN {gastado:,.2f}\n"
            f"Uso: {pct:.1f}%\n\n"
            f"Revisa tus gastos y ajusta tu consumo."
        )
        background_tasks.add_task(send_email, user_email, subject, body)
        return  # prioridad al mensaje de excedido

    # CERCA (>=90%)
    if pct >= NEAR_THRESHOLD_PCT and _should_notify_once_per_day(presupuesto_id, "near"):
        subject = f"Tu presupuesto está por alcanzarse: {categoria_nombre}"
        body = (
            f"Tu presupuesto activo para '{categoria_nombre}' está por alcanzarse.\n\n"
            f"Límite: MXN {limite:,.2f}\n"
            f"Gastado: MXN {gastado:,.2f}\n"
            f"Uso: {pct:.1f}%\n\n"
            f"Considera moderar tus gastos para evitar exceder el límite."
        )
        background_tasks.add_task(send_email, user_email, subject, body)

def _hydrate_and_notify(db: Session, user: Usuario, p: Presupuesto, background_tasks: BackgroundTasks) -> dict:
    payload = _hydrate_presupuesto(db, p)
    _maybe_notify(background_tasks, _get_user_email(user), payload)
    return payload

# ===============================
# Endpoints (sin cambiar lógica)
# ===============================

@router.get("/")
def listar_presupuestos(
    background_tasks: BackgroundTasks,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lista todos los presupuestos del usuario (activos e inactivos),
    con métricas calculadas y notificación si corresponde (>=90% o >=100%).
    """
    rows: List[Presupuesto] = (
        db.query(Presupuesto)
        .filter(Presupuesto.usuarios_id == current_user.id)
        .order_by(Presupuesto.fecha_creacion.desc())
        .all()
    )
    return [_hydrate_and_notify(db, current_user, p, background_tasks) for p in rows]

@router.get("/activos")
def listar_presupuestos_activos(
    background_tasks: BackgroundTasks,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lista solo presupuestos activos. También notifica si se cruza un umbral (>=90% o >=100%).
    """
    rows: List[Presupuesto] = (
        db.query(Presupuesto)
        .filter(Presupuesto.usuarios_id == current_user.id, Presupuesto.estado == "activo")
        .order_by(Presupuesto.fecha_creacion.desc())
        .all()
    )
    return [_hydrate_and_notify(db, current_user, p, background_tasks) for p in rows]

@router.post("/")
def crear_presupuesto(
    background_tasks: BackgroundTasks,
    categorias_id: int = Form(..., description="ID de la categoría"),
    monto_limite: float = Form(..., description="Monto límite del presupuesto"),
    estado: str = Form("activo", description="Estado inicial ('activo'|'inactivo')"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if estado not in ("activo", "inactivo"):
        raise HTTPException(status_code=422, detail="Estado inválido")

    categoria = db.query(Categoria).filter(Categoria.id == categorias_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    # Un presupuesto ACTIVO por categoría y usuario
    if estado == "activo":
        dup = (
            db.query(Presupuesto)
            .filter(
                Presupuesto.usuarios_id == current_user.id,
                Presupuesto.categorias_id == categorias_id,
                Presupuesto.estado == "activo",
            )
            .first()
        )
        if dup:
            raise HTTPException(status_code=400, detail="Ya existe un presupuesto activo para esta categoría")

    p = Presupuesto(
        usuarios_id=current_user.id,
        categorias_id=categorias_id,
        monto_limite=float(monto_limite),
        estado=estado,
        fecha_creacion=datetime.utcnow(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    return _hydrate_and_notify(db, current_user, p, background_tasks)

@router.put("/{presupuesto_id}")
def actualizar_presupuesto(
    background_tasks: BackgroundTasks,
    presupuesto_id: int,
    categorias_id: Optional[int] = Form(None, description="Nueva categoría ID"),
    monto_limite: Optional[float] = Form(None, description="Nuevo monto límite"),
    estado: Optional[str] = Form(None, description="Nuevo estado ('activo'|'inactivo')"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p: Optional[Presupuesto] = (
        db.query(Presupuesto)
        .filter(Presupuesto.id == presupuesto_id, Presupuesto.usuarios_id == current_user.id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if categorias_id is not None:
        cat = db.query(Categoria).filter(Categoria.id == categorias_id).first()
        if not cat:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")

    new_estado = estado if estado is not None else p.estado
    new_categoria = categorias_id if categorias_id is not None else p.categorias_id

    if new_estado not in ("activo", "inactivo"):
        raise HTTPException(status_code=422, detail="Estado inválido")

    # Si va a quedar ACTIVO, validar unicidad por categoría
    if new_estado == "activo":
        dup = (
            db.query(Presupuesto)
            .filter(
                Presupuesto.usuarios_id == current_user.id,
                Presupuesto.categorias_id == new_categoria,
                Presupuesto.estado == "activo",
                Presupuesto.id != p.id,
            )
            .first()
        )
        if dup:
            raise HTTPException(status_code=400, detail="Ya existe un presupuesto activo para esta categoría")

    # Actualizar campos
    if categorias_id is not None:
        p.categorias_id = categorias_id
    if monto_limite is not None:
        p.monto_limite = float(monto_limite)
    if estado is not None:
        p.estado = estado

    db.commit()
    db.refresh(p)

    return _hydrate_and_notify(db, current_user, p, background_tasks)

@router.patch("/{presupuesto_id}/estado")
def cambiar_estado_presupuesto(
    background_tasks: BackgroundTasks,
    presupuesto_id: int,
    estado: str = Form(..., description="Nuevo estado ('activo'|'inactivo')"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if estado not in ("activo", "inactivo"):
        raise HTTPException(status_code=422, detail="Estado inválido")

    p: Optional[Presupuesto] = (
        db.query(Presupuesto)
        .filter(Presupuesto.id == presupuesto_id, Presupuesto.usuarios_id == current_user.id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if estado == "activo":
        # Unicidad de activo por categoría
        dup = (
            db.query(Presupuesto)
            .filter(
                Presupuesto.usuarios_id == current_user.id,
                Presupuesto.categorias_id == p.categorias_id,
                Presupuesto.estado == "activo",
                Presupuesto.id != p.id,
            )
            .first()
        )
        if dup:
            raise HTTPException(status_code=400, detail="Ya existe un presupuesto activo para esta categoría")

    p.estado = estado
    db.commit()
    db.refresh(p)

    return _hydrate_and_notify(db, current_user, p, background_tasks)

@router.delete("/{presupuesto_id}")
def eliminar_presupuesto(
    presupuesto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p: Optional[Presupuesto] = (
        db.query(Presupuesto)
        .filter(Presupuesto.id == presupuesto_id, Presupuesto.usuarios_id == current_user.id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    db.delete(p)
    db.commit()
    return {"mensaje": "Presupuesto eliminado exitosamente"}

# Endpoint para enviar un correo de prueba al usuario del token
@router.post("/_test_email")
def test_email(
    background_tasks: BackgroundTasks,
    current_user: Usuario = Depends(get_current_user),
):
    to = _get_user_email(current_user)
    if not to:
        raise HTTPException(status_code=400, detail="El usuario no tiene correo configurado")
    subject = "Prueba de correo - Presupuestos (Lana App)"
    body = "Hola, este es un correo de prueba enviado por la API de Presupuestos de Lana App."
    background_tasks.add_task(send_email, to, subject, body)
    return {"ok": True, "to": to}
