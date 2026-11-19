"""Las páginas de web/, mostradas por la misma API.

Decisión de Sophia del 19 de noviembre de 2026: en su computadora la API
muestra también la web. Así la página y la API viven en la misma dirección
(http://127.0.0.1:8000/) y el navegador manda la cookie de sesión sin pedir
permisos entre sitios.

Las páginas son lo último que se busca: primero deciden las rutas de la API,
incluso para contestar que un método no está permitido (405). Solo cuando
ninguna ruta de la API coincide se busca el archivo en web/.
"""

from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

# Las páginas solo se leen.
READ_METHODS = ("GET", "HEAD")


class WebFiles(StaticFiles):
    """Entrega los archivos de web/ y nada que esté fuera de esa carpeta."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        # El navegador pregunta siempre si el archivo cambió: al editar una
        # página o los estilos, el cambio se ve al recargar.
        response.headers["Cache-Control"] = "no-cache"
        return response


def mount_web(application: FastAPI, directory: Path | None) -> bool:
    """Agrega las páginas a la aplicación. Devuelve si quedaron puestas.

    No hace nada si la carpeta no existe (por ejemplo, si solo se publica
    backend/) ni si ya estaban puestas.
    """
    if directory is None or not directory.is_dir():
        return False
    if getattr(application.state, "web_directory", None) is not None:
        return True

    files = WebFiles(directory=directory, html=True)
    not_found = application.router.default

    async def web_or_not_found(scope, receive, send):
        """Lo que no es de ninguna ruta de la API: una página, o 404."""
        if scope["type"] == "http" and scope["method"] in READ_METHODS:
            await files(scope, receive, send)
        else:
            await not_found(scope, receive, send)

    application.router.default = web_or_not_found
    application.state.web_directory = directory
    return True
