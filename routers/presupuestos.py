from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, Float, cast
from typing import List
from datetime import datetime

from models.database import get_db, Presupuesto, Categoria, Usuario, Registro, Subcategoria
from models.schemas import PresupuestoResponse
from auth.auth import get_current_user

router = APIRouter(prefix="/presupuestos", tags=["Presupuestos"])

@router.get("/", response_model=List[PresupuestoResponse])
def listar_presupuestos(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    presupuestos = db.query(Presupuesto).filter(Presupuesto.usuarios_id == current_user.id).all()
    return presupuestos

@router.post("/", response_model=PresupuestoResponse)
def crear_presupuesto(
    categorias_id: int = Form(..., description="ID de la categoría"),
    monto_limite: float = Form(..., description="Monto límite del presupuesto"),
    mes: int = Form(..., description="Mes (1-12)", ge=1, le=12),
    ano: int = Form(..., description="Año", ge=2020),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existente = db.query(Presupuesto).filter(
        Presupuesto.usuarios_id == current_user.id,
        Presupuesto.categorias_id == categorias_id,
        Presupuesto.mes == mes,
        Presupuesto.ano == ano
    ).first()
    
    if existente:
        raise HTTPException(status_code=400, detail="Ya existe un presupuesto para esta categoría en este mes")
    
    categoria = db.query(Categoria).filter(Categoria.id == categorias_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    presupuesto = Presupuesto(
        usuarios_id=current_user.id,
        categorias_id=categorias_id,
        monto_limite=monto_limite,
        mes=mes,
        ano=ano
    )
    
    db.add(presupuesto)
    db.commit()
    db.refresh(presupuesto)
    return presupuesto

@router.get("/completo")
def listar_presupuestos_completo(
    current_user: Usuario = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    presupuestos = db.query(
        Presupuesto.id,
        Presupuesto.monto_limite,
        Presupuesto.mes,
        Presupuesto.ano,
        Presupuesto.fecha_creacion,
        Categoria.descripcion.label('categoria_nombre')
    ).join(Categoria, Presupuesto.categorias_id == Categoria.id).filter(
        Presupuesto.usuarios_id == current_user.id
    ).all()
    
    return [
        {
            "id": p.id,
            "categorias_id": 0,
            "monto_limite": p.monto_limite,
            "mes": p.mes,
            "ano": p.ano,
            "fecha_creacion": p.fecha_creacion,
            "categoria_nombre": p.categoria_nombre
        } for p in presupuestos
    ]

@router.get("/mes/{mes}/ano/{ano}")
def presupuestos_por_mes(
    mes: int,
    ano: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    presupuestos = db.query(
        Presupuesto.id,
        Presupuesto.monto_limite,
        Presupuesto.categorias_id,
        Categoria.descripcion.label('categoria')
    ).join(Categoria, Presupuesto.categorias_id == Categoria.id).filter(
        Presupuesto.usuarios_id == current_user.id,
        Presupuesto.mes == mes,
        Presupuesto.ano == ano
    ).all()
    
    resultado = []
    for p in presupuestos:
        gastos_actuales = db.query(
            func.sum(func.abs(cast(Registro.monto, Float)))
        ).join(Subcategoria, Registro.subCategorias_id == Subcategoria.id).filter(
            Registro.usuarios_id == current_user.id,
            Subcategoria.categorias_id == p.categorias_id,
            cast(Registro.monto, Float) < 0,
            extract('month', Registro.fecha_registro) == mes,
            extract('year', Registro.fecha_registro) == ano
        ).scalar() or 0
        
        resultado.append({
            "id": p.id,
            "categoria": p.categoria,
            "monto_limite": p.monto_limite,
            "gastado": float(gastos_actuales),
            "restante": p.monto_limite - float(gastos_actuales),
            "porcentaje_usado": round((float(gastos_actuales) / p.monto_limite * 100), 2) if p.monto_limite > 0 else 0,
            "excedido": float(gastos_actuales) > p.monto_limite
        })
    
    return {
        "mes": mes,
        "ano": ano,
        "presupuestos": resultado
    }

@router.put("/{presupuesto_id}", response_model=PresupuestoResponse)
def actualizar_presupuesto(
    presupuesto_id: int,
    categorias_id: int = Form(None, description="Nueva categoría ID"),
    monto_limite: float = Form(None, description="Nuevo monto límite"),
    mes: int = Form(None, description="Nuevo mes (1-12)", ge=1, le=12),
    ano: int = Form(None, description="Nuevo año", ge=2020),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    presupuesto = db.query(Presupuesto).filter(
        Presupuesto.id == presupuesto_id,
        Presupuesto.usuarios_id == current_user.id
    ).first()
    
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    if categorias_id is not None or mes is not None or ano is not None:
        nueva_categoria = categorias_id if categorias_id is not None else presupuesto.categorias_id
        nuevo_mes = mes if mes is not None else presupuesto.mes
        nuevo_ano = ano if ano is not None else presupuesto.ano
        
        existente = db.query(Presupuesto).filter(
            Presupuesto.usuarios_id == current_user.id,
            Presupuesto.categorias_id == nueva_categoria,
            Presupuesto.mes == nuevo_mes,
            Presupuesto.ano == nuevo_ano,
            Presupuesto.id != presupuesto_id
        ).first()
        
        if existente:
            raise HTTPException(status_code=400, detail="Ya existe un presupuesto para esta categoría en este mes/año")
        
        if categorias_id is not None:
            categoria = db.query(Categoria).filter(Categoria.id == categorias_id).first()
            if not categoria:
                raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    if categorias_id is not None:
        presupuesto.categorias_id = categorias_id
    if monto_limite is not None:
        presupuesto.monto_limite = monto_limite
    if mes is not None:
        presupuesto.mes = mes
    if ano is not None:
        presupuesto.ano = ano
    
    db.commit()
    db.refresh(presupuesto)
    return presupuesto

@router.delete("/{presupuesto_id}")
def eliminar_presupuesto(
    presupuesto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    presupuesto = db.query(Presupuesto).filter(
        Presupuesto.id == presupuesto_id,
        Presupuesto.usuarios_id == current_user.id
    ).first()
    
    if not presupuesto:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    db.delete(presupuesto)
    db.commit()
    return {"mensaje": "Presupuesto eliminado exitosamente"}
