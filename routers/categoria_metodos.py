from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List

from models.database import get_db, CategoriaMetodo, Usuario
from models.schemas import CategoriaMetodoResponse
from auth.auth import get_current_user

router = APIRouter(prefix="/categoria_metodos", tags=["Categoria Metodos"])

@router.get("/", response_model=List[CategoriaMetodoResponse])
def listar_categoria_metodos(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(CategoriaMetodo).all()

@router.post("/", response_model=CategoriaMetodoResponse)
def crear_categoria_metodo(
    nombre: str = Form(..., description="Nombre de la categoría método"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_categoria_metodo = CategoriaMetodo(nombre=nombre)
    db.add(db_categoria_metodo)
    db.commit()
    db.refresh(db_categoria_metodo)
    return db_categoria_metodo

@router.put("/{categoria_metodo_id}", response_model=CategoriaMetodoResponse)
def actualizar_categoria_metodo(
    categoria_metodo_id: int,
    nombre: str = Form(..., description="Nuevo nombre"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    categoria_metodo = db.query(CategoriaMetodo).filter(CategoriaMetodo.id == categoria_metodo_id).first()
    if not categoria_metodo:
        raise HTTPException(status_code=404, detail="Categoría método no encontrada")
    
    categoria_metodo.nombre = nombre
    db.commit()
    db.refresh(categoria_metodo)
    return categoria_metodo

@router.delete("/{categoria_metodo_id}")
def eliminar_categoria_metodo(
    categoria_metodo_id: int, 
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    categoria_metodo = db.query(CategoriaMetodo).filter(CategoriaMetodo.id == categoria_metodo_id).first()
    if not categoria_metodo:
        raise HTTPException(status_code=404, detail="Categoría método no encontrada")
    
    db.delete(categoria_metodo)
    db.commit()
    return {"mensaje": "Categoría método eliminada exitosamente"}