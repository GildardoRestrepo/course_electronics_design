---
type: referencia
---

# Práctica #5: Diseño Electrónico (MQTT local: Mosquitto + Node-RED)

**Fecha:** 06/09/2026
**Estudiante:** Gildardo Estevan Restrepo Duque

---

## Objetivo

Sustituir la plataforma en la nube de las prácticas anteriores por una infraestructura
MQTT **completamente local**: un broker **Mosquitto** propio, un dashboard construido en
**Node-RED** y el ESP32 como cliente, todos en la misma red. El propósito es dejar de
consumir una plataforma cerrada y pasar a **operar el protocolo directamente**.

Además se cambia el entorno de desarrollo: esta práctica abandona el Arduino IDE y usa
**VS Code con PlatformIO**.

---

## Cambio de arquitectura

En las prácticas 01–03, Ubidots era simultáneamente broker, dashboard y base de datos. Al
montar el sistema localmente esas funciones se separan en piezas independientes:

```
                    ┌──────────────────────────┐
                    │  Mosquitto (PC)          │  ← el SERVIDOR (broker)
                    │  192.168.1.6:1883        │     el único que no es cliente
                    └────────────┬─────────────┘
                       ┌─────────┼──────────┬──────────────┐
                       │         │          │              │
                  ┌────┴───┐ ┌───┴────┐ ┌───┴─────┐  ┌─────┴──────┐
                  │ ESP32  │ │Node-RED│ │  MQTT   │  │ terminal   │
                  │ TTGO   │ │dashboard│ │Explorer│  │ mosquitto_ │
                  └────────┘ └────────┘ └─────────┘  └────────────┘
                       ↑ todos son CLIENTES por igual
```

El punto central es que **el dashboard no es especial**: publica y se suscribe igual que el
ESP32, y podría estar en otra máquina, en otra ciudad o en otro país. El broker es el único
elemento con un papel distinto.

| Aspecto              | Prácticas 01–03 (Ubidots)              | Práctica 05 (local)                   |
| -------------------- | -------------------------------------- | ------------------------------------- |
| Broker               | `industrial.api.ubidots.com`           | Mosquitto en el PC                    |
| Dashboard            | Widgets de Ubidots                     | Node-RED (otro cliente MQTT)          |
| Esquema de tópicos   | Impuesto: `/v1.6/devices/<label>/<var>` | Diseñado en esta práctica            |
| Autenticación        | Token como usuario MQTT                | Anónima (red local)                   |
| Aviso de caída       | Lo resolvía el panel                   | **LWT** declarado por el dispositivo  |
| Último valor al abrir| Lo guardaba la plataforma              | **Mensajes retenidos**                |
| Entorno              | Arduino IDE (`.ino`)                   | VS Code + PlatformIO                  |

---

## Componentes

| Componente    | Detalle                                                 |
| ------------- | ------------------------------------------------------- |
| Placa         | ESP32 **TTGO T-Display** (pantalla ST7789V 135×240)     |
| Sensor        | **DHT11** (temperatura y humedad), pin de datos GPIO 25 |
| Backlight TFT | GPIO 4                                                  |
| Botón pánico  | GPIO 35 (botón de la placa, con pull-up integrado)      |
| Broker        | PC con Mosquitto en `192.168.1.6:1883`                  |

## Software

| Paquete            | Versión | Función                                  |
| ------------------ | ------- | ---------------------------------------- |
| Eclipse Mosquitto  | 2.1.2   | Broker MQTT                              |
| Node.js            | 24.19.0 | Dependencia de Node-RED                  |
| Node-RED           | 5.0.6   | Dashboard (cliente MQTT)                 |
| node-red-dashboard | 3.6.6   | Paleta de widgets                        |
| MQTT Explorer      | 0.3.5   | Depuración del árbol de tópicos          |
| PlatformIO Core    | 6.1.19  | Compilación y carga del firmware         |

