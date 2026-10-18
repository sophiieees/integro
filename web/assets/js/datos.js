/* Íntegro · datos de muestra del prototipo
   -------------------------------------------------------------------
   TODO AQUÍ ES FICTICIO. Sirve para que el prototipo se vea con contenido.
   En producción estos datos salen de la API (GET /api/v1/search y
   GET /api/v1/properties/:id) y nunca de un archivo estático.
   Se carga como script (no con fetch) para que la página funcione al abrir
   index.html directamente desde el disco, sin servidor.
   Montos en pesos mexicanos (MXN), enteros. `total_2_noches` es un número
   de muestra: 2 × precio_noche + limpieza. La cotización real (temporadas,
   estancia mínima, fechas bloqueadas) NO existe todavía en este prototipo:
   es una de las funciones candidatas del Assignment 2 (ver PROMPT_LOG.md).
*/
window.INTEGRO_DATOS = {
  ciudadPorDefecto: "Ciudad de México", // Ciudad de lanzamiento por decidir (antes del 30 oct 2026)
  ciudades: ["Ciudad de México", "Guadalajara", "Monterrey", "Oaxaca de Juárez"],
  propiedades: [
    {
      id: 1,
      titulo: "Departamento con terraza en la Roma Norte",
      zona: "Roma Norte", ciudad: "Ciudad de México", tipo: "Departamento completo",
      capacidad: 4, recamaras: 2, camas: 2, banos: 1,
      precio_noche: 2400, limpieza: 450, total_2_noches: 5250,
      calificacion: 4.92, resenas: 38,
      anfitrion: { nombre: "Mariana", nivel: "verificado", responde: "en menos de 1 hora" },
      chapa: true,
      servicios: ["Wifi", "Cocina equipada", "Aire acondicionado", "Lavadora", "Terraza"],
      descripcion: "Departamento de dos recámaras en un edificio de 1950 remodelado. Terraza privada con vista a los árboles de la calle Colima. A tres cuadras del Metrobús Álvaro Obregón.",
      reglas: ["Llegada a partir de las 15:00", "Salida antes de las 11:00", "No se permiten fiestas", "No fumar en interiores"],
      cancelacion: "Moderada",
      tono: "roma"
    },
    {
      id: 2,
      titulo: "Loft luminoso en la Condesa",
      zona: "Condesa", ciudad: "Ciudad de México", tipo: "Loft",
      capacidad: 2, recamaras: 1, camas: 1, banos: 1,
      precio_noche: 1850, limpieza: 350, total_2_noches: 4050,
      calificacion: 4.85, resenas: 21,
      anfitrion: { nombre: "Luis", nivel: "verificado", responde: "en menos de 2 horas" },
      chapa: true,
      servicios: ["Wifi", "Cocina", "Escritorio", "Elevador"],
      descripcion: "Loft de doble altura con ventanales al Parque España. Ideal para una persona que trabaja desde casa o una pareja de visita en la ciudad.",
      reglas: ["Llegada a partir de las 14:00", "Salida antes de las 12:00", "No fumar"],
      cancelacion: "Flexible",
      tono: "condesa"
    },
    {
      id: 3,
      titulo: "Casa con jardín en Coyoacán",
      zona: "Coyoacán", ciudad: "Ciudad de México", tipo: "Casa completa",
      capacidad: 6, recamaras: 3, camas: 4, banos: 2,
      precio_noche: 4200, limpieza: 700, total_2_noches: 9100,
      calificacion: 4.97, resenas: 54,
      anfitrion: { nombre: "Daniela", nivel: "verificado", responde: "en menos de 1 hora" },
      chapa: false,
      servicios: ["Wifi", "Cocina equipada", "Jardín", "Estacionamiento", "Lavadora y secadora"],
      descripcion: "Casa de una planta con jardín de 80 m² a diez minutos a pie del centro de Coyoacán. Tres recámaras, dos baños completos y estacionamiento para un auto.",
      reglas: ["Llegada a partir de las 15:00", "Salida antes de las 11:00", "No se permiten fiestas", "Mascotas con aviso previo"],
      cancelacion: "Estricta",
      tono: "coyoacan"
    },
    {
      id: 4,
      titulo: "Estudio junto al Parque México",
      zona: "Hipódromo", ciudad: "Ciudad de México", tipo: "Estudio",
      capacidad: 2, recamaras: 1, camas: 1, banos: 1,
      precio_noche: 1300, limpieza: 300, total_2_noches: 2900,
      calificacion: 4.8, resenas: 3,
      anfitrion: { nombre: "Andrés", nivel: "nuevo", responde: "en menos de 3 horas" },
      chapa: true,
      servicios: ["Wifi", "Cocineta", "Aire acondicionado"],
      descripcion: "Estudio recién remodelado a media cuadra del Parque México. Cama matrimonial, cocineta y baño completo.",
      reglas: ["Llegada a partir de las 15:00", "Salida antes de las 11:00", "No fumar"],
      cancelacion: "Flexible",
      tono: "hipodromo"
    },
    {
      id: 5,
      titulo: "Departamento en Providencia",
      zona: "Providencia", ciudad: "Guadalajara", tipo: "Departamento completo",
      capacidad: 4, recamaras: 2, camas: 2, banos: 2,
      precio_noche: 1900, limpieza: 400, total_2_noches: 4200,
      calificacion: 4.9, resenas: 17,
      anfitrion: { nombre: "Paola", nivel: "verificado", responde: "en menos de 1 hora" },
      chapa: true,
      servicios: ["Wifi", "Cocina equipada", "Alberca del edificio", "Estacionamiento"],
      descripcion: "Departamento en piso alto con vista a la Minerva. Dos recámaras, dos baños y acceso a la alberca del edificio.",
      reglas: ["Llegada a partir de las 15:00", "Salida antes de las 12:00", "No se permiten fiestas"],
      cancelacion: "Moderada",
      tono: "providencia"
    },
    {
      id: 6,
      titulo: "Casa en el Centro Histórico",
      zona: "Centro", ciudad: "Oaxaca de Juárez", tipo: "Casa completa",
      capacidad: 5, recamaras: 2, camas: 3, banos: 2,
      precio_noche: 2600, limpieza: 500, total_2_noches: 5700,
      calificacion: 4.95, resenas: 29,
      anfitrion: { nombre: "Jorge", nivel: "verificado", responde: "en menos de 2 horas" },
      chapa: false,
      servicios: ["Wifi", "Cocina equipada", "Patio", "Ventiladores"],
      descripcion: "Casa de adobe restaurada a cuatro cuadras del Zócalo, con patio central y dos recámaras alrededor.",
      reglas: ["Llegada a partir de las 14:00", "Salida antes de las 11:00", "No fumar en interiores"],
      cancelacion: "Moderada",
      tono: "oaxaca"
    },
    {
      id: 7,
      titulo: "Departamento en San Pedro Garza García",
      zona: "San Pedro", ciudad: "Monterrey", tipo: "Departamento completo",
      capacidad: 3, recamaras: 1, camas: 2, banos: 1,
      precio_noche: 2100, limpieza: 400, total_2_noches: 4600,
      calificacion: 4.7, resenas: 4,
      anfitrion: { nombre: "Fernanda", nivel: "nuevo", responde: "en menos de 2 horas" },
      chapa: true,
      servicios: ["Wifi", "Cocina", "Aire acondicionado", "Gimnasio del edificio"],
      descripcion: "Departamento en torre con seguridad las 24 horas, a cinco minutos de Calzada del Valle.",
      reglas: ["Llegada a partir de las 15:00", "Salida antes de las 11:00", "No se permiten fiestas"],
      cancelacion: "Moderada",
      tono: "sanpedro"
    }
  ]
};
