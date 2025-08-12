# routers/registros.py
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal, InvalidOperation

from models.database import get_db, Registro, ListaCuenta, Subcategoria, CategoriaMetodo, Usuario
from models.schemas import RegistroResponse
from auth.auth import get_current_user

router = APIRouter(prefix="/registros", tags=["Registros"])

def parse_optional_int(raw: Optional[str], field_name: str) -> Optional[int]:
    """
    Convierte '', None -> None; ints válidos -> int; si no, 422.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    try:
        return int(s)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field_name} debe ser entero o vacío")

def parse_decimal(value: str, field_name: str) -> Decimal:
    """
    Convierte string a Decimal con validación amable.
    """
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=422, detail=f"{field_name} debe ser numérico")

@router.get("/", response_model=List[RegistroResponse])
def listar_registros(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return (
        db.query(Registro)
        .filter(Registro.usuarios_id == current_user.id)
        .order_by(Registro.fecha_registro.desc())
        .all()
    )

@router.post("/", response_model=RegistroResponse)
def crear_registro(
    lista_cuentas_id: int = Form(..., description="ID de la cuenta"),
    subCategorias_id: int = Form(..., description="ID de la subcategoría"),
    monto: str = Form(..., description="Monto del registro"),
    # 🔸 ahora OPCIONAL; acepta "" (-> NULL)
    categori_metodos_id: Optional[str] = Form(
        None, description="ID de la categoría método (opcional)"
    ),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validaciones de entidades
    cuenta = db.query(ListaCuenta).filter(
        ListaCuenta.id == lista_cuentas_id,
        ListaCuenta.usuarios_id == current_user.id
    ).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    
    subcategoria = db.query(Subcategoria).filter(Subcategoria.id == subCategorias_id).first()
    if not subcategoria:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")

    cm_id = parse_optional_int(categori_metodos_id, "categori_metodos_id")
    if cm_id is not None:
        cm = db.query(CategoriaMetodo).filter(CategoriaMetodo.id == cm_id).first()
        if not cm:
            raise HTTPException(status_code=404, detail="Categoría método no encontrada")

    # Validar monto
    _ = parse_decimal(monto, "monto")

    # Crear registro (si tienes trigger AFTER INSERT, él ajusta la cuenta)
    db_registro = Registro(
        usuarios_id=current_user.id,
        lista_cuentas_id=lista_cuentas_id,
        subCategorias_id=subCategorias_id,
        monto=monto,
        fecha_registro=datetime.utcnow(),
        categori_metodos_id=cm_id  # puede ser None
    )
    db.add(db_registro)
    db.commit()
    db.refresh(db_registro)
    return db_registro

@router.put("/{registro_id}", response_model=RegistroResponse)
def actualizar_registro(
    registro_id: int,
    lista_cuentas_id: Optional[int] = Form(None, description="Nueva cuenta"),
    subCategorias_id: Optional[int] = Form(None, description="Nueva subcategoría"),
    monto: Optional[str] = Form(None, description="Nuevo monto"),
    # 🔸 acepta vacío para poner NULL; si no se envía, no cambia
    categori_metodos_id: Optional[str] = Form(
        None, description="Nueva categoría método (opcional)"
    ),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    registro = db.query(Registro).filter(
        Registro.id == registro_id,
        Registro.usuarios_id == current_user.id
    ).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    # Estado previo
    old_cuenta = registro.lista_cuenta  # relación en tu modelo
    if not old_cuenta:
        raise HTTPException(status_code=500, detail="Relación lista_cuenta no disponible en el modelo Registro")
    try:
        old_monto = Decimal(registro.monto)
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=500, detail="Monto almacenado inválido en el registro")

    # Determinar nueva cuenta (si se solicitó cambio)
    new_cuenta = None
    if lista_cuentas_id is not None and lista_cuentas_id != old_cuenta.id:
        new_cuenta = db.query(ListaCuenta).filter(
            ListaCuenta.id == lista_cuentas_id,
            ListaCuenta.usuarios_id == current_user.id
        ).first()
        if not new_cuenta:
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    # Determinar nuevo monto (si viene), si no, usar el viejo
    if monto is not None:
        new_monto = parse_decimal(monto, "monto")
    else:
        new_monto = old_monto

    # Reglas de ajuste de saldos en cuentas:
    # 1) Si cambia la cuenta:
    #    - Restar old_monto de la cuenta vieja
    #    - Sumar new_monto a la cuenta nueva
    # 2) Si NO cambia la cuenta y cambia el monto:
    #    - Sumar diff a la cuenta actual
    if new_cuenta is not None:
        # Mover saldo de una cuenta a otra
        old_cuenta.cantidad = str(Decimal(old_cuenta.cantidad) - old_monto)
        new_cuenta.cantidad = str(Decimal(new_cuenta.cantidad) + new_monto)
        registro.lista_cuentas_id = new_cuenta.id
    else:
        # Misma cuenta; si llegó un nuevo monto, ajustar la diferencia
        if monto is not None:
            diff = new_monto - old_monto
            old_cuenta.cantidad = str(Decimal(old_cuenta.cantidad) + diff)

    # Actualizar campos del registro
    if monto is not None:
        registro.monto = str(new_monto)
    if subCategorias_id is not None:
        registro.subCategorias_id = subCategorias_id

    # Manejo fino de categori_metodos_id: "", None, o número válido
    if categori_metodos_id is not None:
        cm_id = parse_optional_int(categori_metodos_id, "categori_metodos_id")
        if cm_id is None:
            registro.categori_metodos_id = None
        else:
            cm = db.query(CategoriaMetodo).filter(CategoriaMetodo.id == cm_id).first()
            if not cm:
                raise HTTPException(status_code=404, detail="Categoría método no encontrada")
            registro.categori_metodos_id = cm_id

    db.commit()
    db.refresh(registro)
    return registro

@router.delete("/{registro_id}")
def eliminar_registro(
    registro_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    registro = db.query(Registro).filter(
        Registro.id == registro_id,
        Registro.usuarios_id == current_user.id
    ).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    
    db.delete(registro)
    db.commit()
    return {"mensaje": "Registro eliminado exitosamente"}