Librerías del firmware (fijadas en `platformio.ini`): `PubSubClient`, `DHT sensor library`,
`Adafruit Unified Sensor` y `TFT_eSPI`.

---

## Flujo de trabajo realizado

1. Instalación del stack del lado PC: Node.js, Node-RED, la paleta `node-red-dashboard`,
   Mosquitto y MQTT Explorer.
2. Configuración del broker para aceptar conexiones de la red y apertura del puerto 1883
   en el firewall de Windows.
3. Verificación del broker con `mosquitto_pub` / `mosquitto_sub` antes de escribir firmware.
4. Creación del proyecto PlatformIO y desarrollo del firmware.
5. Carga en el ESP32 y comprobación de la conexión al broker.
6. Construcción del dashboard en Node-RED.
7. Demostración del reparto uno a muchos y del LWT.

---
## Proyecto de esta práctica

- [`esp32_mqtt_local`](../05_mqtt_local_nodered/esp32_mqtt_local) — proyecto PlatformIO
  completo: [`platformio.ini`](../05_mqtt_local_nodered/esp32_mqtt_local/platformio.ini),
  [`src/main.cpp`](../05_mqtt_local_nodered/esp32_mqtt_local/src/main.cpp) y
  [`include/secrets.h.example`](../05_mqtt_local_nodered/esp32_mqtt_local/include/secrets.h.example).

A diferencia de las prácticas anteriores **no es un sketch `.ino`**: PlatformIO usa
`src/main.cpp` con `#include <Arduino.h>` explícito y toda la configuración del proyecto
en `platformio.ini`.

---

## Explicación técnica

### Esquema de tópicos

Al desaparecer la ruta impuesta por Ubidots hay que diseñar la jerarquía. Se adoptó
`<usuario>/<dispositivo>/<señal>`, que permite suscribirse a todo un dispositivo con el
comodín `gilbert/ttgo/#`:

| Tópico                       | Sentido               | Retenido |
| ---------------------------- | --------------------- | -------- |
| `gilbert/ttgo/estado`        | dispositivo → todos   | sí       |
| `gilbert/ttgo/temperatura`   | dispositivo → todos   | sí       |
| `gilbert/ttgo/humedad`       | dispositivo → todos   | sí       |
| `gilbert/ttgo/control/led`   | dashboard → dispositivo | no     |
| `gilbert/alertas/panico`     | cualquiera ↔ todos    | no       |

Se usa **un tópico por variable** en lugar de un único JSON. Así cada tópico se conecta
directo a un widget de Node-RED sin nodos de parseo intermedios. La alternativa (un JSON
con todas las variables) ahorra ancho de banda y es más habitual en producción, pero exige
un nodo `json` y un `change` por cada widget.

Nótese que `alertas/panico` **cuelga fuera** de `gilbert/ttgo/`: no pertenece a ningún
dispositivo concreto, porque cualquiera puede publicarlo y todos lo escuchan.

---
### Mensajes retenidos (`retained`)

El broker guarda el último mensaje marcado como retenido en cada tópico y se lo entrega
**inmediatamente** a cualquier cliente que se suscriba después. Sin esto, un dashboard
recién abierto se quedaría en blanco hasta la siguiente publicación del sensor (hasta 5 s).

Se comprobó publicando un mensaje retenido y suscribiéndose **después**.

La alerta de pánico **no** es retenida, y es deliberado: una alerta se define como un evento puntual.

---
### Last Will and Testament (LWT)

Es el mecanismo más relevante de la práctica. El dispositivo declara **al conectarse** un
mensaje que deja en custodia del broker, y el broker lo publica solo si el cliente
desaparece sin despedirse:

```cpp
client.connect(clientId.c_str(), NULL, NULL,
               TOPIC_ESTADO,  // will topic
               1,             // will QoS
               true,          // will retained
               "offline");    // will message
```

Tras conectar, el dispositivo publica `online` retenido en ese mismo tópico.

**Verificación:** se desconectó el cable USB de golpe. 22 segundos después el testigo
registró:

