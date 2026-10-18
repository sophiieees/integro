# ADR 0004 · PWA antes que app nativa

**Estado:** aceptada (MVP técnico, semana 1).

## Contexto
Los requerimientos piden un sitio adaptado a celulares y dejan la app propia para una fase posterior. Publicar en tiendas cuesta tiempo, dinero y revisiones.

## Decisión
La fase 1 se cubre con una aplicación web progresiva (instalable, con caché de interfaz y últimas búsquedas). La app en React Native con Expo entra en la fase 2 sobre la misma API.

## Consecuencias
- Las fichas indexan en buscadores porque se renderizan en servidor.
- La apertura de la chapa por Bluetooth requiere app nativa o capacidades del navegador que hay que validar; es una dependencia de la prueba del SDK (30 de octubre).

## Fuente
Requerimientos, "Módulo del huésped"; MVP técnico, "Won't have".
