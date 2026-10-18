# ADR 0007 · Verificación de propiedad por capas

**Estado:** aceptada (MVP técnico, semana 1).

## Contexto
En México no hay registro nacional de la propiedad ni API unificada. Cada estado tiene su Registro Público de la Propiedad; la consulta es por folio real, con pago y a veces con entrega en días. No sirve para verificar en segundos durante el onboarding.

## Decisión
Cuatro capas, de las cuales tres son obligatorias y automatizables:
1. Documento (predial, escritura o recibo) con OCR, cruzado contra la identidad ya verificada; si no es dueño, contrato con cláusula de subarriendo o carta del propietario.
2. Geocodificación de la dirección y distancia al pin del anuncio; foto con código para anuncios nuevos.
3. Certificado de libertad de gravamen del RPP estatal solo por excepción (alto valor, disputas, sospecha): bandera en el panel y procedimiento manual.
4. Número de padrón local donde la ciudad lo exija.

Todo produce puntajes. Un puntaje bajo manda a revisión manual con respuesta en 24 horas; nunca rechaza solo.

## Consecuencias
- Onboarding rápido sin sacrificar la capa fuerte cuando hace falta.
- El cruce OCR puede fallar con abreviaturas, acentos o recibos a nombre del cónyuge; por eso puntaje y no rechazo.

## Fuente
MVP técnico, pieza "Propiedad en capas" y nota sobre el RPP; ciberseguridad, "Anfitrión falso".
