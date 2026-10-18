# Funciones candidatas para el Assignment 2

Material de apoyo para el Pre-Class Work de la Sesión 19, que pide llegar con 2 o 3 funciones candidatas. La elección y los tres campos de la especificación los escribe Sophia en `PROMPT_LOG.md`, sección 1. Este documento solo reúne lo que el proyecto ya dice de cada candidata y las preguntas que hay que responder antes de especificarla.

Regla del assignment: la función debe ser real. Usa datos, llama a una API o ejecuta lógica propia. No es una pantalla nueva.

## Resumen

| Candidata | Tipo de función | Datos reales de dónde | API externa | Cabe en el prototipo estático | Esfuerzo estimado |
|---|---|---|---|---|---|
| A. Cotización de una reserva | Lógica propia con datos | Tarifas y temporadas de la propiedad, fechas del usuario | Opcional: tipo de cambio MXN a USD | Sí | 1 a 2 días |
| B. Importar calendario iCal | Integración con datos reales | Archivo `.ics` exportado de Airbnb, Booking o Vrbo | No (formato estándar) | Sí, por archivo o texto pegado | 1 a 2 días |
| C. Detector de datos de contacto en mensajes | Lógica propia | Texto que escribe el usuario | No | Sí | Medio día a 1 día |
| D. Distancia entre dirección y pin del anuncio | Integración con API externa | Dirección escrita + coordenadas del pin | Sí: geocodificación (Nominatim o Google) | Sí, con llave o con servicio sin llave | 1 a 2 días |

---

## A. Cotización de una reserva con las reglas de la propiedad

**Qué resolvería en Íntegro.** "Precio total visible" es una promesa central del producto (mapa de etapas, etapa 1; sellos de la portada). Hoy la ficha muestra un total fijo de ejemplo. El MVP técnico lista la pieza "Precios: tarifa base, temporadas, estancia mínima, limpieza; cálculo del total de una reserva" con el endpoint `GET /properties/:id/quote`, y en el modelo de datos la describe como "una función pura sobre la tabla `rates`". La regla de seguridad asociada: el total se calcula siempre en el servidor; el cliente solo manda fechas y propiedad.

**De dónde saldrían los datos (preguntas a responder antes de especificar).**
- ¿Las tarifas salen de `web/assets/js/datos.js`? Hoy cada propiedad tiene `precio_noche` y `limpieza`. ¿Agregarás `estancia_minima` y temporadas (`desde`, `hasta`, `precio`)? ¿Con qué valores de muestra?
- ¿Las fechas salen de los campos Llegada y Salida de la caja de precio en `propiedad.html`? ¿Y el número de huéspedes?
- ¿Qué pasa con fechas bloqueadas? ¿Entran en esta función o quedan para la candidata B?

**Qué habría que probar.** Un caso con noches que cruzan el cambio de temporada (parte a tarifa base, parte a tarifa de temporada), uno que viole la estancia mínima (debe devolver error, no total), y uno con salida anterior a la llegada.

**Dónde la IA podría salirse de la especificación.** Agregar descuentos por semana que nadie pidió; calcular en el cliente con un redondeo distinto al de centavos enteros; inventar la regla de temporadas cuando la temporada empieza a mitad de la estancia; mostrar el precio en USD sin que la especificación lo pida.

**Extensión con API externa (S16).** Convertir el total a USD con un tipo de cambio real. El MVP técnico lo tiene como "Could have: soporte de dos monedas". Hay APIs de tipo de cambio sin llave; verificar en su documentación qué devuelven y con qué frecuencia se actualizan antes de citarlas en la especificación.

---

## B. Importar el calendario iCal de otra plataforma

**Qué resolvería en Íntegro.** Los requerimientos piden "bloqueo de fechas y sincronización iCal con Airbnb, Booking y Vrbo" como función de lanzamiento. El MVP técnico lo marca "Must" (4 días) y aclara los límites: solo pasa fechas bloqueadas u ocupadas, no precios ni huéspedes, y no es en tiempo real. El riesgo técnico registrado es la doble reserva.

**De dónde saldrían los datos.**
- ¿Un archivo `.ics` que el usuario sube, o texto `.ics` que pega? Un enlace iCal directo a Airbnb no se puede leer desde el navegador (bloqueo CORS), así que sería archivo o texto en el prototipo, y URL en el backend.
- ¿Tienes un calendario real exportado de alguna plataforma para probar, o se usa un `.ics` de muestra? Si es de muestra, debe decirlo la bitácora.
- ¿Contra qué se comparan las fechas importadas? ¿Contra reservas de muestra en `datos.js` para detectar conflictos?

