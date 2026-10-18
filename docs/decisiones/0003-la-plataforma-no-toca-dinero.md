# ADR 0003 · La plataforma no toca dinero ni documentos sensibles

**Estado:** aceptada (requerimientos y MVP técnico).

## Contexto
El modelo de negocio es membresía sin comisión: el huésped paga al anfitrión y la plataforma no custodia fondos. Custodiar tarjetas o identificaciones implicaría PCI DSS y un alcance de seguridad que tres personas no pueden sostener.

## Decisión
Las tarjetas viven tokenizadas en el procesador de pagos (cuentas conectadas: cada anfitrión tiene una subcuenta y el procesador deposita a su CLABE). Las identificaciones y la biometría viven en el proveedor de verificación. La base propia guarda referencias y resultados; la CLABE y el RFC se guardan cifrados por campo.

## Consecuencias
- La plataforma solo cobra su propia suscripción; emite la orden de cobro de la reserva y recibe el webhook firmado.
- El fraude se concentra en la verificación del anfitrión y en la protección de la CLABE, que se vuelven el control de seguridad central del producto.
- Un fiscalista debe validar las obligaciones de ISR e IVA con pago directo antes de construir pagos.

## Fuente
Requerimientos, "Pagos al anfitrión"; MVP técnico, decisión 2 y "Pagos y cobros"; ciberseguridad, "Alcance, método y modelo de atacantes".
