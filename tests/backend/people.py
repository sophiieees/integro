"""Personas de prueba para las pruebas que usan la base real.

Se crean siempre dentro de rollback_pool, así que desaparecen al terminar la
prueba. Los correos terminan en @prueba.invalid, un dominio que no existe.
"""

from uuid import UUID, uuid4

from app.database.transaction import system_transaction


def create_person(pool, first_name: str) -> UUID:
    """Crea una persona como el sistema: fila en users y su teléfono principal."""
    tag = uuid4().hex[:12]
    with system_transaction(pool) as connection:
        user_id = connection.execute(
            "insert into users (first_name, last_name, email, country, birth_date) "
            "values (%s, 'Prueba', %s, 'MX', date '1990-01-01') returning id",
            (first_name, f"{first_name.lower()}.{tag}@prueba.invalid"),
        ).fetchone()[0]
        connection.execute(
            "insert into user_phones (user_id, phone, is_primary) values (%s, %s, true)",
            (user_id, "+52" + str(int(tag, 16))[:10].rjust(10, "5")),
        )
    return user_id
