from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, Float, case, and_
from datetime import datetime, timedelta
from typing import Optional

from models.database import get_db, ListaCuenta, Registro, Deuda, Subcategoria, Usuario, CategoriaMetodo
from auth.auth import get_current_user

router = APIRouter(prefix="/graficos", tags=["Graficos"])

# Diccionario para traducir meses a español
MESES_ESPAÑOL = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

@router.get("/resumen")
def resumen_financiero(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    total_saldo = db.query(func.sum(func.cast(ListaCuenta.cantidad, Float))).filter(
        ListaCuenta.usuarios_id == current_user.id
    ).scalar() or 0
    
    total_movimientos = db.query(func.count(Registro.id)).filter(
        Registro.usuarios_id == current_user.id
    ).scalar() or 0
    
    ingresos_mes = db.query(func.sum(func.cast(Registro.monto, Float))).filter(
        Registro.usuarios_id == current_user.id,
        func.cast(Registro.monto, Float) > 0,
        extract('month', Registro.fecha_registro) == datetime.now().month,
        extract('year', Registro.fecha_registro) == datetime.now().year
    ).scalar() or 0
    
    gastos_mes = db.query(func.sum(func.cast(Registro.monto, Float))).filter(
        Registro.usuarios_id == current_user.id,
        func.cast(Registro.monto, Float) < 0,
        extract('month', Registro.fecha_registro) == datetime.now().month,
        extract('year', Registro.fecha_registro) == datetime.now().year
    ).scalar() or 0
    
    return {
        "total_saldo": float(total_saldo),
        "total_movimientos": total_movimientos,
        "ingresos_mes": float(ingresos_mes),
        "gastos_mes": float(abs(gastos_mes)),
        "balance_mes": float(ingresos_mes + gastos_mes),
        "usuario": f"{current_user.nombre} {current_user.apellidos}"
    }

@router.get("/por-dias")
def movimientos_por_dias(
    dias: int = Query(30, description="Número de días hacia atrás", ge=1, le=365),
    current_user: Usuario = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    fecha_inicio = datetime.now() - timedelta(days=dias)
    
    movimientos_diarios = db.query(
        func.date(Registro.fecha_registro).label('fecha'),
        func.sum(case((func.cast(Registro.monto, Float) > 0, func.cast(Registro.monto, Float)), else_=0)).label('ingresos'),
        func.sum(case((func.cast(Registro.monto, Float) < 0, func.abs(func.cast(Registro.monto, Float))), else_=0)).label('gastos'),
        func.count(Registro.id).label('cantidad_movimientos')
    ).filter(
        Registro.usuarios_id == current_user.id,
        Registro.fecha_registro >= fecha_inicio
    ).group_by(func.date(Registro.fecha_registro)).order_by('fecha').all()
    
    registros_detallados = db.query(
        Registro.id,
        Registro.monto,
        Registro.fecha_registro,
        Subcategoria.descripcion.label('categoria'),
        CategoriaMetodo.nombre.label('metodo'),
        ListaCuenta.nombre.label('cuenta')
    ).join(Subcategoria, Registro.subCategorias_id == Subcategoria.id).join(
        CategoriaMetodo, Registro.categori_metodos_id == CategoriaMetodo.id
    ).join(ListaCuenta, Registro.lista_cuentas_id == ListaCuenta.id).filter(
        Registro.usuarios_id == current_user.id,
        Registro.fecha_registro >= fecha_inicio
    ).order_by(Registro.fecha_registro.desc()).all()
    
    return {
        "periodo": f"Últimos {dias} días",
        "fecha_inicio": fecha_inicio.strftime('%Y-%m-%d'),
        "fecha_fin": datetime.now().strftime('%Y-%m-%d'),
        "resumen_diario": [
            {
                "fecha": r.fecha.strftime('%Y-%m-%d'),
                "ingresos": float(r.ingresos or 0),
                "gastos": float(r.gastos or 0),
                "balance": float((r.ingresos or 0) - (r.gastos or 0)),
                "cantidad_movimientos": r.cantidad_movimientos
            } for r in movimientos_diarios
        ],
        "movimientos_individuales": [
            {
                "id": r.id,
                "monto": float(r.monto),
                "fecha": r.fecha_registro.strftime('%Y-%m-%d %H:%M:%S'),
                "categoria": r.categoria,
                "metodo": r.metodo,
                "cuenta": r.cuenta,
                "tipo": "ingreso" if float(r.monto) > 0 else "gasto"
            } for r in registros_detallados
        ]
    }

@router.get("/por-categoria")
def gastos_por_categoria(
    dias: Optional[int] = Query(30, description="Número de días hacia atrás"),
    current_user: Usuario = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    fecha_inicio = datetime.now() - timedelta(days=dias) if dias else None
    
    query_filter = [Registro.usuarios_id == current_user.id]
    if fecha_inicio:
        query_filter.append(Registro.fecha_registro >= fecha_inicio)
    
    por_categoria = db.query(
        Subcategoria.descripcion.label('categoria'),
        func.sum(case((func.cast(Registro.monto, Float) > 0, func.cast(Registro.monto, Float)), else_=0)).label('ingresos'),
        func.sum(case((func.cast(Registro.monto, Float) < 0, func.abs(func.cast(Registro.monto, Float))), else_=0)).label('gastos'),
        func.count(Registro.id).label('cantidad')
    ).join(Registro, Registro.subCategorias_id == Subcategoria.id).filter(
        and_(*query_filter)
    ).group_by(Subcategoria.descripcion).all()
    
    total_ingresos = sum(float(r.ingresos or 0) for r in por_categoria)
    total_gastos = sum(float(r.gastos or 0) for r in por_categoria)
    
    return {
        "periodo": f"Últimos {dias} días" if dias else "Todos los registros",
        "total_ingresos": total_ingresos,
        "total_gastos": total_gastos,
        "categorias": [
            {
                "categoria": r.categoria,
                "ingresos": float(r.ingresos or 0),
                "gastos": float(r.gastos or 0),
                "total": float((r.ingresos or 0) + (r.gastos or 0)),
                "cantidad": r.cantidad,
                "porcentaje_ingresos": round((float(r.ingresos or 0) / total_ingresos * 100), 2) if total_ingresos > 0 else 0,
                "porcentaje_gastos": round((float(r.gastos or 0) / total_gastos * 100), 2) if total_gastos > 0 else 0
            } for r in por_categoria
        ]
    }

@router.get("/por-metodo")
def gastos_por_metodo(
    dias: Optional[int] = Query(30, description="Número de días hacia atrás"),
    current_user: Usuario = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    fecha_inicio = datetime.now() - timedelta(days=dias) if dias else None
    
    query_filter = [Registro.usuarios_id == current_user.id]
    if fecha_inicio:
        query_filter.append(Registro.fecha_registro >= fecha_inicio)
    
    por_metodo = db.query(
        CategoriaMetodo.nombre.label('metodo'),
        func.sum(case((func.cast(Registro.monto, Float) > 0, func.cast(Registro.monto, Float)), else_=0)).label('ingresos'),
        func.sum(case((func.cast(Registro.monto, Float) < 0, func.abs(func.cast(Registro.monto, Float))), else_=0)).label('gastos'),
        func.count(Registro.id).label('cantidad')
    ).join(Registro, Registro.categori_metodos_id == CategoriaMetodo.id).filter(
        and_(*query_filter)
    ).group_by(CategoriaMetodo.nombre).all()
    
    return {
        "periodo": f"Últimos {dias} días" if dias else "Todos los registros",
        "metodos": [
            {
                "metodo": r.metodo,
                "ingresos": float(r.ingresos or 0),
                "gastos": float(r.gastos or 0),
                "total": float((r.ingresos or 0) + (r.gastos or 0)),
                "cantidad": r.cantidad
            } for r in por_metodo
        ]
    }

@router.get("/tendencia-mensual")
def tendencia_mensual(
    current_user: Usuario = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    tendencia = db.query(
        extract('year', Registro.fecha_registro).label('año'),
        extract('month', Registro.fecha_registro).label('mes'),
        func.sum(case((func.cast(Registro.monto, Float) > 0, func.cast(Registro.monto, Float)), else_=0)).label('ingresos'),
        func.sum(case((func.cast(Registro.monto, Float) < 0, func.abs(func.cast(Registro.monto, Float))), else_=0)).label('gastos'),
        func.count(Registro.id).label('cantidad')
    ).filter(
        Registro.usuarios_id == current_user.id
    ).group_by(
        extract('year', Registro.fecha_registro),
        extract('month', Registro.fecha_registro)
    ).order_by('año', 'mes').all()
    
    return {
        "tendencia_mensual": [
            {
                "año": int(r.año),
                "mes": int(r.mes),
                "mes_nombre": MESES_ESPAÑOL[int(r.mes)],
                "ingresos": float(r.ingresos or 0),
                "gastos": float(r.gastos or 0),
                "balance": float((r.ingresos or 0) - (r.gastos or 0)),
                "cantidad": r.cantidad
            } for r in tendencia
        ]
    }

@router.get("/cuentas")
def resumen_cuentas(
    current_user: Usuario = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    cuentas = db.query(
        ListaCuenta.id,
        ListaCuenta.nombre,
        ListaCuenta.cantidad,
        func.count(Registro.id).label('movimientos')
    ).outerjoin(Registro, ListaCuenta.id == Registro.lista_cuentas_id).filter(
        ListaCuenta.usuarios_id == current_user.id
    ).group_by(ListaCuenta.id, ListaCuenta.nombre, ListaCuenta.cantidad).all()
    
    total_saldo = sum(float(c.cantidad) for c in cuentas)
    
    return {
        "total_saldo": total_saldo,
        "cuentas": [
            {
                "id": c.id,
                "nombre": c.nombre,
                "saldo": float(c.cantidad),
                "movimientos": c.movimientos
            } for c in cuentas
        ]
    }

@router.get("/circular-gastos")
def grafica_circular_gastos(
    dias: int = Query(30, description="Número de días hacia atrás", ge=1, le=365),
    current_user: Usuario = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    fecha_inicio = datetime.now() - timedelta(days=dias)
    
    gastos_por_categoria = db.query(
        Subcategoria.descripcion.label('categoria'),
        func.sum(func.abs(func.cast(Registro.monto, Float))).label('total_gastos')
    ).join(Registro, Registro.subCategorias_id == Subcategoria.id).filter(
        Registro.usuarios_id == current_user.id,
        func.cast(Registro.monto, Float) < 0,  # Solo gastos
        Registro.fecha_registro >= fecha_inicio
    ).group_by(Subcategoria.descripcion).all()
    
    total_gastos = sum(float(r.total_gastos) for r in gastos_por_categoria)
    
    return {
        "periodo": f"Últimos {dias} días",
        "total_gastos": total_gastos,
        "categorias_gastos": [
            {
                "categoria": r.categoria,
                "monto": float(r.total_gastos),
                "porcentaje": round((float(r.total_gastos) / total_gastos * 100), 2) if total_gastos > 0 else 0
            } for r in gastos_por_categoria
        ]
    }

@router.get("/circular-ingresos")
def grafica_circular_ingresos(
    dias: int = Query(30, description="Número de días hacia atrás", ge=1, le=365),
    current_user: Usuario = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    fecha_inicio = datetime.now() - timedelta(days=dias)
    
    ingresos_por_categoria = db.query(
        Subcategoria.descripcion.label('categoria'),
        func.sum(func.cast(Registro.monto, Float)).label('total_ingresos')
    ).join(Registro, Registro.subCategorias_id == Subcategoria.id).filter(
        Registro.usuarios_id == current_user.id,
        func.cast(Registro.monto, Float) > 0,  # Solo ingresos
        Registro.fecha_registro >= fecha_inicio
    ).group_by(Subcategoria.descripcion).all()
    
    total_ingresos = sum(float(r.total_ingresos) for r in ingresos_por_categoria)
    
    return {
        "periodo": f"Últimos {dias} días",
        "total_ingresos": total_ingresos,
        "categorias_ingresos": [
            {
                "categoria": r.categoria,
                "monto": float(r.total_ingresos),
                "porcentaje": round((float(r.total_ingresos) / total_ingresos * 100), 2) if total_ingresos > 0 else 0
            } for r in ingresos_por_categoria
        ]
    }