---
type: referencia
---

# Práctica #2: Diseño Electrónico (UBIDOTS)

**Fecha:** 05/08/2026
**Estudiante:** Gildardo Estevan Restrepo Duque

---

## Objetivo

Ampliar la práctica anterior para que el ESP32 no solo **publique** datos, sino que
también **reciba** información desde Ubidots (*downlink*): suscribirse a una variable
de control del dashboard y reaccionar a sus cambios en tiempo real, además de construir
los dashboards de visualización de las variables del DHT11.

## Componentes

Los mismos de la Práctica #1 (ESP32 TTGO T-Display, DHT11 en GPIO 25, backlight en
GPIO 4), añadiendo en el dashboard de Ubidots un **widget de control** (Slider o Switch)
asociado a la variable `control`.

## Librerías

- `UbidotsEsp32Mqtt`, `TFT_eSPI`, `DHT sensor library` (igual que la Práctica #1).

---

## Flujo de trabajo realizado

1. Seguimiento del video y preparación del entorno Arduino IDE (librerías).
2. Código para probar el funcionamiento de la pantalla.
3. Código para probar la conexión a Ubidots por MQTT (onda senoidal).
4. Soldar pines del ESP32.
5. Enviar lecturas del DHT11 a Ubidots e imprimir el último dato en pantalla.
6. Desarrollo de **dashboards** en Ubidots para la visualización de las variables del DHT11.
7. Código para probar la **recepción de *downlinks*** desde Ubidots.

## Sketches de esta práctica

- [`ubidots_sub`](../02_ubidots_subscription/ubidots_sub/ubidots_sub.ino) —
  suscripción mínima a la variable `control`; sirve para aislar y entender el mecanismo
  de *downlink* sin la lógica del sensor. Usa placeholders de credenciales.
- [`ubidots_dht11_downlink`](../02_ubidots_subscription/ubidots_dht11_downlink/ubidots_dht11_downlink.ino) —
  sketch final: publica `temperatura` y `humedad` **y** se suscribe a `control`,
  mostrando el valor recibido en pantalla.

## Explicación técnica

- La suscripción se hace con `ubidots.subscribeLastValue(DEVICE_LABEL, CONTROL_LABEL)`.
  Tras cada reconexión hay que **volver a suscribirse**, por eso se repite dentro del
  bloque de reconexión del `loop()`.
- El `callback` se dispara únicamente cuando `control` **cambia de valor** en Ubidots.
  El payload del tópico `/lv` llega como **texto plano** (no JSON), por lo que se
  reconstruye carácter a carácter y se convierte con `toFloat()`.
- La pantalla se organiza en **dos columnas** separadas por una línea vertical: a la
  izquierda el valor recibido de Ubidots y hace cuántos segundos llegó; a la derecha la
  temperatura y humedad del DHT11.
- El contador "Hace Xs" (usando `lastReceived`) permite ver de un vistazo si la
  comunicación descendente sigue viva.

## Resultado

El dispositivo publica el DHT11 y, simultáneamente, reacciona a los cambios del widget
de control del dashboard, reflejando el último valor recibido y su antigüedad en pantalla.

---
## Enlaces
[[diseno_electronico_iot|Diseño Electrónico IoT]]