```
2026-09-06T19:34:39-0500 ; gilbert/ttgo/estado ; online
2026-09-06T19:36:25-0500 ; gilbert/ttgo/estado ; offline
```

Ese `offline` **no lo envió el ESP32**, que estaba sin alimentación: lo publicó Mosquitto
ejecutando el testamento. El retardo de ~22 s no es un fallo, es el protocolo: el broker no
puede saber que el cliente murió hasta que incumple el *keepalive* (PubSubClient usa 15 s
por defecto, y Mosquitto declara muerto al cliente a 1,5× ese valor).

**Por qué importa:** con el dispositivo ya muerto, los medidores del dashboard seguían
mostrando 25.8 °C y 49 % — la última lectura, congelada, con aspecto perfectamente
saludable. Solo el campo alimentado por el LWT decía la verdad. Sin este mecanismo, un
sensor caído y un sensor midiendo son indistinguibles desde el dashboard.

### Configuración de `TFT_eSPI` por `build_flags`

En las prácticas 01–03 había que editar `User_Setup_Select.h` **dentro de la librería** y
descomentar `Setup25_TTGO_T_Display.h`. Eso hacía que el repositorio no fuera autosuficiente:
quien lo clonara tenía que repetir ese paso manual o no le compilaba.

Definiendo `USER_SETUP_LOADED=1` en `build_flags`, la librería ignora sus archivos de setup
y usa los flags del `platformio.ini`, que **sí están versionados**. El proyecto compila en
cualquier máquina recién clonado.

---
## Dashboard de Node-RED

Cinco grupos de widgets:

| Grupo                 | Widget                        | Tópico                     |
| --------------------- | ----------------------------- | -------------------------- |
| Sensor DHT11          | 2 medidores                   | `temperatura`, `humedad`   |
| Estado del dispositivo| Texto CONECTADO/DESCONECTADO  | `estado` (LWT)             |
| Control               | Interruptor                   | `control/led`              |
| Alertas               | Botón + último aviso + toast  | `alertas/panico`           |
| Histórico             | Gráfica de 10 minutos         | ambas señales              |

Detalle de implementación: los nodos `mqtt in` colocan la **ruta completa** del tópico en
`msg.topic`, y la gráfica usa `msg.topic` como nombre de serie. Sin un nodo `change` que lo
reescriba, la leyenda mostraría `gilbert/ttgo/temperatura` en vez de `Temperatura`.

Para reproducirlo: menú de Node-RED → **Import** → pegar el JSON siguiente → **Deploy**.
Hay que ajustar la IP del broker en el nodo de configuración `Mosquitto local`.

<details>
<summary><b>flows.json</b> — flujo completo del dashboard (desplegar para copiar e importar en Node-RED)</summary>

