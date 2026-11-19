"""Las páginas de web/, mostradas por la misma API.

Decisión de Sophia del 19 de noviembre de 2026: en su computadora la API
muestra también la web. Así la página y la API viven en la misma dirección
(http://127.0.0.1:8000/) y el navegador manda la cookie de sesión sin pedir
permisos entre sitios.

Las rutas de la API se registran antes y ganan siempre: /api/v1/..., /docs y
/openapi.json siguen siendo de la API. Todo lo demás se busca en web/.
"""

from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

ROUTE_NAME = "web"


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
    if not any(getattr(route, "name", None) == ROUTE_NAME for route in application.routes):
        application.mount("/", WebFiles(directory=directory, html=True), name=ROUTE_NAME)
    return True
