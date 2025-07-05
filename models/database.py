from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Float, func, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:angel820@localhost:3306/lana_app")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    apellidos = Column(String(45), nullable=False)
    telefono = Column(Integer, nullable=False)
    correo = Column(String(100), unique=True, nullable=False)
    contrasena = Column(String(255), nullable=False)
    fecha_creacion = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    lista_cuentas = relationship("ListaCuenta", back_populates="usuario")
    registros = relationship("Registro", back_populates="usuario")

class Categoria(Base):
    __tablename__ = "categorias"
    
    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String(45), nullable=False)
    
    subcategorias = relationship("Subcategoria", back_populates="categoria")

class Subcategoria(Base):
    __tablename__ = "subcategorias"
    
    id = Column(Integer, primary_key=True, index=True)
    categorias_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    descripcion = Column(String(45), nullable=False)
    
    categoria = relationship("Categoria", back_populates="subcategorias")
    registros = relationship("Registro", back_populates="subcategoria")

class CategoriaMetodo(Base):
    __tablename__ = "categori_metodos"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(45), nullable=False)
    
    registros = relationship("Registro", back_populates="categoria_metodo")
    deudas = relationship("Deuda", back_populates="categoria_metodo")

class ListaCuenta(Base):
    __tablename__ = "lista_cuentas"
    
    id = Column(Integer, primary_key=True, index=True)
    usuarios_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre = Column(String(45), nullable=False)
    cantidad = Column(String(45), nullable=False)
    
    usuario = relationship("Usuario", back_populates="lista_cuentas")
    registros = relationship("Registro", back_populates="lista_cuenta")

class Registro(Base):
    __tablename__ = "registros"
    
    id = Column(Integer, primary_key=True, index=True)
    usuarios_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    lista_cuentas_id = Column(Integer, ForeignKey("lista_cuentas.id"), nullable=False)
    subCategorias_id = Column(Integer, ForeignKey("subcategorias.id"), nullable=False)
    monto = Column(String(45), nullable=False)
    fecha_registro = Column(DateTime, nullable=False, default=datetime.utcnow)
    categori_metodos_id = Column(Integer, ForeignKey("categori_metodos.id"), nullable=False)
    
    usuario = relationship("Usuario", back_populates="registros")
    lista_cuenta = relationship("ListaCuenta", back_populates="registros")
    subcategoria = relationship("Subcategoria", back_populates="registros")
    categoria_metodo = relationship("CategoriaMetodo", back_populates="registros")
    estadisticas = relationship("Estadistica", back_populates="registro")

class Deuda(Base):
    __tablename__ = "deudas"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(45), nullable=False)
    monto = Column(String(45), nullable=False)
    fecha_inicio = Column(DateTime, nullable=False)
    fecha_vencimiento = Column(DateTime, nullable=False)
    descripcion = Column(String(45), nullable=False)
    categori_metodos_id = Column(Integer, ForeignKey("categori_metodos.id"), nullable=False)
    
    categoria_metodo = relationship("CategoriaMetodo", back_populates="deudas")
    estadisticas = relationship("Estadistica", back_populates="deuda")

class Estadistica(Base):
    __tablename__ = "estadisticas"
    
    id = Column(Integer, primary_key=True, index=True)
    registros_id = Column(Integer, ForeignKey("registros.id"), nullable=False)
    deudas_id = Column(Integer, ForeignKey("deudas.id"), nullable=False)
    
    registro = relationship("Registro", back_populates="estadisticas")
    deuda = relationship("Deuda", back_populates="estadisticas")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()