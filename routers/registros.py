from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from models.database import get_db, Registro, ListaCuenta, Subcategoria, CategoriaMetodo, Usuario
from models.schemas import RegistroResponse
from auth.auth import get_current_user

router = APIRouter(prefix="/registros", tags=["Registros"])

@router.get("/", response_model=List[RegistroResponse])
def listar_registros(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Registro).filter(Registro.usuarios_id == current_user.id).order_by(Registro.fecha_registro.desc()).all()

@router.post("/", response_model=RegistroResponse)
def crear_registro(
    lista_cuentas_id: int = Form(..., description="ID de la cuenta"),
    subCategorias_id: int = Form(..., description="ID de la subcategoría"),
    monto: str = Form(..., description="Monto del registro"),
    categori_metodos_id: int = Form(..., description="ID de la categoría método"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cuenta = db.query(ListaCuenta).filter(
        ListaCuenta.id == lista_cuentas_id,
        ListaCuenta.usuarios_id == current_user.id
    ).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    
    subcategoria = db.query(Subcategoria).filter(Subcategoria.id == subCategorias_id).first()
    if not subcategoria:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    
    categoria_metodo = db.query(CategoriaMetodo).filter(CategoriaMetodo.id == categori_metodos_id).first()
    if not categoria_metodo:
        raise HTTPException(status_code=404, detail="Categoría método no encontrada")
    
    db_registro = Registro(
        usuarios_id=current_user.id,
        lista_cuentas_id=lista_cuentas_id,
        subCategorias_id=subCategorias_id,
        monto=monto,
        fecha_registro=datetime.utcnow(),
        categori_metodos_id=categori_metodos_id
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
    categori_metodos_id: Optional[int] = Form(None, description="Nueva categoría método"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    registro = db.query(Registro).filter(
        Registro.id == registro_id,
        Registro.usuarios_id == current_user.id
    ).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    old_cuenta = registro.lista_cuenta
    old_monto = Decimal(registro.monto)

    new_cuenta = None
    if lista_cuentas_id is not None and lista_cuentas_id != old_cuenta.id:
        new_cuenta = db.query(ListaCuenta).filter(
            ListaCuenta.id == lista_cuentas_id,
            ListaCuenta.usuarios_id == current_user.id
        ).first()
        if not new_cuenta:
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        old_cuenta.cantidad = str(Decimal(old_cuenta.cantidad) - old_monto)
        registro.lista_cuentas_id = lista_cuentas_id

    if monto is not None:
        new_monto = Decimal(monto)
        cuenta_afin = new_cuenta or old_cuenta
        diff = new_monto - old_monto
        cuenta_afin.cantidad = str(Decimal(cuenta_afin.cantidad) + diff)
        registro.monto = monto

    if subCategorias_id is not None:
        registro.subCategorias_id = subCategorias_id
    if categori_metodos_id is not None:
        registro.categori_metodos_id = categori_metodos_id

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