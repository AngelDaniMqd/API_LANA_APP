from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import usuarios, lista_cuentas, categoria_metodos, categorias, subcategorias, registros, deudas, dashboard, presupuestos, pagos_fijos
app = FastAPI(
    title="Lana App API",
    description="API para control de finanzas personales",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(usuarios.router)
app.include_router(categorias.router)
app.include_router(subcategorias.router)
app.include_router(categoria_metodos.router)
app.include_router(lista_cuentas.router)
app.include_router(registros.router)
app.include_router(deudas.router)
app.include_router(presupuestos.router)
app.include_router(pagos_fijos.router)
app.include_router(dashboard.router)