```json
[
  {
    "id": "flow_p5",
    "type": "tab",
    "label": "Practica 05 - MQTT local",
    "disabled": false,
    "info": "Dashboard de la practica 05 (Diseno Electronico).\n\nNode-RED es aqui un CLIENTE MQTT mas, igual que el ESP32: se conecta al broker Mosquitto local y publica/suscribe. No tiene ningun privilegio especial sobre el dispositivo."
  },
  {
    "id": "mqtt_temp",
    "type": "mqtt in",
    "z": "flow_p5",
    "name": "temperatura",
    "topic": "gilbert/ttgo/temperatura",
    "qos": "0",
    "datatype": "auto-detect",
    "broker": "broker_local",
    "nl": false,
    "rap": true,
    "rh": 0,
    "inputs": 0,
    "x": 150,
    "y": 80,
    "wires": [
      [
        "set_temp"
      ]
    ]
  },
  {
    "id": "set_temp",
    "type": "change",
    "z": "flow_p5",
    "name": "topic = Temperatura",
    "rules": [
      {
        "t": "set",
        "p": "topic",
        "pt": "msg",
        "to": "Temperatura",
        "tot": "str"
      }
    ],
    "action": "",
    "property": "",
    "from": "",
    "to": "",
    "reg": false,
    "x": 400,
    "y": 80,
    "wires": [
      [
        "gauge_temp",
        "chart_hist"
      ]
    ]
  },
  {
    "id": "gauge_temp",
    "type": "ui_gauge",
    "z": "flow_p5",
    "name": "",
    "group": "g_sensor",
    "order": 1,
    "width": 3,
    "height": 4,
    "gtype": "gage",
    "title": "Temperatura",
    "label": "C",
    "format": "{{value}}",
    "min": 0,
    "max": "50",
    "colors": [
      "#00b500",
      "#e6e600",
      "#ca3838"
    ],
    "seg1": "",
    "seg2": "",
    "className": "",
    "x": 660,
    "y": 60,
    "wires": []
  },
  {
    "id": "mqtt_hum",
    "type": "mqtt in",
    "z": "flow_p5",
    "name": "humedad",
    "topic": "gilbert/ttgo/humedad",
    "qos": "0",
    "datatype": "auto-detect",
    "broker": "broker_local",
    "nl": false,
    "rap": true,
    "rh": 0,
    "inputs": 0,
    "x": 140,
    "y": 160,
    "wires": [
      [
        "set_hum"
      ]
    ]
  },
  {
    "id": "set_hum",
    "type": "change",
    "z": "flow_p5",
    "name": "topic = Humedad",
    "rules": [
      {
        "t": "set",
        "p": "topic",
        "pt": "msg",
        "to": "Humedad",
        "tot": "str"
      }
    ],
    "action": "",
    "property": "",
    "from": "",
    "to": "",
    "reg": false,
    "x": 390,
    "y": 160,
    "wires": [
      [
        "gauge_hum",
        "chart_hist"
      ]
    ]
  },
  {
    "id": "gauge_hum",
    "type": "ui_gauge",
    "z": "flow_p5",
    "name": "",
    "group": "g_sensor",
    "order": 2,
    "width": 3,
    "height": 4,
    "gtype": "gage",
    "title": "Humedad",
    "label": "%",
    "format": "{{value}}",
    "min": 0,
    "max": "100",
    "colors": [
      "#e6e600",
      "#00b500",
      "#0080ff"
    ],
    "seg1": "",
    "seg2": "",
    "className": "",
    "x": 660,
    "y": 140,
    "wires": []
  },
  {
    "id": "chart_hist",
    "type": "ui_chart",
    "z": "flow_p5",
    "name": "historico",
    "group": "g_hist",
    "order": 1,
    "width": 12,
    "height": 6,
    "label": "Ultimos 10 minutos",
    "chartType": "line",
    "legend": "true",
    "xformat": "HH:mm:ss",
    "interpolate": "linear",
    "nodata": "Esperando datos del ESP32...",
    "dot": false,
    "ymin": "",
    "ymax": "",
    "removeOlder": "10",
    "removeOlderPoints": "",
    "removeOlderUnit": "60",
    "cutout": 0,
    "useOneColor": false,
    "useUTC": false,
    "colors": [
      "#ca3838",
      "#0080ff",
      "#ff7f0e",
      "#2ca02c",
      "#98df8a",
      "#d62728",
      "#ff9896",
      "#9467bd",
      "#c5b0d5"
    ],
    "outputs": 1,
    "useDifferentColor": false,
    "className": "",
    "x": 660,
    "y": 220,
    "wires": [
      []
    ]
  },
  {
    "id": "mqtt_estado",
    "type": "mqtt in",
    "z": "flow_p5",
    "name": "estado (LWT)",
    "topic": "gilbert/ttgo/estado",
    "qos": "0",
    "datatype": "utf8",
    "broker": "broker_local",
    "nl": false,
    "rap": true,
    "rh": 0,
    "inputs": 0,
    "x": 150,
    "y": 260,
    "wires": [
      [
        "fn_estado"
      ]
    ]
  },
  {
    "id": "fn_estado",
    "type": "function",
    "z": "flow_p5",
    "name": "formatear estado",
    "func": "// El broker publica 'offline' aqui por su cuenta si el ESP32 desaparece\n// sin despedirse (Last Will and Testament declarado por el dispositivo).\nvar vivo = (msg.payload === 'online');\nmsg.payload = vivo ? 'CONECTADO' : 'DESCONECTADO';\nmsg.color = vivo ? '#00b500' : '#ca3838';\nreturn msg;",
    "outputs": 1,
    "timeout": 0,
    "noerr": 0,
    "initialize": "",
    "finalize": "",
    "libs": [],
    "x": 400,
    "y": 260,
    "wires": [
      [
        "txt_estado"
      ]
    ]
  },
  {
    "id": "txt_estado",
    "type": "ui_text",
    "z": "flow_p5",
    "group": "g_estado",
    "order": 1,
    "width": 6,
    "height": 1,
    "name": "",
    "label": "Dispositivo",
    "format": "<span style=\"color:{{msg.color}}; font-weight:bold\">{{msg.payload}}</span>",
    "layout": "row-spread",
    "className": "",
    "x": 650,
    "y": 260,
    "wires": []
  },
  {
    "id": "sw_led",
    "type": "ui_switch",
    "z": "flow_p5",
    "name": "",
    "label": "Indicador en pantalla del ESP32",
    "tooltip": "Enciende el circulo de la pantalla TFT",
    "group": "g_control",
    "order": 1,
    "width": 6,
    "height": 1,
    "passthru": false,
    "decouple": "false",
    "topic": "gilbert/ttgo/control/led",
    "topicType": "str",
    "style": "",
    "onvalue": "1",
    "onvalueType": "str",
    "onicon": "",
    "oncolor": "",
    "offvalue": "0",
    "offvalueType": "str",
    "officon": "",
    "offcolor": "",
    "animate": false,
    "className": "",
    "x": 160,
    "y": 360,
    "wires": [
      [
        "mqtt_out_led"
      ]
    ]
  },
  {
    "id": "mqtt_out_led",
    "type": "mqtt out",
    "z": "flow_p5",
    "name": "control/led",
    "topic": "gilbert/ttgo/control/led",
    "qos": "0",
    "retain": "false",
    "respTopic": "",
    "contentType": "",
    "userProps": "",
    "correl": "",
    "expiry": "",
    "broker": "broker_local",
    "x": 440,
    "y": 360,
    "wires": []
  },
  {
    "id": "btn_panico",
    "type": "ui_button",
    "z": "flow_p5",
    "name": "",
    "group": "g_alertas",
    "order": 1,
    "width": 6,
    "height": 2,
    "passthru": false,
    "label": "BOTON DE PANICO",
    "tooltip": "Publica en gilbert/alertas/panico",
    "color": "#ffffff",
    "bgcolor": "#c62828",
    "className": "",
    "icon": "warning",
    "payload": "Node-RED",
    "payloadType": "str",
    "topic": "gilbert/alertas/panico",
    "topicType": "str",
    "x": 160,
    "y": 440,
    "wires": [
      [
        "mqtt_out_panico"
      ]
    ]
  },
  {
    "id": "mqtt_out_panico",
    "type": "mqtt out",
    "z": "flow_p5",
    "name": "alertas/panico",
    "topic": "gilbert/alertas/panico",
    "qos": "0",
    "retain": "false",
    "respTopic": "",
    "contentType": "",
    "userProps": "",
    "correl": "",
    "expiry": "",
    "broker": "broker_local",
    "x": 450,
    "y": 440,
    "wires": []
  },
  {
    "id": "mqtt_in_panico",
    "type": "mqtt in",
    "z": "flow_p5",
    "name": "alertas/panico",
    "topic": "gilbert/alertas/panico",
    "qos": "0",
    "datatype": "utf8",
    "broker": "broker_local",
    "nl": false,
    "rap": true,
    "rh": 0,
    "inputs": 0,
    "x": 150,
    "y": 540,
    "wires": [
      [
        "fn_alerta"
      ]
    ]
  },
  {
    "id": "fn_alerta",
    "type": "function",
    "z": "flow_p5",
    "name": "formatear alerta",
    "func": "// Este mensaje llega venga de donde venga: del boton del dashboard, del\n// boton fisico del ESP32 o de una terminal con mosquitto_pub. El broker\n// entrega la MISMA copia a todos los suscriptores: eso es el uno a muchos.\nvar origen = msg.payload || 'desconocido';\nvar hora = new Date().toLocaleTimeString('es-CO');\nmsg.payload = 'ALERTA recibida de ' + origen + ' a las ' + hora;\nreturn msg;",
    "outputs": 1,
    "timeout": 0,
    "noerr": 0,
    "initialize": "",
    "finalize": "",
    "libs": [],
    "x": 400,
    "y": 540,
    "wires": [
      [
        "toast_panico",
        "txt_panico"
      ]
    ]
  },
  {
    "id": "toast_panico",
    "type": "ui_toast",
    "z": "flow_p5",
    "position": "top right",
    "displayTime": "5",
    "highlight": "#c62828",
    "sendall": true,
    "outputs": 0,
    "ok": "OK",
    "cancel": "",
    "raw": false,
    "className": "",
    "topic": "",
    "name": "aviso emergente",
    "x": 660,
    "y": 520,
    "wires": []
  },
  {
    "id": "txt_panico",
    "type": "ui_text",
    "z": "flow_p5",
    "group": "g_alertas",
    "order": 2,
    "width": 6,
    "height": 2,
    "name": "",
    "label": "Ultima alerta",
    "format": "{{msg.payload}}",
    "layout": "col-center",
    "className": "",
    "x": 650,
    "y": 580,
    "wires": []
  },
  {
    "id": "broker_local",
    "type": "mqtt-broker",
    "name": "Mosquitto local",
    "broker": "192.168.1.6",
    "port": "1883",
    "clientid": "node-red-practica05",
    "autoConnect": true,
    "usetls": false,
    "protocolVersion": "4",
    "keepalive": "60",
    "cleansession": true,
    "autoUnsubscribe": true,
    "birthTopic": "",
    "birthQos": "0",
    "birthPayload": "",
    "birthMsg": {},
    "closeTopic": "",
    "closeQos": "0",
    "closePayload": "",
    "closeMsg": {},
    "willTopic": "",
    "willQos": "0",
    "willPayload": "",
    "willMsg": {},
    "userProps": "",
    "sessionExpiry": ""
  },
  {
    "id": "tab_p5",
    "type": "ui_tab",
    "name": "Practica 05",
    "icon": "dashboard",
    "order": 1,
    "disabled": false,
    "hidden": false
  },
  {
    "id": "g_sensor",
    "type": "ui_group",
    "name": "Sensor DHT11",
    "tab": "tab_p5",
    "order": 1,
    "disp": true,
    "width": 6,
    "collapse": false,
    "className": ""
  },
  {
    "id": "g_estado",
    "type": "ui_group",
    "name": "Estado del dispositivo",
    "tab": "tab_p5",
    "order": 2,
    "disp": true,
    "width": 6,
    "collapse": false,
    "className": ""
  },
  {
    "id": "g_control",
    "type": "ui_group",
    "name": "Control (dashboard -> ESP32)",
    "tab": "tab_p5",
    "order": 3,
    "disp": true,
    "width": 6,
    "collapse": false,
    "className": ""
  },
  {
    "id": "g_alertas",
    "type": "ui_group",
    "name": "Alertas (uno a muchos)",
    "tab": "tab_p5",
    "order": 4,
    "disp": true,
    "width": 6,
    "collapse": false,
    "className": ""
  },
  {
    "id": "g_hist",
    "type": "ui_group",
    "name": "Historico",
    "tab": "tab_p5",
    "order": 5,
    "disp": true,
    "width": 12,
    "collapse": false,
    "className": ""
  }
]
```

