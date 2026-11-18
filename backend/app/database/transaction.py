"""Transacciones con papel: como el sistema o como una persona con sesión.

La API inicia sesión en la base con el usuario integro_api, que no tiene
permisos propios. En cada transacción elige con cuál de los dos papeles actúa
(ADR 0013):

- integro_service: el sistema. Registro, inicio de sesión, avisos de
  proveedores.
- integro_app: una persona con sesión. Solo alcanza sus propias filas, porque
  las reglas de la base leen su id del ajuste app.user_id.

El papel y el id se ponen con SET LOCAL: duran lo que dura la transacción. Al
terminar, con éxito o con error, la conexión vuelve al grupo como integro_api
y sin persona anotada, así que una petición nunca hereda la identidad de otra.

Todo acceso a las tablas pasa por system_transaction o user_transaction.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from psycopg import Connection
from psycopg_pool import ConnectionPool

SYSTEM_ROLE = "integro_service"
USER_ROLE = "integro_app"


class InvalidUserIdError(ValueError):
    """El id de la persona falta o no es un UUID."""


def parse_user_id(user_id: object) -> UUID:
    """Devuelve el id como UUID o lo rechaza. No toca la base de datos.

    Solo se acepta un UUID o un texto que lo sea. Vacío, None, números o
    cualquier otro texto se rechazan: integro_app nunca se usa sin persona.
    """
    if isinstance(user_id, UUID):
        return user_id
    if isinstance(user_id, str):
        try:
            return UUID(user_id)
        except ValueError:
            pass
    raise InvalidUserIdError("El id de la persona falta o no es un UUID.")


def set_system_actor(connection: Connection) -> None:
    """Dentro de una transacción abierta, pasa a actuar como el sistema."""
    connection.execute("set local role integro_service")
    # Se borra la persona anotada por si la transacción venía de actuar como una.
    connection.execute("select set_config('app.user_id', '', true)")


def set_user_actor(connection: Connection, user_id: object) -> None:
    """Dentro de una transacción abierta, pasa a actuar como esa persona."""
    validated = parse_user_id(user_id)
    connection.execute("set local role integro_app")
    # El id viaja como parámetro, nunca pegado al texto de la consulta.
    connection.execute("select set_config('app.user_id', %s, true)", (str(validated),))


@contextmanager
def system_transaction(pool: ConnectionPool) -> Iterator[Connection]:
    """Abre una transacción como el sistema.

    Se confirma al salir del bloque. Si el bloque falla, se deshace todo.
    """
    with pool.connection() as connection:
        with connection.transaction():
            set_system_actor(connection)
            yield connection


@contextmanager
def user_transaction(pool: ConnectionPool, user_id: object) -> Iterator[Connection]:
    """Abre una transacción como la persona con ese id.

    El id se valida antes de pedir una conexión: si no sirve, la base ni se
    toca. Se confirma al salir del bloque. Si el bloque falla, se deshace todo.
    """
    validated = parse_user_id(user_id)
    with pool.connection() as connection:
        with connection.transaction():
            set_user_actor(connection, validated)
            yield connection
