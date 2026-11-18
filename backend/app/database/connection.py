"""Grupo de conexiones a PostgreSQL y comprobación de que la base responde.

Se usa psycopg 3 con SQL directo, igual que las migraciones. El grupo es
síncrono: FastAPI atiende cada petición síncrona en un hilo aparte, y en
Windows la variante asíncrona de psycopg no funciona con el ciclo de eventos
que el sistema usa por defecto.
"""

import logging
from dataclasses import dataclass

import psycopg
from psycopg_pool import ConnectionPool

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Segundos que se espera una conexión antes de dar la base por no disponible.
CONNECTION_TIMEOUT_SECONDS = 3
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 5


@dataclass(frozen=True)
class DatabaseStatus:
    """Lo que la base dice de sí misma cuando responde."""

    database: str
    port: int
    server_version: str


def create_pool(settings: Settings) -> ConnectionPool:
    """Prepara el grupo de conexiones sin abrirlo.

    Los datos de conexión se pasan por separado, no en una cadena, para que la
    contraseña no quede en un texto que pueda terminar en un registro.
    """
    return ConnectionPool(
        kwargs={
            "host": settings.database_host,
            "port": settings.database_port,
            "dbname": settings.database_name,
            "user": settings.database_user,
            "password": settings.database_password.get_secret_value(),
            "connect_timeout": CONNECTION_TIMEOUT_SECONDS,
            "application_name": "integro-api",
        },
        min_size=POOL_MIN_SIZE,
        max_size=POOL_MAX_SIZE,
        timeout=CONNECTION_TIMEOUT_SECONDS,
        # Antes de entregar una conexión comprueba que siga viva.
        check=ConnectionPool.check_connection,
        name="integro",
        open=False,
    )


def read_database_status(pool: ConnectionPool) -> DatabaseStatus | None:
    """Pregunta a la base su nombre, su puerto y su versión.

    Devuelve None si la base no responde: apagada, credenciales incorrectas o
    sin conexiones libres. El motivo se anota en el registro del servidor y
    nunca se devuelve a quien hizo la petición.
    """
    try:
        with pool.connection(timeout=CONNECTION_TIMEOUT_SECONDS) as connection:
            row = connection.execute(
                "select current_database(), inet_server_port(), "
                "current_setting('server_version')"
            ).fetchone()
    except psycopg.Error as error:
        logger.warning("La base de datos no respondió: %s", type(error).__name__)
        return None
    return DatabaseStatus(database=row[0], port=row[1], server_version=row[2])