</details>

---

## Verificación realizada

| Mecanismo        | Evidencia                                                        |
| ---------------- | ---------------------------------------------------------------- |
| Publicación      | Telemetría cada 5 s recibida en el broker                        |
| Suscripción      | Interruptor del dashboard → cambio del círculo en la pantalla    |
| `retained`       | Estado y valores entregados al instante de suscribirse           |
| Uno a muchos     | 1 publicación → 4 clientes, todos en el mismo segundo            |
| LWT              | Broker publica `offline` 22 s después del corte de alimentación  |
| Red y firewall   | `CONNECT` correcto desde `192.168.1.8` hacia `192.168.1.6`       |

La prueba del reparto uno a muchos se hizo pulsando el botón físico del ESP32 con dos
clientes de terminal suscritos:

```
terminal-1:  2026-09-06T19:34:01-0500 ; gilbert/alertas/panico ; ESP32-TTGO
terminal-2:  2026-09-06T19:34:01-0500 ; gilbert/alertas/panico ; ESP32-TTGO
dashboard:   "ALERTA recibida de ESP32-TTGO a las 7:34:01 p. m."
ESP32:       pantalla roja de alerta
```

Una sola publicación, cuatro destinatarios, el mismo instante. El emisor no sabe cuántos
son ni quiénes son: ese desacoplamiento es la razón de ser de MQTT.

