# routers/objetivos.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship, Session
from pydantic import BaseModel, Field, confloat
from typing import List, Optional
from datetime import datetime

# Imports de tu proyecto
from models.database import get_db, engine, Base, Usuario
from auth.auth import get_current_user

# =========================
#  MODELOS SQLALCHEMY
# =========================
class Objetivo(Base):
    __tablename__ = "objetivos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    usuarios_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    tipo = Column(String(45), nullable=True)
    monto_meta = Column(Float, nullable=False)
    monto_ahorrado = Column(Float, nullable=False, default=0)
    fecha_inicio = Column(DateTime, nullable=True)
    fecha_vencimiento = Column(DateTime, nullable=True)
    estado = Column(Enum("activo","pausado","completado", name="estado_objetivo"), nullable=False, default="activo")
    fecha_creacion = Column(DateTime, nullable=True, default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)

    aportes = relationship("ObjetivoAporte", back_populates="objetivo", cascade="all, delete-orphan")


class ObjetivoAporte(Base):
    __tablename__ = "objetivo_aportes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    objetivo_id = Column(Integer, ForeignKey("objetivos.id", ondelete="CASCADE"), nullable=False, index=True)
    monto = Column(Float, nullable=False)  # positivo suma, negativo resta
    fecha = Column(DateTime, nullable=False, default=datetime.utcnow)
    nota = Column(String(120), nullable=True)

    objetivo = relationship("Objetivo", back_populates="aportes")


# Crea tablas si no existen (si usas Alembic, puedes quitar esto)
Base.metadata.create_all(bind=engine)

# =========================
#  ESQUEMAS Pydantic
# =========================
class ObjetivoBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    tipo: Optional[str] = Field(None, max_length=45)
    monto_meta: confloat(gt=0)
    fecha_inicio: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None

class ObjetivoCreate(ObjetivoBase):
    pass

class ObjetivoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=100)
    tipo: Optional[str] = Field(None, max_length=45)
    monto_meta: Optional[confloat(gt=0)] = None
    fecha_inicio: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None

class ObjetivoOut(BaseModel):
    id: int
    usuarios_id: int
    nombre: str
    tipo: Optional[str]
    monto_meta: float
    monto_ahorrado: float
    fecha_inicio: Optional[datetime]
    fecha_vencimiento: Optional[datetime]
    estado: str
    fecha_creacion: Optional[datetime]
    fecha_actualizacion: Optional[datetime]

    class Config:
        from_attributes = True

class CambiarEstadoIn(BaseModel):
    estado: str = Field(..., pattern="^(activo|pausado|completado)$")

class AporteCreate(BaseModel):
    monto: float  # puede ser negativo para corrección/retiro
    nota: Optional[str] = Field(None, max_length=120)

class AporteOut(BaseModel):
    id: int
    objetivo_id: int
    monto: float
    fecha: datetime
    nota: Optional[str]

    class Config:
        from_attributes = True

# =========================
#  ROUTER
# =========================
router = APIRouter(prefix="/objetivos", tags=["Objetivos"])

# Helper: obtener objetivo del usuario (y lanzar 404 si no es suyo)
def get_objetivo_propietario(db: Session, objetivo_id: int, user_id: int) -> Objetivo:
    obj = db.query(Objetivo).filter(
        Objetivo.id == objetivo_id,
        Objetivo.usuarios_id == user_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado")
    return obj

# Listar objetivos SOLO del usuario logueado (opcional filtrar por estado)
@router.get("/", response_model=List[ObjetivoOut])
def listar_objetivos(
    estado: Optional[str] = Query(None, pattern="^(activo|pausado|completado)$"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Objetivo).filter(Objetivo.usuarios_id == current_user.id)
    if estado:
        q = q.filter(Objetivo.estado == estado)
    return q.order_by(Objetivo.fecha_creacion.desc()).all()

# Detalle (propiedad verificada)
@router.get("/{objetivo_id}", response_model=ObjetivoOut)
def obtener_objetivo(
    objetivo_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_objetivo_propietario(db, objetivo_id, current_user.id)

# Crear (asigna usuarios_id desde el token)
@router.post("/", response_model=ObjetivoOut, status_code=status.HTTP_201_CREATED)
def crear_objetivo(
    data: ObjetivoCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    obj = Objetivo(
        usuarios_id=current_user.id,
        nombre=data.nombre,
        tipo=data.tipo,
        monto_meta=data.monto_meta,
        monto_ahorrado=0,
        fecha_inicio=data.fecha_inicio,
        fecha_vencimiento=data.fecha_vencimiento,
        estado="activo",
        fecha_creacion=datetime.utcnow(),
        fecha_actualizacion=datetime.utcnow(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

# Editar (solo propio)
@router.put("/{objetivo_id}", response_model=ObjetivoOut)
def actualizar_objetivo(
    objetivo_id: int,
    data: ObjetivoUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    obj = get_objetivo_propietario(db, objetivo_id, current_user.id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.fecha_actualizacion = datetime.utcnow()
    db.commit()
    db.refresh(obj)
    return obj

# Eliminar (solo propio)
@router.delete("/{objetivo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_objetivo(
    objetivo_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    obj = get_objetivo_propietario(db, objetivo_id, current_user.id)
    db.delete(obj)
    db.commit()
    return None

# PATCH = actualización parcial (solo cambia 'estado')
@router.patch("/{objetivo_id}/estado", response_model=ObjetivoOut)
def cambiar_estado(
    objetivo_id: int,
    body: CambiarEstadoIn,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    obj = get_objetivo_propietario(db, objetivo_id, current_user.id)
    obj.estado = body.estado
    obj.fecha_actualizacion = datetime.utcnow()
    db.commit()
    db.refresh(obj)
    return obj

# Registrar aporte (suma/resta) y validar propiedad
@router.post("/{objetivo_id}/aportes", response_model=AporteOut, status_code=status.HTTP_201_CREATED)
def crear_aporte(
    objetivo_id: int,
    data: AporteCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    obj = get_objetivo_propietario(db, objetivo_id, current_user.id)

    ap = ObjetivoAporte(
        objetivo_id=obj.id,
        monto=float(data.monto),
        nota=data.nota,
        fecha=datetime.utcnow(),
    )
    obj.monto_ahorrado = (obj.monto_ahorrado or 0) + float(data.monto)
    obj.fecha_actualizacion = datetime.utcnow()

    db.add(ap)
    db.add(obj)
    db.commit()
    db.refresh(ap)
    return ap

# Listar aportes del objetivo (solo propio)
@router.get("/{objetivo_id}/aportes", response_model=List[AporteOut])
def listar_aportes(
    objetivo_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _ = get_objetivo_propietario(db, objetivo_id, current_user.id)
    return db.query(ObjetivoAporte)\
             .filter(ObjetivoAporte.objetivo_id == objetivo_id)\
             .order_by(ObjetivoAporte.fecha.desc())\
             .all()
