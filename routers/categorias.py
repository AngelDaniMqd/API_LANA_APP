from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List

from models.database import get_db, Categoria, Usuario
from models.schemas import CategoriaResponse
from auth.auth import get_current_user

router = APIRouter(prefix="/categorias", tags=["Categorias"])

@router.get("/", response_model=List[CategoriaResponse])
def listar_categorias(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Categoria).all()

@router.post("/", response_model=CategoriaResponse)
def crear_categoria(
    descripcion: str = Form(..., description="Descripción de la categoría"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_categoria = Categoria(descripcion=descripcion)
    db.add(db_categoria)
    db.commit()
    db.refresh(db_categoria)
    return db_categoria

@router.put("/{categoria_id}", response_model=CategoriaResponse)
def actualizar_categoria(
    categoria_id: int,
    descripcion: str = Form(..., description="Nueva descripción"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    categoria.descripcion = descripcion
    db.commit()
    db.refresh(categoria)
    return categoria

@router.delete("/{categoria_id}")
def eliminar_categoria(
    categoria_id: int, 
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    db.delete(categoria)
    db.commit()
    return {"mensaje": "Categoría eliminada exitosamente"}