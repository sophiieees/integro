# ADR 0006 · Calendario por iCal con aviso inmediato contra la doble reserva

**Estado:** aceptada (MVP técnico, semana 1).

## Contexto
Cualquier anfitrión puede exportar de Airbnb, Booking o Vrbo un enlace iCal de su calendario e importar el nuestro. No necesita API ni acuerdo con la plataforma. Límites: solo pasa fechas bloqueadas u ocupadas (no precios, huéspedes ni reglas) y no es en tiempo real: Airbnb refresca cada pocas horas.

## Decisión
Sincronización iCal entrante y saliente como función de lanzamiento. Contra la doble reserva: bloqueo transaccional al crear la reserva (índice de exclusión en `calendar_blocks`), aviso inmediato al anfitrión al confirmar para que bloquee en las otras plataformas, y buffer de bloqueo configurable.

## Consecuencias
- El riesgo de doble reserva se registra como alto; la respuesta es operativa (aviso) y técnica (bloqueo), no una promesa de sincronía.
- `DTEND` en iCal es exclusivo; cualquier importador debe tratarlo así.

## Fuente
MVP técnico, pieza "Calendario y disponibilidad" y tabla de riesgos.
