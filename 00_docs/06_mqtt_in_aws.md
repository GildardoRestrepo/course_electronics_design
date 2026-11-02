---
type: referencia
---

# Práctica #6: Diseño Electrónico (MQTT en la nube: Mosquitto + Node-RED en AWS)

**Fecha:** 04/10/2026
**Estudiante:** Gildardo Estevan Restrepo Duque
**Guía:** *Práctica Servidor MQTT (AWS + Mosquitto)* — Prof. Fabio Guzmán, UPB

---

## Objetivo

Llevar a la nube la infraestructura MQTT que en la práctica 05 vivía en el PC: el broker
**Mosquitto** y el dashboard **Node-RED** pasan a una **máquina virtual en AWS (EC2)** con IP
pública. Con eso, los dispositivos y el dashboard ya no tienen que estar en la misma red:
cualquier cliente con Internet puede publicar y suscribirse **desde cualquier parte del mundo**.

Por el camino se trabajan tres temas que en la práctica 05 no existían:

1. **Administrar un servidor Linux remoto** por SSH y desde la línea de comandos.
2. **Seguridad de red en la nube**: el *Security Group* de AWS como firewall y la
   autenticación del broker, porque ahora está expuesto a Internet.
3. **Gestión de procesos y servicios** (`ps`, `kill`, `systemctl`, `journalctl`): un
   servidor tiene que seguir funcionando cuando cerramos la sesión SSH.

---

## Cambio de arquitectura

```
                         ┌───────────────── AWS EC2 (Ubuntu 26.04, t3.micro) ─────────────────┐
                         │                                                                     │
                         │   ┌──────────────┐   localhost:1883   ┌──────────────────────────┐  │
                         │   │  Node-RED    │◄──────────────────►│  Mosquitto (broker)      │  │
                         │   │  :1880 / ui  │                    │  :1883  usuario+clave    │  │
                         │   └──────▲───────┘                    └────────────▲─────────────┘  │
                         └──────────┼─────────────── IP pública ──────────────┼────────────────┘
                     Security Group │ 1880 (solo mi IP)          1883 (todos) │
                                    │                                         │   Internet
                    ┌───────────────┴──┐          ┌───────────────────────────┼───────────────────┐
                    │ Navegador        │          │                           │                   │
                    │ (editor + /ui)   │   ┌──────┴───────┐          ┌────────┴──────┐   ┌────────┴──────┐
                    └──────────────────┘   │ TTGO sensor  │          │ TTGO          │   │ MQTT Explorer │
                                           │ DHT11 + sw   │          │ observador    │   │ / terminal    │
                                           │ red A        │          │ red B         │   │ red C         │
                                           └──────────────┘          └───────────────┘   └───────────────┘
```

Es la misma idea de la práctica 05 —**todos son clientes por igual y el broker es el único
distinto**—, pero ahora cada cliente puede estar en una red diferente. La guía lo ilustra con
dos TTGO en `192.168.1.10` y `192.168.1.15`: son IP **privadas**, de redes que no se ven entre
sí. Lo único que comparten es la IP pública del broker.

| Aspecto               | Práctica 05 (local)                  | Práctica 06 (AWS)                                   |
| --------------------- | ------------------------------------ | --------------------------------------------------- |
| Dónde corre el broker | PC de la casa (`192.168.1.6`)        | Instancia EC2 con IP pública                        |
| Alcance               | Solo la red local                    | Cualquier red con Internet                          |
| Firewall              | Firewall de Windows                  | **Security Group** de AWS                           |
| Autenticación         | Anónima (`allow_anonymous true`)     | **Usuario y contraseña** (`password_file`)          |
| Node-RED → broker     | Por la red local                     | `localhost` (misma máquina)                         |
| Ciclo de vida         | Se cierra con el PC                  | **Servicios `systemd`** que arrancan solos          |
| Clientes ESP32        | Uno                                  | Dos: **sensor** y **observador**                    |
| Administración        | Interfaz gráfica de Windows          | **SSH + línea de comandos** de Linux                |

---

## Componentes

| Componente     | Detalle                                                              |
| -------------- | -------------------------------------------------------------------- |
| Placa 1        | ESP32 **TTGO T-Display** — firmware `sensor`                         |
| Sensor         | **DHT11**, datos en GPIO 25                                          |
| Entrada `sw`   | Botón derecho de la placa, GPIO 35 (pull-up en placa)                |
| Placa 2        | ESP32 TTGO T-Display — firmware `observador` (opcional, ver nota)    |
| Servidor       | AWS EC2 **t3.micro** (2 vCPU, 1 GiB RAM), **Ubuntu Server 26.04 LTS** |

