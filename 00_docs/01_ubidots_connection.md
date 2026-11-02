---
type: referencia
---

# Práctica #1: Diseño Electrónico (UBIDOTS)

**Fecha:** 29/07/2026
**Estudiante:** Gildardo Estevan Restrepo Duque

---

## Objetivo

Preparar el entorno de trabajo con la placa **ESP32 TTGO T-Display**, verificar el
funcionamiento de la pantalla TFT y lograr la **conexión a Ubidots por MQTT** para
publicar las lecturas de temperatura y humedad de un sensor **DHT11**, mostrando el
último dato en la pantalla del dispositivo.

## Componentes

| Componente        | Detalle                                          |
| ----------------- | ------------------------------------------------ |
| Placa             | ESP32 TTGO T-Display (pantalla ST7789V 135×240)  |
| Sensor            | DHT11 — pin de datos en **GPIO 25**              |
| Backlight TFT     | GPIO 4                                            |
| Conectividad      | Wi-Fi + MQTT hacia Ubidots                        |

## Librerías

- `UbidotsEsp32Mqtt` — conexión MQTT a Ubidots.
- `TFT_eSPI` — control de la pantalla (configuración `Setup25_TTGO_T_Display`).
- `DHT sensor library` (Adafruit) — lectura del DHT11.

---

## Flujo de trabajo realizado

1. Seguimiento del video y preparación del entorno Arduino IDE (librerías).
2. Código para probar el funcionamiento de la pantalla.
3. Código para probar la conexión a Ubidots por MQTT (onda senoidal).
4. Soldar pines del ESP32.
5. Enviar lecturas del DHT11 a Ubidots e imprimir el último dato en pantalla
   (mezcla de los dos sketches anteriores).

## Sketches de esta práctica

- [`test_pantalla`](../01_ubidots_connection/test_pantalla/test_pantalla.ino) —
  prueba básica del TFT: valida que `TFT_eSPI` esté bien configurada y que el
  controlador ST7789V responda. Requiere activar en `User_Setup_Select.h` la línea
  `#include <User_Setups/Setup25_TTGO_T_Display.h>`.
- [`connection_ubidots_wavetest`](../01_ubidots_connection/connection_ubidots_wavetest/conexion_ubidots_wavetest.ino) —
  publica una **onda senoidal** de prueba a Ubidots. Sirve para confirmar que el token,
  el `DEVICE_LABEL` y la conexión MQTT funcionan antes de meter el sensor real.
- [`ubidots_dht11`](../01_ubidots_connection/ubidots_dht11/ubidots_dht11.ino) —
  sketch final de la práctica: lee el DHT11 y publica `temperatura` y `humedad`.

## Explicación técnica

- La publicación se controla con `millis()` cada **2 s** (`PUBLISH_FREQUENCY`), ya que
  el DHT11 solo admite una lectura por segundo; 2 s dan margen de seguridad.
- Cada ciclo se valida la lectura con `isnan()`: si el sensor falla devuelve `NaN` y
  **no se publican datos inválidos**, mostrando en su lugar un aviso de error en pantalla.
- El valor se pinta en **verde** si la publicación fue exitosa y en **rojo** si falló,
  como realimentación visual local del estado del envío.
- El callback MQTT está presente (lo exige la librería) aunque en esta práctica solo
  imprime lo recibido por el puerto serie.

## Resultado

El dispositivo se conecta al Wi-Fi y a Ubidots, envía temperatura y humedad de forma
periódica y muestra el último valor en la pantalla con indicación de estado por color.

---
## Enlaces
[[diseno_electronico_iot|Diseño Electrónico IoT]]
