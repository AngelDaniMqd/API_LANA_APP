from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from models.database import get_db, Usuario
from models.schemas import UsuarioResponse, Token
from auth.auth import get_password_hash, verify_password, create_access_token, get_current_user
from utils.sms import enviar_sms

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])





@router.post("/login", response_model=Token)
def login(
    correo: str = Form(..., description="Correo electrónico"),
    contrasena: str = Form(..., description="Contraseña"),
    db: Session = Depends(get_db)
):
    user = db.query(Usuario).filter(Usuario.correo == correo).first()
    if not user or not verify_password(contrasena, user.contrasena):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}










@router.post("/", response_model=UsuarioResponse)
def crear_usuario(
    nombre: str = Form(..., description="Nombre del usuario"),
    apellidos: str = Form(..., description="Apellidos del usuario"),
    telefono: int = Form(..., description="Número de teléfono"),
    correo: str = Form(..., description="Correo electrónico"),
    contrasena: str = Form(..., description="Contraseña"),
    db: Session = Depends(get_db)
):
    db_user = db.query(Usuario).filter(Usuario.correo == correo).first()
    if db_user:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    hashed_password = get_password_hash(contrasena)
    db_user = Usuario(
        nombre=nombre,
        apellidos=apellidos,
        telefono=telefono,
        correo=correo,
        contrasena=hashed_password,
        fecha_creacion=datetime.utcnow()
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user












@router.get("/", response_model=List[UsuarioResponse])
def listar_usuarios(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Usuario).all()




@router.get("/{usuario_id}", response_model=UsuarioResponse)
def obtener_usuario_por_id(
    usuario_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario







@router.put("/{usuario_id}", response_model=UsuarioResponse)
def actualizar_usuario(
    usuario_id: int,
    nombre: Optional[str] = Form(None, description="Nuevo nombre"),
    apellidos: Optional[str] = Form(None, description="Nuevos apellidos"),
    telefono: Optional[int] = Form(None, description="Nuevo teléfono"),
    correo: Optional[str] = Form(None, description="Nuevo correo electrónico"),
    contrasena: Optional[str] = Form(None, description="Nueva contraseña"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if nombre is not None:
        usuario.nombre = nombre
    if apellidos is not None:
        usuario.apellidos = apellidos
    if telefono is not None:
        usuario.telefono = telefono
    if correo is not None:
        existente = db.query(Usuario).filter(
            Usuario.correo == correo,
            Usuario.id != usuario_id
        ).first()
        if existente:
            raise HTTPException(status_code=400, detail="El correo ya está en uso")
        usuario.correo = correo
    if contrasena is not None:
        usuario.contrasena = get_password_hash(contrasena)

    db.commit()
    db.refresh(usuario)
    return usuario

@router.delete("/{usuario_id}")
def eliminar_usuario(
    usuario_id: int, 
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    db.delete(usuario)
    db.commit()
    return {"mensaje": "Usuario eliminado exitosamente"}

@router.post("/sms")
async def sms_usuario(
    descripcion: str = Form(..., description="Contenido del SMS"),
    current_user: Usuario = Depends(get_current_user),
):
    tel = str(current_user.telefono)
    numero = tel if tel.startswith("+") else f"+52{tel}"
    
    enviado = await enviar_sms(numero, descripcion)
    if not enviado:
        raise HTTPException(status_code=500, detail="Error al enviar SMS")
    return {
        "to": numero,
        "mensaje": descripcion,
        "enviado": True
    }