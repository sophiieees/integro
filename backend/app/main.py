"""Punto de entrada del backend de Íntegro.

Se arranca desde la carpeta backend/ con:  uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.config import Settings, load_settings
from app.database.connection import create_pool
from app.api.auth import NotAuthenticated, not_authenticated_response
from app.notifications import create_code_sender


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construye la aplicación.

    Las pruebas pasan su propia configuración. Al arrancar con uvicorn no se
    pasa nada y la configuración se lee de backend/.env en el arranque, no al
    importar este archivo.
    """

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.settings = settings or load_settings()
        application.state.code_sender = create_code_sender(application.state.settings)
        pool = create_pool(application.state.settings)
        # wait=False: la API arranca aunque la base esté apagada. Así
        # /api/v1/health sigue respondiendo y /api/v1/health/database avisa.
        pool.open(wait=False)
        application.state.pool = pool
        try:
            yield
        finally:
            pool.close()

    application = FastAPI(
        title="Íntegro API",
        version="0.1.0",
        description="API REST de Íntegro. Monolito modular; todas las rutas bajo /api/v1.",
        lifespan=lifespan,
    )
    application.include_router(api_v1_router)
    # Toda ruta que pida sesión responde igual cuando no la hay: 401.
    application.add_exception_handler(NotAuthenticated, not_authenticated_response)
    return application


app = create_app()
