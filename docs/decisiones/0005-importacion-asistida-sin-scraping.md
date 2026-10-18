# ADR 0005 · Importación asistida; sin scraping de Airbnb

**Estado:** aceptada (MVP técnico, semana 1).

## Contexto
Los requerimientos pedían "importación desde Airbnb: copia automática de fotos, descripción y calendario". Airbnb no tiene API pública, lleva años sin aceptar socios nuevos, y leer su sitio viola sus términos y se rompe con cada cambio.

## Decisión
El anfitrión pega el enlace de su anuncio y sube sus fotos; la plataforma prellena el formulario, registra el origen y un modelo con visión redacta título y descripción que el anfitrión edita antes de publicar. El scraping queda fuera de todas las fases. Si los anfitriones fundadores piden sincronizar precios, se evalúa un channel manager socio de Airbnb (Channex u otro), que cobra por propiedad.

## Consecuencias
- Publicar exige más del anfitrión que un "copiar de Airbnb"; la meta es menos de 15 minutos y se mide con los 50 fundadores.
- El calendario sí se sincroniza, por iCal (ADR 0006).

## Fuente
MVP técnico, pieza "Importación asistida", "Could have" y "Won't have".
