"""Punto de entrada de la API para Vercel.

Vercel ejecuta este archivo como una función de Python y le manda todo lo que empiece con /api/ (vercel.json). La
aplicación es la misma de backend/app/main.py; aquí solo se le dice dónde está. La configuración sale de las
variables de entorno del proyecto en Vercel, no de ningún archivo.

Las páginas de web/ no las muestra la función: Vercel las entrega directo, desde su red de distribución.
"""

import sys
from pathlib import Path

# El código del backend vive en backend/app; se agrega backend/ a la ruta de Python para poder escribir «from app...».
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import create_app  # noqa: E402

app = create_app(web_directory=None)