> **Nota sobre la segunda placa:** si no hay un segundo TTGO, el papel de "cliente 2" lo
> cumple **MQTT Explorer** o `mosquitto_sub` en otro equipo, idealmente conectado por datos
> móviles para demostrar que está en otra red.

> **Adaptación respecto a la guía:** la guía usa un **MAX30100** (SpO₂ y ritmo cardiaco).
> Este repositorio conserva el **DHT11** de las prácticas anteriores; la arquitectura, los
> tópicos de control y el comportamiento son los mismos (ver
> [Esquema de tópicos](#esquema-de-tópicos)).

## Software

| Paquete              | Versión esperada  | Dónde       | Función                              |
| -------------------- | ----------------- | ----------- | ------------------------------------ |
| Ubuntu Server        | 26.04 LTS         | EC2         | Sistema operativo del servidor       |
| Eclipse Mosquitto    | 2.0.22 (apt)      | EC2         | Broker MQTT                          |
| Node.js              | 22.22 (apt)       | EC2         | Dependencia de Node-RED              |
| Node-RED             | 5.0.x (npm)       | EC2         | Dashboard (cliente MQTT)             |
| node-red-dashboard   | 3.6.6 (npm)       | EC2         | Paleta de widgets                    |
| PlatformIO           | 6.x               | PC          | Compilación y carga del firmware     |
| MQTT Explorer / Mosquitto clients | —    | PC / celular | Clientes externos de prueba        |

Las versiones de Mosquitto y Node.js son las de los repositorios oficiales de Ubuntu 26.04
([packages.ubuntu.com][ubuntu-pkgs]). Se confirman en la instancia con `mosquitto -h`,
`node -v` y `node-red --version`.

---

## Archivos de esta práctica

```
06_mqtt_in_aws/
├── esp32_mqtt_aws/                  # Proyecto PlatformIO con DOS entornos
│   ├── platformio.ini               #   [env:sensor] y [env:observador]
│   ├── include/
│   │   ├── secrets.h.example        #   WiFi, IP del broker, usuario y clave MQTT
│   │   ├── topicos.h                #   esquema de tópicos compartido
│   │   └── conexion.h
│   └── src/
│       ├── comun/conexion.cpp       #   WiFi + MQTT + LWT (lo usan ambos firmwares)
│       ├── sensor/main.cpp          #   cliente 1: DHT11, sw, led1/led2
│       └── observador/main.cpp      #   cliente 2: solo se suscribe
├── servidor/
│   ├── default.conf                 # /etc/mosquitto/conf.d/default.conf
│   └── node-red.service             # /etc/systemd/system/node-red.service
├── nodered/
│   └── flows_p06.json               # flujo del dashboard (importar en Node-RED)
└── 06_mqtt_in_aws_evidencias.md     # capturas de la práctica
```

---

## Procedimiento

### 1. Cuenta de AWS

Registro en <https://aws.amazon.com/es/console/> → *Crear cuenta gratuita*. La tarjeta solo
sirve para verificar la identidad.

Desde el 15 de julio de 2025 las cuentas nuevas entran al **plan gratuito**: reciben
**USD 100 en créditos** al crearla y pueden ganar hasta USD 100 más. El plan dura **6 meses**
o hasta agotar los créditos, y no cobra nada mientras no se pase a un plan de pago
([AWS Free Tier][aws-free]).

> 💡 Aun así conviene detener la instancia cuando no se use (`Instance state → Stop`): así no
> consume horas de cómputo de los créditos.

### 2. Lanzar la instancia EC2

Consola → **EC2** → **Launch instance**:

| Campo                | Valor                                              | Por qué                                                         |
| -------------------- | -------------------------------------------------- | --------------------------------------------------------------- |
| Name                 | `mqtt-practica06`                                  |                                                                 |
| AMI                  | **Ubuntu Server 26.04 LTS** (x86_64)               | Ver la nota sobre Node.js más abajo                             |
| Instance type        | **t3.micro**                                       | Elegible para el plan gratuito; 2 vCPU y 1 GiB de RAM           |
| Key pair             | *Create new key pair* → `miclave`, RSA, **`.pem`** | Es la "llave" del SSH; AWS la entrega **una sola vez**          |
| Network settings     | *Create security group* (reglas en el paso 4)      |                                                                 |
| Storage              | 8 GiB gp3 (por defecto)                            | Suficiente para Mosquitto + Node-RED                            |

Los tipos elegibles para el plan gratuito en cuentas creadas después del 15/07/2025 son
`t3.micro`, `t3.small`, `t4g.micro`, `t4g.small`, `c7i-flex.large` y `m7i-flex.large`
([AWS EC2 Free Tier][aws-ec2-free]). `t3.micro` tiene **2 vCPU y 1 GiB de RAM**
([AWS T3][aws-t3]): se comprueba más adelante con `nproc` y `free -m`.

> ⚠️ **¿Por qué Ubuntu 26.04 y no 24.04?** La guía instala Node.js con
> `sudo apt install nodejs npm`. **Node-RED 5.x exige Node.js 22.9 o superior**
> ([Node-RED, versiones soportadas][nr-node]; [Node-RED 5.0][nr-5]). Ubuntu 24.04 trae
> Node.js **18.19** por apt, que no sirve; Ubuntu 26.04 trae **22.22**, que sí
> ([packages.ubuntu.com][ubuntu-pkgs]). Con 26.04 los comandos de la guía funcionan tal cual.
> Si solo está disponible 24.04, hay que instalar Node.js con el script oficial de Node-RED
> (ver [Problemas posibles](#problemas-posibles)).

### 3. Conexión por SSH desde Windows

El archivo `miclave.pem` debe ser legible **solo** por el usuario; si no, OpenSSH lo rechaza
(`UNPROTECTED PRIVATE KEY FILE`). En PowerShell, en la carpeta donde está la llave (comandos
de la guía):

```powershell
icacls.exe miclave.pem /reset
icacls.exe miclave.pem /grant:r "$($env:username):(r)"
icacls.exe miclave.pem /inheritance:r
```

> En Linux/macOS el equivalente es `chmod 400 miclave.pem`.

Conexión (el usuario por defecto de las AMI de Ubuntu es `ubuntu`; la IP pública se copia
del detalle de la instancia en la consola):

```powershell
ssh -i .\miclave.pem ubuntu@<IP_PUBLICA>
```

Primeros comandos en la instancia:

```bash
sudo apt update && sudo apt upgrade -y   # actualizar el sistema
nproc                                    # número de procesadores -> 2
free -m                                  # memoria en MB -> ~1 GiB
df -H                                    # espacio en disco
```

> 📸 **Evidencia 1:** salida de `nproc`, `free -m` y `df -H`.

### 4. Security Group (firewall de AWS)

Por defecto el Security Group solo deja entrar SSH. Todo lo demás se descarta **antes de
llegar a la máquina**, por bien configurado que esté Mosquitto. Es el equivalente en la nube
de lo que en la práctica 05 hizo el firewall de Windows.

EC2 → instancia → pestaña **Security** → el Security Group → **Edit inbound rules**:

| Tipo        | Puerto | Origen                | Para qué                                                    |
| ----------- | ------ | --------------------- | ----------------------------------------------------------- |
| SSH         | 22     | **My IP**             | Administración                                              |
| Custom TCP  | 1883   | `0.0.0.0/0` (Anywhere) | MQTT: los ESP32 se conectan desde cualquier red            |
| Custom TCP  | 1880   | **My IP**             | Editor de Node-RED y dashboard (`/ui`)                      |

> ⚠️ **1880 restringido a "My IP".** El editor de Node-RED permite ejecutar código en el
> servidor (nodos `function`, `exec`). Expuesto a Internet sin protección, cualquiera podría
> tomar control de la instancia. Por eso se aplican dos barreras: esta regla y la
> autenticación del paso 6. Si la IP de la casa cambia, hay que actualizar la regla.

> 📸 **Evidencia 2:** reglas de entrada del Security Group.

### 5. Mosquitto

Instalación y verificación:

```bash
sudo apt install -y mosquitto mosquitto-clients
mosquitto -h | head -1                 # versión
sudo systemctl status mosquitto        # debe estar "active (running)"
```

**Usuarios.** La guía usa `allow_anonymous true`. En la red local de la práctica 05 era
razonable; aquí el puerto 1883 queda abierto a todo Internet, y cualquiera que encuentre la
IP podría leer y publicar en todos los tópicos. Por eso se crean usuarios (la guía ya lo
anticipa con `client.connect("arduinoClient", "testuser", "testpass")`):

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd gilbert   # -c crea el archivo (¡solo la 1.ª vez!)
sudo mosquitto_passwd /etc/mosquitto/passwd esp32         # los dos TTGO
sudo mosquitto_passwd /etc/mosquitto/passwd nodered       # Node-RED
sudo chown mosquitto:mosquitto /etc/mosquitto/passwd
sudo chmod 600 /etc/mosquitto/passwd
```

`mosquitto_passwd` guarda las claves con **hash**, no en texto plano
([Mosquitto, autenticación][mosq-auth]).

**Configuración** (contenido de [`servidor/default.conf`](../06_mqtt_in_aws/servidor/default.conf)):

```bash
sudo nano /etc/mosquitto/conf.d/default.conf
```

```conf
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd
```

- `listener 1883` abre el puerto en **todas** las interfaces. Sin él, Mosquitto 2.x solo
  acepta conexiones de la propia máquina.
- El archivo principal de Ubuntu (`/etc/mosquitto/mosquitto.conf`) ya incluye `conf.d/` y
  activa `persistence true`: **los mensajes retenidos sobreviven a un reinicio** del broker.

Aplicar y revisar:

```bash
sudo systemctl restart mosquitto
sudo systemctl status mosquitto
sudo tail /var/log/mosquitto/mosquitto.log
sudo ss -tlnp | grep 1883          # 0.0.0.0:1883 en LISTEN
# alternativa de la guía:  netstat -an | grep 1883   (requiere: sudo apt install net-tools)
```

### 6. Prueba de conexión desde fuera

Desde el **PC** (con los clientes de Mosquitto instalados en la práctica 05), en una
terminal se suscribe y en otra se publica:

```powershell
mosquitto_sub -h <IP_PUBLICA> -u gilbert -P <clave> -t "gilbert/#" -v
mosquitto_pub -h <IP_PUBLICA> -u gilbert -P <clave> -t gilbert/prueba -m "hola desde el PC"
```

**Pruebas negativas** (deben fallar):

```powershell
mosquitto_pub -h <IP_PUBLICA> -t gilbert/prueba -m x                 # sin usuario
mosquitto_pub -h <IP_PUBLICA> -u gilbert -P mala -t gilbert/prueba -m x
# -> Connection error: Connection Refused: not authorised.
```

**"Desde cualquier parte del mundo":** repetir la suscripción desde el **celular con datos
móviles** (MQTT Explorer u otra app MQTT). Son redes distintas y el mensaje llega igual.

> 📸 **Evidencia 3:** publicación desde el PC recibida en el celular (datos móviles) y
> conexión anónima rechazada.

### 7. Node-RED

Instalación con los comandos de la guía:

```bash
sudo apt install -y nodejs npm
node -v                                   # debe ser >= 22.9  (Ubuntu 26.04: v22.22.x)
sudo npm install -g --unsafe-perm node-red
```

Primer arranque **en primer plano** (crea `~/.node-red/` con `settings.js`):

```bash
node-red
# ... Server now running at http://127.0.0.1:1880/
# Ctrl+C para detenerlo
```

**Dashboard — corrección a la guía.** La guía indica `sudo npm i node-red-dashboard`. Ese
comando instala el paquete en la carpeta **donde se esté parado**, y Node-RED solo carga
nodos de su directorio de usuario. Hay que instalarlo **dentro de `~/.node-red`** y sin
`sudo`:

```bash
cd ~/.node-red
npm install node-red-dashboard
```

> `node-red-dashboard` (Dashboard 1) está **oficialmente deprecado desde junio de 2024**:
> funciona pero ya no recibe desarrollo ([FlowFuse][dash-deprecated]). Se usa porque es el
> que pide la guía y el de la práctica 05; su sucesor es `@flowfuse/node-red-dashboard`.

**Seguridad del editor y del dashboard.** Generar el hash de una contraseña:

```bash
node-red admin hash-pw
```

y en `~/.node-red/settings.js` descomentar/editar ([Node-RED, seguridad][nr-sec]):

```js
adminAuth: {                       // protege el EDITOR (:1880)
    type: "credentials",
    users: [{ username: "gilbert", password: "<HASH>", permissions: "*" }]
},
httpNodeAuth: { user: "gilbert", pass: "<HASH>" },   // protege el DASHBOARD (/ui)
credentialSecret: "<una-frase-larga-propia>",        // cifra flows_cred.json
```

El README de `node-red-dashboard` confirma que `httpNodeAuth` también protege el dashboard
([node-red-dashboard][dash-readme]).

**Importar el flujo:** abrir `http://<IP_PUBLICA>:1880` → menú ☰ → **Import** → pegar
[`nodered/flows_p06.json`](../06_mqtt_in_aws/nodered/flows_p06.json) → abrir el nodo de
configuración **Mosquitto (EC2 localhost)** → pestaña *Security* → escribir la clave del
usuario `nodered` → **Deploy**. El dashboard queda en `http://<IP_PUBLICA>:1880/ui`.

> El broker del flujo es **`localhost`**, no la IP pública: Node-RED y Mosquitto están en la
> misma máquina, así que ese tráfico nunca sale de la instancia ni depende del Security Group.

> 📸 **Evidencia 4:** editor de Node-RED con el flujo desplegado y dashboard `/ui` abierto
> desde el navegador del PC.

### 8. Gestión de procesos en Linux

Si se lanza `node-red` desde SSH y se cierra la sesión, **Node-RED muere con ella**: el
proceso es hijo de la terminal. Este paso recorre las formas de manejarlo, de la más frágil a
la correcta.

**a) Primer plano, segundo plano y trabajos**

```bash
node-red            # primer plano: la terminal queda ocupada.  Ctrl+C lo termina
node-red &          # segundo plano: devuelve la terminal
jobs                # trabajos de esta sesión
fg %1               # traerlo al primer plano;  Ctrl+Z lo suspende,  bg lo reanuda atrás
nohup node-red > ~/node-red.log 2>&1 &   # inmune al cierre de la sesión SSH
```

**b) Ver y terminar procesos**

```bash
ps aux | grep node-red     # todos los procesos, filtrados (columna 2 = PID)
pgrep -a node              # PID + comando, más directo
htop                       # monitor interactivo: CPU, RAM, procesos  (F9 = kill, q = salir)
kill <PID>                 # pide terminar (SIGTERM): el proceso cierra ordenadamente
kill -9 <PID>              # lo mata (SIGKILL): último recurso, no puede limpiar
sudo ss -tlnp              # qué proceso escucha en cada puerto (1880, 1883, 22)
```

**c) La forma correcta: un servicio de `systemd`**

`nohup` sobrevive al cierre de sesión pero **no a un reinicio**, y si Node-RED se cae nadie
lo levanta. Mosquitto no tiene ese problema porque apt lo instaló como servicio. Se hace lo
mismo con Node-RED usando [`servidor/node-red.service`](../06_mqtt_in_aws/servidor/node-red.service)
(corre como el usuario `ubuntu`, se reinicia si falla y arranca después de Mosquitto).
Primero hay que terminar cualquier `node-red` lanzado a mano (`kill <PID>`), o el puerto
1880 estará ocupado:

```bash
sudo nano /etc/systemd/system/node-red.service      # pegar el contenido del archivo
sudo systemctl daemon-reload
sudo systemctl enable --now node-red                # habilitar al arranque + iniciar ya
```

Administración de ambos servicios:

| Comando                                 | Qué hace                                       |
| --------------------------------------- | ---------------------------------------------- |
| `systemctl status node-red`             | Estado, PID, memoria y últimas líneas de log   |
| `sudo systemctl stop / start node-red`  | Detener / iniciar                              |
| `sudo systemctl restart mosquitto`      | Reiniciar (tras cambiar la configuración)      |
| `sudo systemctl enable / disable ...`   | Arrancar o no al encender la instancia         |
| `journalctl -u node-red -f`             | Log del servicio en vivo (Ctrl+C sale)         |
| `systemctl list-units --type=service`   | Todos los servicios del sistema                |

**Prueba definitiva:** `sudo reboot`, esperar un minuto, y sin volver a entrar por SSH el
dashboard y el broker deben estar funcionando.

> 📸 **Evidencia 5:** `systemctl status` de `mosquitto` y `node-red` en *active (running)* y
> `htop` mostrando ambos procesos.

### 9. Firmware

1. Abrir `06_mqtt_in_aws/esp32_mqtt_aws` en VS Code con PlatformIO.
2. Copiar `include/secrets.h.example` como `include/secrets.h` y rellenar: Wi-Fi, **IP pública**
   de la instancia, usuario `esp32` y su clave.
3. Cargar cada firmware en su placa:

```powershell
pio run -e sensor -t upload          # placa 1
pio run -e observador -t upload      # placa 2
pio device monitor                   # ver el log por serie
```

> La carga en el TTGO T-Display puede requerir el procedimiento de BOOT (GPIO 0) descrito en
> el README, incluido el ciclo de alimentación final.

Si no conecta, la pantalla y el monitor serie muestran la **causa probable**:

| Mensaje en pantalla        | Código `rc` | Revisar                                                      |
| -------------------------- | ----------- | ------------------------------------------------------------ |
| `sin TCP (IP/puerto/SG)`   | -2          | IP pública en `secrets.h`, regla 1883 del SG, red que bloquee el 1883 |
| `usuario/clave rechazados` | 4 / 5       | Usuario y clave en `secrets.h` vs. `mosquitto_passwd`        |
| `conexion perdida`         | -3          | Wi-Fi inestable                                              |

---

## Explicación técnica

### Esquema de tópicos

Se conserva la jerarquía `<usuario>/<dispositivo>/<señal>` de la práctica 05 y se adapta a
la arquitectura de la guía:

| Guía (MAX30100) | Este repositorio (DHT11)     | Sentido              | Retenido | QoS |
| --------------- | ---------------------------- | -------------------- | -------- | --- |
| `esp32/spo2`    | `gilbert/ttgo/temperatura`   | sensor → todos       | sí       | 0   |
| `esp32/ritmo`   | `gilbert/ttgo/humedad`       | sensor → todos       | sí       | 0   |
| `esp32/sw`      | `gilbert/ttgo/sw`            | sensor → todos       | sí       | 0   |
| `esp32/led1`    | `gilbert/ttgo/led1`          | dashboard → sensor   | **sí**   | 1   |
| `esp32/led2`    | `gilbert/ttgo/led2`          | dashboard → sensor   | **sí**   | 1   |
| —               | `gilbert/ttgo/estado`        | LWT del sensor       | sí       | 1   |
| —               | `gilbert/observador/estado`  | LWT del observador   | sí       | 1   |

Suscripciones de cada cliente, igual que en el diagrama de la guía:

| Cliente      | Publica                                  | Se suscribe a                     |
| ------------ | ---------------------------------------- | --------------------------------- |
| Sensor       | `temperatura`, `humedad`, `sw`, `estado` | `led1`, `led2`                    |
| Node-RED     | `led1`, `led2`                           | `temperatura`, `humedad`, `sw`, ambos `estado`, `led1`, `led2` |
| Observador   | su `estado`                              | `temperatura`, `sw`, `estado` del sensor |

### Autenticación: qué protege y qué no

`allow_anonymous false` + `password_file` impide que un desconocido se conecte. Pero en el
puerto **1883 el usuario y la clave viajan sin cifrar**: alguien que intercepte el tráfico
podría leerlos. Para la práctica es aceptable; en producción se usaría **TLS en el puerto
8883**, que requiere un certificado (y en la práctica, un dominio). Queda como mejora.

Cada tipo de cliente tiene su propio usuario (`esp32`, `nodered`, `gilbert`). Así, si una
clave se filtra, se cambia solo esa, y en el log de Mosquitto se ve **quién** se conectó
(`u'nodered'`).

### Órdenes retenidas: `led1` y `led2`

En la práctica 05 la orden del LED **no** era retenida. Si el ESP32 se reiniciaba, arrancaba
con el indicador apagado aunque el dashboard lo mostrara encendido: los dos lados quedaban
desincronizados.

Ahora el switch de Node-RED publica `led1`/`led2` **retenidos**. El broker guarda el **estado
deseado** y se lo entrega al ESP32 apenas se suscribe, tras cualquier reinicio o corte.

El dashboard también se suscribe a esos mismos tópicos y alimenta con ellos su propio
switch. Así, si se reinicia Node-RED, el switch recupera el estado real del broker en vez de
aparecer apagado. Esto no crea un bucle porque el switch tiene `passthru: false`: un mensaje
que **entra** al switch actualiza la interfaz pero **no** se reenvía a su salida.

### `sw`: estado por flanco

El botón publica `1` al **pulsar** y `0` al **soltar**, con 30 ms de antirrebote y retenido,
porque es un **estado**. Esto corrige una limitación documentada en la práctica 05, donde
mantener el botón presionado repetía el mensaje cada 400 ms.

Al reconectar, el firmware republica el valor actual de `sw` para que el retenido del broker
nunca quede desactualizado.

### LWT a través de Internet

El mecanismo es idéntico al de la práctica 05: al conectar, el cliente deja en custodia del
broker el mensaje `offline` en su tópico `estado`. Lo que cambia es el **contexto**: con el
dispositivo a kilómetros del dashboard, ya no hay forma de "mirar si está prendido". El LWT
es la única señal fiable de que un cliente remoto murió.

El retardo esperado es el mismo, unos 22 s (1,5 × keepalive de 15 s). El observador también
declara su LWT, así que el dashboard muestra el estado de **ambos** clientes.

### Un proyecto, dos firmwares

PlatformIO permite varios `[env]` en un mismo `platformio.ini`. Con `build_src_filter`, cada
entorno compila solo sus carpetas: `sensor` = `comun/` + `sensor/`, `observador` =
`comun/` + `observador/`. La conexión (Wi-Fi, MQTT, LWT, reintentos) está escrita **una sola
vez** en `src/comun/conexion.cpp`, y la librería del DHT solo se descarga para el entorno que
la usa.

### La IP pública no es fija

> "We release the public IP address when the instance is stopped, hibernated, or terminated.
> We assign a new public IP address when you start your stopped or hibernated instance."
> — [AWS, direccionamiento de instancias][aws-ip]

Cada *Stop/Start* de la instancia cambia la IP. Eso obliga a recompilar el firmware con la
nueva IP, a actualizar las reglas *My IP* si cambió la del PC, y a volver a abrir el dashboard
con otra URL. Hay dos soluciones:

- **Elastic IP**: IP fija asociada a la instancia. Es la solución que recomienda AWS.
- **Nombre DNS** (dominio propio o DNS dinámico) en `MQTT_BROKER`; el firmware ya acepta un
  nombre en lugar de una IP.

Sobre costos: el uso de IPv4 públicas se cobra a USD 0,005 por hora, con 750 h/mes incluidas
en la capa gratuita de EC2 ([AWS, IPv4 pública][aws-ipv4]). Con el plan gratuito, ese consumo
sale de los créditos.

---

## Dashboard de Node-RED

| Grupo                          | Widget                                | Tópico                        |
| ------------------------------ | ------------------------------------- | ----------------------------- |
| Sensor DHT11                   | 2 medidores                           | `temperatura`, `humedad`      |
| Estado de los clientes (LWT)   | 2 textos CONECTADO/DESCONECTADO       | `ttgo/estado`, `observador/estado` |
| Control (dashboard → ESP32)    | 2 interruptores sincronizados         | `led1`, `led2`                |
| Entrada del ESP32              | Texto PULSADO / libre                 | `sw`                          |
| Histórico                      | Gráfica de 10 minutos                 | ambas señales                 |

Detalle corregido respecto a la práctica 05: el color de los textos de estado se aplica con
`<font color="{{msg.color}}">` y no con `<span style="...">`. En la prueba con
`node-red-dashboard` 3.6.6, el atributo `style` se descartaba y el texto salía en negro.

---

## Verificación

### Hecha antes del montaje (sin AWS ni placas)

| Qué                          | Cómo                                                                 | Resultado |
| ---------------------------- | -------------------------------------------------------------------- | --------- |
| Configuración de Mosquitto   | `default.conf` + `password_file` en Mosquitto 2.0.18                 | ✅ Carga sin errores, escucha en 1883 |
| Rechazo de anónimos          | `mosquitto_pub` sin usuario y con clave errada                       | ✅ `Connection Refused: not authorised` |
| Retenidos                    | Publicar retenido y suscribirse después                              | ✅ Valor entregado al instante |
| LWT                          | Cliente con *will* terminado con `kill -9`                           | ✅ El broker publica `offline` |
| Flujo de Node-RED            | Despliegue en Node-RED 5.0.7 + dashboard 3.6.6, broker con usuario `nodered` | ✅ `Connected to broker`, `/ui` responde 200 |
| Switch → broker              | Clic en LED1 del dashboard (navegador automatizado)                  | ✅ `gilbert/ttgo/led1 1`, retenido |
| Firmware                     | Revisión de sintaxis y tipos de los tres `.cpp` con `g++`             | ✅ Sin errores |

> **Pendiente:** la compilación real con PlatformIO (`pio run -e sensor -e observador`) no
> pudo hacerse en el entorno de preparación porque no tenía acceso al registro de PlatformIO.
> Debe ejecutarse en el PC antes de cargar las placas.

### A completar durante la práctica

| Mecanismo                         | Evidencia esperada                                                   | Estado |
| --------------------------------- | -------------------------------------------------------------------- | ------ |
| Recursos de la instancia          | `nproc` = 2, `free -m` ≈ 1 GiB                                       | ⬜     |
| Broker accesible desde Internet   | `mosquitto_sub` desde el PC y desde el celular con datos móviles      | ⬜     |
| Seguridad                         | Conexión anónima rechazada desde fuera                                | ⬜     |
| Publicación (sensor → dashboard)  | Medidores con temperatura y humedad cada 5 s                          | ⬜     |
| Suscripción (dashboard → sensor)  | LED1/LED2 del dashboard → indicadores en la pantalla                  | ⬜     |
| Órdenes retenidas                 | Reiniciar el ESP32 → recupera LED1/LED2 sin tocar el dashboard        | ⬜     |
| Uno a muchos entre redes          | Pulsar `sw` → cambia en el dashboard **y** en el observador (otra red) | ⬜     |
| LWT remoto                        | Desconectar el sensor → DESCONECTADO en dashboard y observador (~22 s) | ⬜     |
| Servicios                         | `sudo reboot` → todo vuelve solo                                      | ⬜     |

---

## Problemas posibles

1. **`node -v` muestra v18** (AMI Ubuntu 24.04). Node-RED 5 no es compatible con esa versión.
   Hay dos salidas: lanzar la instancia con Ubuntu 26.04 o instalar Node.js con el script
   oficial de Node-RED para Debian/Ubuntu
   (`bash <(curl -sL https://github.com/node-red/linux-installers/releases/latest/download/install-update-nodered-deb)`).
   El script además crea su propio servicio `nodered.service`, así que en ese caso **no** se
   instala `servidor/node-red.service` ([Node-RED, instalación en Linux][nr-install]).
2. **`npm install` se queda colgado o termina en `Killed`.** Con 1 GiB de RAM, npm puede
   agotar la memoria. Solución: crear 1 GiB de *swap*.
   ```bash
   sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```
3. **El dashboard no aparece en la paleta.** `node-red-dashboard` se instaló fuera de
   `~/.node-red` (ver paso 7). Reinstalarlo ahí y reiniciar Node-RED.
4. **El ESP32 muestra `sin TCP` en la red de la universidad.** Algunas redes institucionales
   bloquean puertos de salida no web, como el 1883. Se comprueba compartiendo datos desde el
   celular: si así conecta, el bloqueo es de la red.
5. **Tras detener y arrancar la instancia nada conecta.** Cambió la IP pública (ver
   [La IP pública no es fija](#la-ip-pública-no-es-fija)).
6. **`ssh` responde `Permission denied (publickey)` o `UNPROTECTED PRIVATE KEY FILE`.** El
   usuario debe ser `ubuntu` (no `root` ni `ec2-user`), y hay que repetir los tres `icacls`
   del paso 3.

## Limitaciones conocidas

- **MQTT sin cifrar** (1883): las credenciales viajan en texto plano. Mejora: TLS en 8883.
- **Node-RED por HTTP**: la contraseña del editor también viaja sin cifrar. Lo mitiga la
  regla *My IP*; la solución completa sería HTTPS (proxy inverso con certificado).
- **IP pública dinámica** sin Elastic IP ni DNS.
- **Dashboard 1 deprecado**: funciona, pero un trabajo nuevo debería migrar a
  `@flowfuse/node-red-dashboard`.

---

## Resultado

Broker MQTT y un dashboard propios, alojados en la nube y protegidos con usuario y contraseña. Dos clientes ESP32 en redes distintas se comunican a través de ellos, y el estado real de cada uno es visible en todo momento gracias al LWT. Los servicios están administrados por `systemd` y se recuperan solos
tras un reinicio.


---

## Fuentes

- [AWS Free Tier][aws-free] — plan gratuito: créditos y duración.
- [AWS — EC2 Free Tier usage][aws-ec2-free] — tipos de instancia elegibles.
- [AWS — Instancias T3][aws-t3] — vCPU y memoria de `t3.micro`.
- [AWS — Instance addressing][aws-ip] — IP pública al detener/arrancar; Elastic IP.
- [AWS — 750 h de IPv4 pública en la capa gratuita][aws-ipv4] — costo de IPv4 pública.
- [Ubuntu — Ubuntu 26.04 LTS disponible en AWS][ubuntu-aws].
- [packages.ubuntu.com][ubuntu-pkgs] — versiones de `nodejs` y `mosquitto` por versión de Ubuntu.
- [Node-RED — Supported Node versions][nr-node] y [Node-RED 5.0 released][nr-5] — Node.js ≥ 22.9.
- [Node-RED — Securing Node-RED][nr-sec] — `adminAuth`, `httpNodeAuth`, `hash-pw`.
- [Node-RED — Instalación en Linux / Raspberry Pi][nr-install] — script oficial y `nodered.service`.
- [node-red-dashboard (README)][dash-readme] — instalación y protección con `httpNodeAuth`.
- [FlowFuse — Node-RED Dashboard formally deprecated][dash-deprecated].
- [Eclipse Mosquitto — Authentication methods][mosq-auth] — `password_file`, `mosquitto_passwd`.
- Guía de la práctica: *Práctica Servidor MQTT (AWS + Mosquitto)*, Prof. Fabio Guzmán, UPB.

---
## Enlaces
[[diseno_electronico_iot|Diseño Electrónico IoT]]
