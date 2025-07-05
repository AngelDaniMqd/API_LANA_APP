from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List

from models.database import get_db, Subcategoria, Categoria, Usuario
from models.schemas import SubcategoriaResponse
from auth.auth import get_current_user

router = APIRouter(prefix="/subcategorias", tags=["Subcategorias"])

@router.get("/", response_model=List[SubcategoriaResponse])
def listar_subcategorias(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Subcategoria).all()

@router.post("/", response_model=SubcategoriaResponse)
def crear_subcategoria(
    categorias_id: int = Form(..., description="ID de la categoría"),
    descripcion: str = Form(..., description="Descripción de la subcategoría"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    categoria = db.query(Categoria).filter(Categoria.id == categorias_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    db_subcategoria = Subcategoria(
        categorias_id=categorias_id,
        descripcion=descripcion
    )
    db.add(db_subcategoria)
    db.commit()
    db.refresh(db_subcategoria)
    return db_subcategoria

@router.put("/{subcategoria_id}", response_model=SubcategoriaResponse)
def actualizar_subcategoria(
    subcategoria_id: int,
    descripcion: str = Form(..., description="Nueva descripción"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    subcategoria = db.query(Subcategoria).filter(Subcategoria.id == subcategoria_id).first()
    if not subcategoria:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    
    subcategoria.descripcion = descripcion
    db.commit()
    db.refresh(subcategoria)
    return subcategoria

@router.delete("/{subcategoria_id}")
def eliminar_subcategoria(
    subcategoria_id: int, 
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    subcategoria = db.query(Subcategoria).filter(Subcategoria.id == subcategoria_id).first()
    if not subcategoria:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    
    db.delete(subcategoria)
    db.commit()
    return {"mensaje": "Subcategoría eliminada exitosamente"}