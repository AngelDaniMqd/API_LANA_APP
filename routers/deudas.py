from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from models.database import get_db, Deuda, CategoriaMetodo, Usuario
from models.schemas import DeudaResponse
from auth.auth import get_current_user

router = APIRouter(prefix="/deudas", tags=["Deudas"])

@router.get("/", response_model=List[DeudaResponse])
def listar_deudas(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Deuda).all()

@router.post("/", response_model=DeudaResponse)
def crear_deuda(
    nombre: str = Form(..., description="Nombre de la deuda"),
    monto: str = Form(..., description="Monto de la deuda"),
    fecha_inicio: datetime = Form(..., description="Fecha de inicio"),
    fecha_vencimiento: datetime = Form(..., description="Fecha de vencimiento"),
    descripcion: str = Form(..., description="Descripción de la deuda"),
    categori_metodos_id: int = Form(..., description="ID de la categoría método"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    categoria_metodo = db.query(CategoriaMetodo).filter(CategoriaMetodo.id == categori_metodos_id).first()
    if not categoria_metodo:
        raise HTTPException(status_code=404, detail="Categoría método no encontrada")
    
    db_deuda = Deuda(
        nombre=nombre,
        monto=monto,
        fecha_inicio=fecha_inicio,
        fecha_vencimiento=fecha_vencimiento,
        descripcion=descripcion,
        categori_metodos_id=categori_metodos_id
    )
    db.add(db_deuda)
    db.commit()
    db.refresh(db_deuda)
    return db_deuda

@router.put("/{deuda_id}", response_model=DeudaResponse)
def actualizar_deuda(
    deuda_id: int,
    nombre: Optional[str] = Form(None, description="Nuevo nombre"),
    monto: Optional[str] = Form(None, description="Nuevo monto"),
    fecha_inicio: Optional[datetime] = Form(None, description="Nueva fecha de inicio"),
    fecha_vencimiento: Optional[datetime] = Form(None, description="Nueva fecha de vencimiento"),
    descripcion: Optional[str] = Form(None, description="Nueva descripción"),
    categori_metodos_id: Optional[int] = Form(None, description="Nueva categoría método"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    deuda = db.query(Deuda).filter(Deuda.id == deuda_id).first()
    if not deuda:
        raise HTTPException(status_code=404, detail="Deuda no encontrada")
    
    if nombre is not None:
        deuda.nombre = nombre
    if monto is not None:
        deuda.monto = monto
    if fecha_inicio is not None:
        deuda.fecha_inicio = fecha_inicio
    if fecha_vencimiento is not None:
        deuda.fecha_vencimiento = fecha_vencimiento
    if descripcion is not None:
        deuda.descripcion = descripcion
    if categori_metodos_id is not None:
        categoria_metodo = db.query(CategoriaMetodo).filter(CategoriaMetodo.id == categori_metodos_id).first()
        if not categoria_metodo:
            raise HTTPException(status_code=404, detail="Categoría método no encontrada")
        deuda.categori_metodos_id = categori_metodos_id
    
    db.commit()
    db.refresh(deuda)
    return deuda

@router.delete("/{deuda_id}")
def eliminar_deuda(
    deuda_id: int, 
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    deuda = db.query(Deuda).filter(Deuda.id == deuda_id).first()
    if not deuda:
        raise HTTPException(status_code=404, detail="Deuda no encontrada")
    
    db.delete(deuda)
    db.commit()
    return {"mensaje": "Deuda eliminada exitosamente"}