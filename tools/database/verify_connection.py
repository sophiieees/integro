"""Comprueba que la API puede usar una base de datos (por ejemplo, la de Neon) sin romper la seguridad por papeles.

Se usa antes de publicar la API en la nube (docs/despliegue-vercel-neon.md). No escribe nada en la base: solo lee.
Usa el mismo código que la API (grupo de conexiones y transacciones con papel), con la configuración de un
archivo de variables, y nunca imprime la contraseña ni la llave de los códigos.

Qué comprueba:

     1. Que conecta, qué versión de PostgreSQL es y si la conexión del lado de la API va cifrada (SSL). Se pregunta
        del lado del cliente: en Neon, el cifrado termina en su entrada y la base nunca lo ve (pg_stat_ssl diría NO).
     2. Que fuera de una transacción con papel, la API es integro_api y no ve ninguna persona.
     3. Que system_transaction actúa como integro_service y user_transaction como integro_app con el id de esa persona.
     4. Que al terminar la transacción la conexión vuelve a ser integro_api y sin persona anotada, también cuando
        la transacción falla.
     5. Que integro_api por sí solo no puede leer ninguna tabla.
     6. Que integro_app con una persona que no existe no ve ninguna fila de users.
     7. Que ninguna petición hereda la identidad de otra: cientos de transacciones seguidas, alternando entre
        sistema y personas distintas y desde varios hilos a la vez, siempre ven exactamente su papel y su persona.
        También dice cuánto tarda cada una (sirve para calcular la latencia entre Vercel y Neon). Si el grupo de
        conexiones se queda sin lugar a tiempo, eso se dice aparte: no es un fallo de identidad.

Se corre desde la raíz del repositorio, con el entorno virtual del backend activo:

    python tools/database/verify_connection.py --env backend/.env.neon

Cada caso imprime lo esperado, lo obtenido y COINCIDE o NO COINCIDE. El programa termina con código 0 solo si todos
coinciden. Si el archivo trae DATABASE_HOST_DIRECT, se repite todo también con esa dirección (la directa de Neon).
"""

import argparse
import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

import psycopg  # noqa: E402
from psycopg_pool import ConnectionPool, PoolTimeout  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.database.connection import create_pool  # noqa: E402
from app.database.transaction import system_transaction, user_transaction  # noqa: E402

ROUNDS = 200
# Menos hilos que conexiones del grupo (POOL_MAX_SIZE = 5): se prueba la identidad, no la saturación del grupo.
THREADS = 4


def read_env_value(path: Path, name: str) -> str | None:
    """Un valor del archivo de variables, sin imprimirlo. Solo para las que Settings no conoce."""
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == name:
            return value.strip().strip("\"'")
    return None


class Report:
    def __init__(self):
        self.results: list[bool] = []

    def compare(self, case: str, expected, obtained) -> None:
        ok = expected == obtained
        self.results.append(ok)
        print(f"{'COINCIDE   ' if ok else 'NO COINCIDE'}  {case}")
        if not ok:
            print(f"                esperado: {expected!r}")
            print(f"                obtenido: {obtained!r}")

    def info(self, text: str) -> None:
        print(f"              {text}")


def person_in_session(connection) -> str:
    """La persona anotada en esta transacción: vacío si no hay ninguna."""
    return connection.execute("select coalesce(current_setting('app.user_id', true), '')").fetchone()[0]


