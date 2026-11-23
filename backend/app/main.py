"""Punto de entrada del backend de Íntegro.

Se arranca desde la carpeta backend/ con:  uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.config import WEB_DIRECTORY, Settings, load_settings
from app.database.connection import create_pool
from app.api.auth import NotAuthenticated, not_authenticated_response
from app.api.captcha import CaptchaRejected, captcha_rejected_response, create_captcha_verifier
from app.api.delivery import delivery_failed_response
from app.api.protection import Forbidden, forbidden_response
from app.notifications import create_code_sender
from app.notifications.sender import DeliveryFailed
from app.web import mount_web


def create_app(settings: Settings | None = None, web_directory: Path | None = WEB_DIRECTORY) -> FastAPI:
    """Construye la aplicación.

    Las pruebas pasan su propia configuración. Al arrancar con uvicorn no se
    pasa nada y la configuración se lee de backend/.env en el arranque, no al
    importar este archivo.

    web_directory es la carpeta de las páginas que la API también muestra.
    """

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.settings = settings or load_settings()
        application.state.code_sender = create_code_sender(application.state.settings)
        application.state.captcha = create_captcha_verifier(application.state.settings)
        # Las páginas se agregan al arrancar, cuando ya se leyó la
        # configuración. Son lo último que se busca: las rutas de la API
        # ganan siempre.
        if application.state.settings.serve_web:
            mount_web(application, web_directory)
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
    # Y toda ruta que cambia algo responde igual cuando la petición no pasa
    # las defensas contra páginas ajenas: 403.
    application.add_exception_handler(Forbidden, forbidden_response)
    # Las acciones que cualquiera puede pedir sin sesión piden CAPTCHA: 400 si no lo resolvió, 503 si no se pudo comprobar.
    application.add_exception_handler(CaptchaRejected, captcha_rejected_response)
    # Un código que no se pudo enviar por correo: 503 (ADR 0017). Las rutas que no pueden decirlo así lo atrapan antes.
    application.add_exception_handler(DeliveryFailed, delivery_failed_response)
    return application


app = create_app()
