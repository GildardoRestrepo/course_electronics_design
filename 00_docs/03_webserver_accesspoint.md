---
type: referencia
---

# Práctica #3: Diseño Electrónico (Access Point + WebServer)

**Fecha:** 19/08/2026
**Estudiante:** Gildardo Estevan Restrepo Duque

---

## Objetivo

Integrar todo lo anterior en un sistema completo de monitoreo con ESP32 + DHT11 +
Ubidots y añadir un **modo Access Point con servidor web** que permita **reconfigurar
la red Wi-Fi del dispositivo desde el navegador**, guardando las credenciales de forma
persistente en la memoria interna. En esta práctica se cambia de la librería de alto
nivel `UbidotsEsp32Mqtt` a un cliente **MQTT crudo con `PubSubClient`**.

## Componentes

| Componente    | Detalle                                           |
| ------------- | ------------------------------------------------- |
| Placa         | ESP32 TTGO T-Display (pantalla ST7789V 135×240)   |
| Sensor        | DHT11 — pin de datos en **GPIO 25**               |
| Backlight TFT | GPIO 4                                            |
| Conectividad  | Wi-Fi (STA + AP simultáneos) + MQTT hacia Ubidots |

## Librerías

- `WiFi`, `WebServer`, `Preferences` — incluidas en el core de ESP32.
- `PubSubClient` (Nick O'Leary) — cliente MQTT crudo.
- `TFT_eSPI` — control de la pantalla.
- `DHT sensor library` (Adafruit) — lectura del DHT11.

> En esta práctica **ya no se usa** `UbidotsEsp32Mqtt`: la conexión MQTT se arma
> manualmente contra `industrial.api.ubidots.com:1883`.

---

## Enfoque híbrido

El sketch combina las prácticas anteriores con el nuevo requerimiento:

- **Se conserva** la configuración física (DHT11 en GPIO 25, backlight en GPIO 4,
  `TFT_eSPI(135,240)`), el `DEVICE_LABEL = "gilbert_ttgo"` y el estilo de las prácticas
  01 y 02.
- **Se adopta** de la referencia el uso de `PubSubClient`, el modo Access Point con
  servidor web y el almacenamiento de credenciales con `Preferences`.

## Sketch de esta práctica

- [`ubidots_dht11_ap`](../03_webserver_accesspoint/ubidots_dht11_ap/ubidots_dht11_ap.ino) —
  sketch completo de la práctica.

## Explicación técnica

### Publicación y suscripción MQTT (PubSubClient)

- **Publica** temperatura y humedad como JSON `{"temperatura":..,"humedad":..}` al
  tópico `/v1.6/devices/gilbert_ttgo` cada **5 s**.
- **Se suscribe** a `/v1.6/devices/gilbert_ttgo/sw1/lv` y `.../sw2/lv`. El payload `/lv`
  llega como texto plano y se convierte con `toInt()`.
- En Ubidots el **usuario MQTT es el token** y la contraseña va vacía. El `clientId` se
  genera a partir de la MAC (`ESP.getEfuseMac()`) para que sea único.

### Control visual con los switches

En pantalla se dibuja un **círculo** cuyo color depende del estado de `sw1`/`sw2`:

| sw1 | sw2 | Color |
| --- | --- | ----- |
| 1   | 1   | Verde |
| 1   | 0   | Rojo  |
| 0   | 1   | Azul  |
| 0   | 0   | Gris  |

### Modo Access Point + servidor web

- `WiFi.mode(WIFI_AP_STA)` permite ser **cliente del router y punto de acceso a la vez**.
- El ESP32 crea la red **`ESP32-gilbert`** (clave `12345678`). Conectándose a ella y
  entrando a **`http://192.168.4.1`** se abre un portal para **cambiar el SSID/clave** de
  la red a la que se conectará el dispositivo.
- Las credenciales se guardan con **`Preferences` (NVS)**, por lo que **sobreviven al
  reinicio**. Existe también la opción de **restaurar** la red predeterminada.
- Tras guardar o restaurar, el dispositivo hace `ESP.restart()` para aplicar los cambios.

### Robustez del `loop()`

- Todo es **no bloqueante** con `millis()`: atiende el servidor web, reintenta el Wi-Fi
  cada 15 s, reintenta MQTT cada 5 s y publica/lee el sensor cada 5 s.
- Se valida el DHT11 con `isnan()`; si falla, se muestra pantalla de error y no se publica.

## Ajustes respecto al código de referencia

- **Layout adaptado a 240×135:** el ejemplo de referencia dibujaba texto en `y=140`, fuera
  de la pantalla del TTGO. Se reubicaron el círculo `(205,40)` y las etiquetas SW1/SW2, y
  se añadió la **IP local** en pantalla para distinguir de un vistazo si el equipo está
  conectado al router o solo en modo AP.
- Se eliminó `FS.h` (no se utilizaba) y se compactó el HTML/CSS del portal.

## Seguridad

Las credenciales del sketch (`UBIDOTS_TOKEN`, Wi-Fi por defecto) están como
**marcadores** (`TU_TOKEN_AQUI`, etc.). Deben completarse **localmente** y nunca
subirse con valores reales al repositorio.

## Resultado

Sistema autónomo que mide y publica temperatura/humedad, responde a dos switches del
dashboard cambiando el color del indicador, y permite reconfigurar su red Wi-Fi desde el
navegador sin recompilar, conservando la configuración tras apagones o reinicios.

---
## Enlaces
[[diseno_electronico_iot|Diseño Electrónico IoT]]