def check(pool: ConnectionPool, name: str, report: Report) -> None:
    print(f"\n== {name} ==")

    # 1. Qué es la conexión.
    with pool.connection() as connection:
        version = connection.execute("select current_setting('server_version')").fetchone()[0]
        ssl = bool(connection.pgconn.ssl_in_use)
        report.info(f"PostgreSQL {version}; cifrada con SSL: {'sí' if ssl else 'NO'}")
        report.compare("la conexión va cifrada con SSL (en una base en la nube; en la local no hace falta)", True, ssl or name.startswith("base local"))

        # 2. Sin papel.
        report.compare(
            "fuera de una transacción con papel, la API es integro_api y no ve ninguna persona",
            ("integro_api", ""),
            (connection.execute("select current_user").fetchone()[0], person_in_session(connection)),
        )

    # 3. Los dos papeles.
    person = uuid.uuid4()
    with system_transaction(pool) as connection:
        as_system = (connection.execute("select current_user").fetchone()[0], person_in_session(connection))
    report.compare("system_transaction actúa como integro_service y sin persona", ("integro_service", ""), as_system)
    with user_transaction(pool, person) as connection:
        as_person = (connection.execute("select current_user").fetchone()[0], person_in_session(connection))
    report.compare("user_transaction actúa como integro_app con el id de esa persona", ("integro_app", str(person)), as_person)

    # 4. Al terminar, se vuelve a integro_api, con éxito y con error.
    def after() -> tuple:
        with pool.connection() as connection:
            with connection.transaction():
                return (connection.execute("select current_user").fetchone()[0], person_in_session(connection))

    report.compare("después de una transacción de persona, la conexión vuelve a integro_api y sin persona", ("integro_api", ""), after())
    try:
        with user_transaction(pool, person) as connection:
            connection.execute("select 1/0")
    except psycopg.errors.DivisionByZero:
        pass
    report.compare("después de una transacción que falla, también", ("integro_api", ""), after())

    # 5. Sin papel no se lee nada.
    try:
        with pool.connection() as connection:
            with connection.transaction():
                connection.execute("select count(*) from users").fetchone()
        denied = "pudo leer users"
    except psycopg.errors.InsufficientPrivilege:
        denied = "permiso denegado"
    except psycopg.errors.UndefinedTable:
        denied = "no existe users: faltan las migraciones"
    report.compare("integro_api por sí solo no puede leer las tablas", "permiso denegado", denied)

    # 6. Una persona que no existe no ve filas.
    try:
        with user_transaction(pool, uuid.uuid4()) as connection:
            rows = connection.execute("select count(*) from users").fetchone()[0]
        report.compare("integro_app con una persona que no existe no ve ninguna fila de users", 0, rows)
    except psycopg.errors.UndefinedTable:
        report.compare("integro_app con una persona que no existe no ve ninguna fila de users", 0, "faltan las migraciones")

    # 7. Ninguna petición hereda la identidad de otra.
    people = [uuid.uuid4() for _ in range(25)]
    plan = [random.choice(["system", "plain", "person"]) for _ in range(ROUNDS)]
    chosen = [random.choice(people) for _ in range(ROUNDS)]

    def one(index: int) -> tuple[str | None, float]:
        """(problema de identidad o de espera, segundos que tardó), para la transacción número `index`."""
        kind = plan[index]
        started = time.monotonic()
        try:
            if kind == "system":
                with system_transaction(pool) as connection:
                    got = (connection.execute("select current_user").fetchone()[0], person_in_session(connection))
                problem = None if got == ("integro_service", "") else f"sistema vio {got}"
            elif kind == "person":
                with user_transaction(pool, chosen[index]) as connection:
                    got = (connection.execute("select current_user").fetchone()[0], person_in_session(connection))
                problem = None if got == ("integro_app", str(chosen[index])) else f"persona {chosen[index]} vio {got}"
            else:
                with pool.connection() as connection:
                    with connection.transaction():
                        got = (connection.execute("select current_user").fetchone()[0], person_in_session(connection))
                problem = None if got == ("integro_api", "") else f"sin papel vio {got}"
        except PoolTimeout:
            return "espera", time.monotonic() - started
        return problem, time.monotonic() - started

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        outcomes = list(executor.map(one, range(ROUNDS)))
    waits = sum(1 for problem, _ in outcomes if problem == "espera")
    identity = [problem for problem, _ in outcomes if problem and problem != "espera"]
    seconds = sorted(s for _, s in outcomes)
    report.info(
        f"cada transacción tardó {sum(seconds) / len(seconds):.2f} s en promedio "
        f"(la mediana {seconds[len(seconds) // 2]:.2f} s, la más lenta {seconds[-1]:.2f} s); "
        f"sin lugar en el grupo a tiempo: {waits}"
    )
    report.compare(f"{ROUNDS} transacciones seguidas, desde {THREADS} hilos, nunca heredan la identidad de otra", [], identity[:5])
    report.compare("ninguna transacción se quedó sin conexión a tiempo", 0, waits)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--env", default="backend/.env.neon", help="archivo de variables (por defecto backend/.env.neon)")
    arguments = parser.parse_args()
    env_file = (REPO / arguments.env) if not Path(arguments.env).is_absolute() else Path(arguments.env)
    if not env_file.exists():
        print(f"No existe {env_file}. Es el archivo con los datos de conexión; git lo ignora.")
        return 2
    try:
        settings = Settings(_env_file=env_file)
    except Exception as error:  # el mensaje de pydantic trae los valores: solo se dicen los nombres
        names = sorted({str(detail["loc"][0]).upper() for detail in getattr(error, "errors", lambda: [])()})
        print("La configuración no es válida; revisa estas variables:", ", ".join(names) or "(ver el archivo)")
        return 2

    report = Report()
    if settings.database_host in ("127.0.0.1", "localhost"):
        targets = [("base local", settings)]
    else:
        kind = "agrupada" if "-pooler" in settings.database_host else "directa"
        targets = [(f"conexión {kind} ({settings.database_host.split('.')[0]})", settings)]
    direct = read_env_value(env_file, "DATABASE_HOST_DIRECT")
    if direct:
        targets.append((f"conexión directa ({direct.split('.')[0]})", settings.model_copy(update={"database_host": direct})))
    for label, target in targets:
        pool = create_pool(target)
        try:
            pool.open(wait=True, timeout=30)
            check(pool, label, report)
        except (psycopg.OperationalError, PoolTimeout) as error:
            print(f"\n== {label} ==\nNO se pudo conectar: {type(error).__name__}")
            report.results.append(False)
        finally:
            pool.close()

    total, good = len(report.results), sum(report.results)
    print(f"\n{good} de {total} coinciden")
    return 0 if good == total and total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
