from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List, Optional
# arriba del archivo:
from models.database import get_db, ListaCuenta, Usuario, Registro, Estadistica

from models.database import get_db, ListaCuenta, Usuario
from models.schemas import ListaCuentaResponse
from auth.auth import get_current_user

router = APIRouter(prefix="/lista_cuentas", tags=["Lista Cuentas"])

@router.get("/", response_model=List[ListaCuentaResponse])
def listar_cuentas(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(ListaCuenta).filter(ListaCuenta.usuarios_id == current_user.id).all()

@router.post("/", response_model=ListaCuentaResponse)
def crear_cuenta(
    nombre: str = Form(..., description="Nombre de la cuenta"),
    cantidad: str = Form(..., description="Cantidad/saldo de la cuenta"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_cuenta = ListaCuenta(
        usuarios_id=current_user.id,
        nombre=nombre,
        cantidad=cantidad
    )
    db.add(db_cuenta)
    db.commit()
    db.refresh(db_cuenta)
    return db_cuenta

@router.put("/{cuenta_id}", response_model=ListaCuentaResponse)
def actualizar_cuenta(
    cuenta_id: int,
    nombre: Optional[str] = Form(None, description="Nuevo nombre"),
    cantidad: Optional[str] = Form(None, description="Nueva cantidad"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cuenta = db.query(ListaCuenta).filter(
        ListaCuenta.id == cuenta_id,
        ListaCuenta.usuarios_id == current_user.id
    ).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    
    if nombre is not None:
        cuenta.nombre = nombre
    if cantidad is not None:
        cuenta.cantidad = cantidad
    
    db.commit()
    db.refresh(cuenta)
    return cuenta

@router.delete("/{cuenta_id}")
def eliminar_cuenta(
    cuenta_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cuenta = (
        db.query(ListaCuenta)
        .filter(ListaCuenta.id == cuenta_id, ListaCuenta.usuarios_id == current_user.id)
        .first()
    )
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    try:
        reg_ids = [
            r.id for r in db.query(Registro.id).filter(
                Registro.lista_cuentas_id == cuenta_id,
                Registro.usuarios_id == current_user.id,
            ).all()
        ]

        deleted_stats = 0
        if reg_ids:
            deleted_stats = db.query(Estadistica).filter(
                Estadistica.registros_id.in_(reg_ids)
            ).delete(synchronize_session=False)

        deleted_regs = db.query(Registro).filter(
            Registro.lista_cuentas_id == cuenta_id,
            Registro.usuarios_id == current_user.id,
        ).delete(synchronize_session=False)

        db.delete(cuenta)
        db.commit()

        return {
            "mensaje": "Cuenta y datos relacionados eliminados exitosamente",
            "eliminados": {"registros": int(deleted_regs), "estadisticas": int(deleted_stats)},
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar la cuenta: {e}")
