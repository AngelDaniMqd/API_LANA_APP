from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from models.database import get_db, PagoFijo, Usuario
from models.schemas import PagoFijoResponse
from auth.auth import get_current_user

router = APIRouter(prefix="/pagos-fijos", tags=["Pagos Fijos"])

@router.get("/", response_model=List[PagoFijoResponse])
def listar_pagos_fijos(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(PagoFijo).filter(PagoFijo.usuarios_id == current_user.id).all()

@router.post("/", response_model=PagoFijoResponse)
def crear_pago_fijo(
    nombre: str = Form(..., description="Nombre del pago fijo"),
    monto: float = Form(..., description="Monto del pago"),
    dia_pago: int = Form(..., description="Día del mes para el pago (1-31)", ge=1, le=31),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pago_fijo = PagoFijo(
        usuarios_id=current_user.id,
        nombre=nombre,
        monto=monto,
        dia_pago=dia_pago,
        activo=1
    )
    
    db.add(pago_fijo)
    db.commit()
    db.refresh(pago_fijo)
    return pago_fijo

@router.put("/{pago_id}", response_model=PagoFijoResponse)
def actualizar_pago_fijo(
    pago_id: int,
    nombre: str = Form(None, description="Nuevo nombre"),
    monto: float = Form(None, description="Nuevo monto"),
    dia_pago: int = Form(None, description="Nuevo día de pago", ge=1, le=31),
    activo: int = Form(None, description="Estado activo (0 o 1)"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pago_fijo = db.query(PagoFijo).filter(
        PagoFijo.id == pago_id,
        PagoFijo.usuarios_id == current_user.id
    ).first()
    
    if not pago_fijo:
        raise HTTPException(status_code=404, detail="Pago fijo no encontrado")
    
    if nombre is not None:
        pago_fijo.nombre = nombre
    if monto is not None:
        pago_fijo.monto = monto
    if dia_pago is not None:
        pago_fijo.dia_pago = dia_pago
    if activo is not None:
        pago_fijo.activo = activo
    
    db.commit()
    db.refresh(pago_fijo)
    return pago_fijo

@router.delete("/{pago_id}")
def eliminar_pago_fijo(
    pago_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pago_fijo = db.query(PagoFijo).filter(
        PagoFijo.id == pago_id,
        PagoFijo.usuarios_id == current_user.id
    ).first()
    
    if not pago_fijo:
        raise HTTPException(status_code=404, detail="Pago fijo no encontrado")
    
    db.delete(pago_fijo)
    db.commit()
    return {"mensaje": "Pago fijo eliminado exitosamente"}

@router.get("/proximos")
def pagos_proximos(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    hoy = datetime.now()
    dia_actual = hoy.day
    
    pagos_fijos = db.query(PagoFijo).filter(
        PagoFijo.usuarios_id == current_user.id,
        PagoFijo.activo == 1
    ).all()
    
    proximos = []
    for pago in pagos_fijos:
        dias_restantes = pago.dia_pago - dia_actual
        if dias_restantes < 0:
            dias_restantes += 30
        
        proximos.append({
            "id": pago.id,
            "nombre": pago.nombre,
            "monto": pago.monto,
            "dia_pago": pago.dia_pago,
            "dias_restantes": dias_restantes,
            "urgente": dias_restantes <= 3
        })
    
    proximos.sort(key=lambda x: x["dias_restantes"])
    
    return {
        "total_pagos": len(proximos),
        "monto_total": sum(p["monto"] for p in proximos),
        "pagos_urgentes": len([p for p in proximos if p["urgente"]]),
        "proximos_pagos": proximos
    }