Conviene notar que el ESP32 **no pinta la alerta al detectar la pulsación**: publica y
espera a recibirla como un suscriptor más. Si el broker estuviera caído, el botón no haría
nada ni siquiera en su propia pantalla.

---

## Problemas encontrados

1. **Mosquitto no aceptaba conexiones externas.** Configuración de fábrica limitada a
   localhost. Resuelto con el `listener` explícito (ver arriba).
2. **npm 11 bloquea los scripts de postinstalación.** El `postinstall` de
   `node-red-dashboard` quedó sin ejecutar y hubo que lanzarlo a mano. Es un cambio reciente
   de npm que invalida las instrucciones de tutoriales antiguos.
3. **La carga del firmware falla con `No serial data received`.** El auto-reset por DTR/RTS
   no funciona de forma fiable en esta placa. Hay que forzar el modo bootloader: desconectar
   el USB, mantener pulsado **BOOT (GPIO 0)**, reconectar sin soltar, y soltar tras dos
   segundos. **Importante:** tras grabar, el chip *sigue* en modo descarga y no ejecuta nada
   (pantalla apagada, sin salida por el puerto serie); hace falta **otro ciclo de
   alimentación** para que arranque el firmware nuevo.
4. **El DHT11 devuelve `NaN` en los primeros segundos.** Se observaron cuatro lecturas
   inválidas seguidas tras el arranque en frío. El código las descarta con `isnan()` y no
   publica datos falsos.

## Limitaciones conocidas

- **El antirrebote del botón repite mientras se mantiene pulsado.** Dispara cada 400 ms en
  vez de una sola vez por flanco de bajada; una pulsación algo larga publica dos alertas.
- **La IP del broker está fijada en `secrets.h`** y la asigna el router por DHCP: si cambia,
  el dispositivo deja de conectar. Lo correcto sería una IP reservada o mDNS.
- **Node-RED no está registrado como servicio**, así que no sobrevive a un reinicio del PC.
- **`allow_anonymous true`** implica que cualquiera en la red puede publicar y suscribirse.


---
## Resultado

Sistema IoT completo y autónomo, sin dependencia de ninguna plataforma externa: el ESP32
publica temperatura y humedad a un broker propio, recibe órdenes desde un dashboard que es
un cliente más, y participa en un canal de alertas donde cualquier cliente puede emitir y
todos reciben. El estado real del dispositivo es observable gracias al LWT, y el proyecto
completo compila desde cero en cualquier máquina a partir del repositorio.

---
## Enlaces
[[diseno_electronico_iot|Diseño Electrónico IoT]]
