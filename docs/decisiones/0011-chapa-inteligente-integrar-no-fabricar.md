# ADR 0011 · Chapa inteligente: integrar, no fabricar

**Estado:** aceptada como recomendación del documento de chapa (13 de octubre de 2026); proveedor por validar.

## Contexto
Cada propiedad de Íntegro usará una chapa inteligente: el huésped abre con su teléfono por Bluetooth desde la app, con llave digital válida solo en las fechas de la reserva y código numérico de respaldo. La apertura registrada confirma la llegada real y puede liberar el pago a anfitriones nuevos con certeza. Fabricar una chapa propia exige diseño de hardware, certificaciones, manufactura e inventario.

## Decisión
Integrar chapas existentes en la etapa 1. Candidata principal: TTLock (costo bajo, SDK para abrir desde la app propia); alternativa: igloohome (funciona sin internet, mayor calidad, más cara). Shakti prueba el SDK elegido antes del 30 de octubre e instala en dos o tres propiedades piloto antes del 13 de noviembre. Evaluar chapa propia cuando haya volumen.

## Consecuencias
- Entra un módulo `chapa` en el backend y tablas para llaves digitales y registro de aperturas (dato personal: va en el aviso de privacidad).
- Riesgo de dependencia del proveedor: usar un intermediario como Seam o mantener dos proveedores aprobados.
- Modelo de entrega: comodato con permanencia de 12 meses en planes Profesional en adelante; renta o compra en el plan Individual. La chapa no cobra comisión por reserva ni por apertura.

## Fuente
Chapa inteligente de Íntegro, "Opciones tecnológicas", "Modelo de negocio" y "Próximos pasos".