**Qué habría que probar.** Un `.ics` con dos eventos (`DTSTART`/`DTEND`) debe producir dos rangos bloqueados con las fechas correctas; un evento que se traslape con una reserva existente debe marcarse como conflicto.

**Dónde la IA podría salirse de la especificación.** Intentar leer la URL de Airbnb directamente; interpretar `DTEND` como inclusivo (en iCal es exclusivo); importar también el resumen del evento con nombre del huésped (dato personal que no debe entrar).

---

## C. Detector de datos de contacto en mensajes

**Qué resolvería en Íntegro.** El documento de ciberseguridad identifica el "pago fuera de la plataforma" como el fraude más común en Airbnb, con probabilidad alta, y propone como control: "mensajería que detecta CLABEs, teléfonos y enlaces antes de confirmar y los oculta o marca". Los requerimientos lo llaman "mensajería protegida" y dejan la decisión al equipo. El MVP técnico lo tiene en "Could have" con expresión regular, y LLM solo en casos dudosos.

**De dónde saldrían los datos.**
- El texto lo escribe el usuario en un campo de mensaje. ¿Dónde vive ese campo? Hoy la ficha no tiene hilo de mensajes; habría que agregar un cuadro de "Escribe al anfitrión".
- ¿Qué patrones cuentan? CLABE (18 dígitos), teléfono mexicano (10 dígitos, con o sin espacios o guiones), correo, enlace. ¿Qué se hace con cada uno: ocultar, marcar, bloquear el envío?
- ¿El estado "reserva confirmada" existe en el prototipo? Si no, ¿la función siempre actúa como si no estuviera confirmada?

**Qué habría que probar.** Un mensaje con una CLABE de 18 dígitos debe salir con la CLABE oculta y un aviso; un mensaje con un número de 10 dígitos que sea, por ejemplo, un código postal de 5 dígitos repetido, no debe marcarse (caso límite); un mensaje sin datos de contacto debe pasar intacto.

**Dónde la IA podría salirse de la especificación.** Mandar el mensaje a un modelo de IA cuando la especificación dice expresión regular; bloquear palabras en vez de patrones; guardar el mensaje en algún lado.

---

## D. Distancia entre la dirección declarada y el pin del anuncio

**Qué resolvería en Íntegro.** La capa 2 de la verificación de propiedad (MVP técnico, pieza "Propiedad en capas"): geocodificar la dirección y medir la distancia al pin del anuncio; el resultado es un puntaje que manda a revisión manual, nunca un rechazo automático. El modelo de datos lo guarda en `verifications.geocode_distance_m`.

**De dónde saldrían los datos.**
- La dirección la escribe el anfitrión en un campo. ¿Y las coordenadas del pin? Habría que agregar `lat` y `lng` a las propiedades de muestra o un campo donde se peguen.
- ¿Qué servicio geocodifica? Nominatim (OpenStreetMap) funciona sin llave pero con límites de uso y política de atribución; Google Geocoding necesita llave y la llave no puede vivir en el repositorio. Verificar la documentación del servicio elegido y citarla.

**Qué habría que probar.** Una dirección conocida frente a un pin a pocos metros debe dar una distancia pequeña (definir el umbral); la misma dirección frente a un pin en otra colonia debe dar cientos o miles de metros y la etiqueta "revisión manual".

**Dónde la IA podría salirse de la especificación.** Poner la llave de la API en el código; convertir la distancia en "aprobado o rechazado" en lugar de puntaje; usar un servicio distinto del especificado.

---

## Lo que no conviene como función del assignment (y por qué)

- **Descripción del anuncio con IA** (Must del MVP): necesita una llave de proveedor de modelos en un backend; en un prototipo estático la llave quedaría expuesta. Si se eligiera, exige una función serverless y guardar el system prompt en el repo (la tarea lo pide para la Sesión 23).
- **Cobro de la reserva o suscripción**: depende de elegir el procesador de pagos (decisión pendiente) y de webhooks firmados; no cabe en el plazo.
- **Scraping de Airbnb**: descartado para cualquier fase (ADR 0005).
