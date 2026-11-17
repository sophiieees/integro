---
name: pieza
description: Construye una pieza de Íntegro (backend o frontend) de principio a fin, en su propia rama, con pruebas y explicación, sin fusionar hasta que Sophia autorice. Úsala cuando Sophia escriba /pieza o pida construir, agregar o cambiar una función, un endpoint, una tabla o una pantalla.
---

# /pieza

Una pieza es una sola responsabilidad: una función, un endpoint, una tabla con su migración o una pantalla. Si lo pedido son varias, propón el orden y construye solo la primera.

## Antes de escribir código

1. `git fetch` y `git pull --rebase` sobre `main`. Crea la rama `tipo/descripcion-corta` (`funcion/`, `datos/`, `api/`, `web/`, `docs/`).
2. Escribe la especificación de la pieza en tres campos y confírmala con Sophia si alguno es vago:
   - **Qué hace:** la acción exacta.
   - **Qué datos necesita:** de dónde sale cada uno (campo existente, lo escribe el usuario, API externa, hay que agregarlo).
   - **Cómo se sabrá que funciona:** casos de prueba con entrada exacta y resultado esperado.
3. Si la especificación la dio Sophia, no la cambies. No supongas, a menos de que se te indique, siempre pregunta.

## Al construir

4. Lógica separada de la pantalla: funciones puras que se puedan probar sin navegador.
5. Si la pieza toca pagos, membresías, propiedades o reservas, escribe primero la tabla de estados y transiciones permitidas. El código solo implementa esa tabla.
6. Respeta las reglas de seguridad de `CLAUDE.md`. Si la pieza necesita un secreto, pide que Sophia lo cargue en el proveedor; nunca lo escribas.
7. Cada cosa que agregues fuera de la especificación se anota como **desviación** con su razón. No la escondas dentro del código.

## Pruebas

8. Un caso de prueba por cada caso de la especificación, más los límites: entradas vacías, fechas invertidas, valores en el borde y cada transición prohibida.
9. Corre las pruebas y copia la salida real. Si un caso no coincide, se reporta así; no se ajusta el caso para que pase.

## Al terminar

10. `git fetch` otra vez, commit con mensaje que diga la decisión, push de la rama. No fusiones.
11. Entrega a Sophia, en este orden:
    - fecha;
    - carpetas y archivos creados o modificados, y por qué;
    - desviaciones de la especificación, cada una con el campo en juego, para que decida aceptar, rechazar o revisar;
    - sugerencias y por qué;
    - líneas o secciones modificadas;
    - salida real de las pruebas;
    - qué falta para publicarla (fusionar, variables de entorno, probar en el deploy).
12. Cuando Sophia decida, aplica sus decisiones en commits separados y ejecuta `/bitacora`.
