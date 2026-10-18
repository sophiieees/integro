# ADR 0002 · Monolito modular, no microservicios

**Estado:** aceptada (MVP técnico, semana 1).

## Contexto
Tres personas construyen y operan el sistema. Los microservicios exigen operar redes, despliegues y observabilidad por servicio.

## Decisión
Un solo backend con módulos separados por dominio: cuentas, verificación, propiedades, búsqueda, reservas, pagos, mensajería, reportes, admin, IA y chapa. Una sola base de datos.

## Consecuencias
- Un despliegue, una base, un conjunto de alertas.
- Los módulos no se llaman entre sí por red; se separan por carpetas e interfaces para poder partirlos después.
- Kubernetes y multirregión quedan fuera (Won't have); el monolito en una región cubre la carga de la fase 1 con holgura.

## Fuente
MVP técnico (MoSCoW), decisión 3 y "Won't have".
