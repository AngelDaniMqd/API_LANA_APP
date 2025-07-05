from pydantic import BaseModel
from datetime import datetime

class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    apellidos: str
    telefono: int
    correo: str
    fecha_creacion: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class CategoriaResponse(BaseModel):
    id: int
    descripcion: str
    
    class Config:
        from_attributes = True

class SubcategoriaResponse(BaseModel):
    id: int
    categorias_id: int
    descripcion: str
    
    class Config:
        from_attributes = True

class CategoriaMetodoResponse(BaseModel):
    id: int
    nombre: str
    
    class Config:
        from_attributes = True

class ListaCuentaResponse(BaseModel):
    id: int
    usuarios_id: int
    nombre: str
    cantidad: str
    
    class Config:
        from_attributes = True

class RegistroResponse(BaseModel):
    id: int
    usuarios_id: int
    lista_cuentas_id: int
    subCategorias_id: int
    monto: str
    fecha_registro: datetime
    categori_metodos_id: int
    
    class Config:
        from_attributes = True

class DeudaResponse(BaseModel):
    id: int
    nombre: str
    monto: str
    fecha_inicio: datetime
    fecha_vencimiento: datetime
    descripcion: str
    categori_metodos_id: int
    
    class Config:
        from_attributes = True