# ADR 0010 · Sin blockchain en el MVP; anclaje de hashes en fase 2

**Estado:** aceptada (ciberseguridad, semana 2).

## Contexto
La pregunta por blockchain volverá en cada junta con inversionistas. Una blockchain resuelve un problema específico: varias partes que no confían entre sí necesitan un registro compartido que nadie pueda alterar. Si una sola empresa controla el registro, no agrega confianza; agrega costo, lentitud y la imposibilidad de borrar, que choca con los derechos ARCO.

## Decisión
Fuera del MVP: pagos en cripto o stablecoins, contratos inteligentes como depósito en garantía, identidad descentralizada, reseñas en cadena y tokenización de propiedades. En fase 2, un solo uso: anclaje de hashes de la bitácora (`audit_log`): cada registro guarda el hash del anterior; cada noche se publica la raíz de Merkle del día en una cadena pública o un servicio de sellado de tiempo. No salen datos personales, cuesta centavos y es compatible con borrar datos.

## Consecuencias
- En una disputa ("yo nunca cambié la CLABE") se puede demostrar que la bitácora de ese día no se tocó.
- Un día de trabajo cuando entre; no cambia la arquitectura.

## Fuente
Ciberseguridad, "Blockchain: dónde sí, dónde no".
