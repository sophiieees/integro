"""El perfil de anfitrión: pedirlo y verlo (pieza 3.1).

Decisiones de Sophia del 24 de noviembre de 2026 (bitácora 42.2 y la especificación de la pieza 3.1):

- Una persona con sesión y correo verificado puede pedir ser anfitriona. Queda con un perfil de nivel «new».
- Si ya tiene perfil y lo vuelve a pedir, se le entrega el que tiene, sin cambiarlo: un doble clic o un reintento no
  es un error, y un perfil «verified» o «suspended» nunca vuelve a «new» por pedirlo otra vez.
- La persona ve su propio perfil: el nivel y la fecha en que se creó. La cuenta de Stripe nunca sale de aquí.
- Al pedirlo no se le pide nada más. Aceptar términos de anfitrión o declarar que es dueña o copropietaria queda
  pendiente de la revisión legal de Valeria.
- Un administrador también puede pedirlo: ser administrador y ser anfitrión son dos permisos distintos.

No van aquí: exigir el Authenticator (pieza 3.3) ni verificar la identidad (pieza 3.5).

La tabla host_profiles ya existía (database/migrations/20261117000001): la persona lee su fila y solo el sistema la
escribe. Por eso el perfil lo crea el sistema, y se lee como la persona, para que la base misma solo le deje ver el suyo.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from psycopg_pool import ConnectionPool

from app.database.transaction import system_transaction, user_transaction


@dataclass(frozen=True)
class HostProfile:
    # new: recién pedido. verified: identidad comprobada (pieza 3.5). suspended: lo suspendió la plataforma.
    level: str
    created_at: datetime


class RequestOutcome(Enum):
    CREATED = "created"
    # Ya tenía perfil: se le entrega tal como está.
    EXISTING = "existing"
    EMAIL_NOT_VERIFIED = "email_not_verified"


@dataclass(frozen=True)
class RequestResult:
    outcome: RequestOutcome
    profile: HostProfile | None = None


def request_host_profile(pool: ConnectionPool, user_id: UUID) -> RequestResult:
    """Crea el perfil de anfitrión de esa persona, con nivel «new», o entrega el que ya tiene.

    El id sale de la sesión, nunca de lo que mande la página. Lo escribe el sistema, porque la persona no tiene
    permiso de escribir en host_profiles. Dos peticiones al mismo tiempo dejan una sola fila: la regla de único de
    user_id hace que la segunda no inserte, y entonces lee la que ya existe.
    """
    with system_transaction(pool) as connection:
        user = connection.execute("select email_verified_at from users where id = %s", (user_id,)).fetchone()
        # Para iniciar sesión hay que tener el correo comprobado, pero aquí se revisa otra vez: no se confía en que
        # siempre haya sido así.
        if user is None or user[0] is None:
            return RequestResult(RequestOutcome.EMAIL_NOT_VERIFIED)

        created = connection.execute(
            "insert into host_profiles (user_id) values (%s) on conflict (user_id) do nothing "
            "returning level, created_at",
            (user_id,),
        ).fetchone()
        if created is not None:
            return RequestResult(RequestOutcome.CREATED, HostProfile(level=created[0], created_at=created[1]))

        existing = connection.execute(
            "select level, created_at from host_profiles where user_id = %s", (user_id,)
        ).fetchone()
        return RequestResult(RequestOutcome.EXISTING, HostProfile(level=existing[0], created_at=existing[1]))


def read_host_profile(pool: ConnectionPool, user_id: UUID) -> HostProfile | None:
    """El perfil de anfitrión de esa persona, o None si no tiene.

    Se lee como la persona: la base solo le entrega su propia fila, aunque la consulta pidiera otra.
    """
    with user_transaction(pool, user_id) as connection:
        row = connection.execute(
            "select level, created_at from host_profiles where user_id = %s", (user_id,)
        ).fetchone()
    return None if row is None else HostProfile(level=row[0], created_at=row[1])
