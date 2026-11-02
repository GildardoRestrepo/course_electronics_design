---
type: referencia
---

# Práctica #4: Diseño Electrónico (Repositorio de entregables)

**Fecha:** 19/08/2026
**Estudiante:** Gildardo Estevan Restrepo Duque

---

## Objetivo

Consolidar las entregas del curso en un **repositorio público de Git** que sirva como
entregable único y verificable: reunir el código de las prácticas 01 a 03, definir una
estructura y unas convenciones que soporten las prácticas siguientes, y documentar cada
actividad en su propia bitácora.

A diferencia de las prácticas anteriores, esta no añade hardware ni firmware nuevo: el
resultado es la **infraestructura de trabajo** sobre la que se apoyan las demás.

## Herramientas

| Herramienta | Detalle                                                            |
| ----------- | ------------------------------------------------------------------ |
| Git         | Control de versiones local                                         |
| GitHub      | Repositorio remoto: `GildardoRestrepo/electronics_design_IoT_upb`  |
| Markdown    | README y bitácoras de `_docs/`                                     |
| Obsidian    | Edición de las bitácoras (de ahí el frontmatter y los enlaces `[[ ]]`) |

---

## Flujo de trabajo realizado

1. Inicialización del repositorio y creación del remoto en GitHub.
2. Recolección de los sketches de las prácticas 01, 02 y 03, cada uno en su carpeta.
3. Definición de la estructura por prácticas numeradas y de la convención de nombres.
4. Redacción del `.gitignore` (artefactos de compilación, credenciales, archivos del SO).
5. Revisión de los sketches para sustituir credenciales reales por marcadores.
6. Redacción de las bitácoras `_docs/01`, `_docs/02` y `_docs/03`.
7. Redacción del `README.md` como índice y guía de compilación.
8. Licenciamiento del repositorio bajo **MIT**.
9. Commit inicial `Repositorio de entregables: hasta la entrega 03`.

## Explicación técnica

### Estructura por prácticas

El repositorio se organiza en carpetas numeradas `NN_tema`, una por práctica, y dentro de
cada una **una subcarpeta por sketch**. Esto responde a una exigencia del Arduino IDE: el
archivo `.ino` debe llamarse igual que su carpeta contenedora, así que agrupar varios
sketches sueltos en una misma carpeta no es posible.

La numeración de las carpetas sigue la del curso, de modo que el orden alfabético coincide
con el cronológico y cada entrega es localizable por su número.

### Separación entre código y bitácora

El código vive en las carpetas de práctica y la documentación en `_docs/`, con un archivo
por práctica. La razón es que las bitácoras se editan en **Obsidian** como notas de clase:
llevan frontmatter con `tags: tipo/clase` y enlaces internos `[[ing_electronica|Ing. Electrónica]]` que las
integran a la bóveda de apuntes, mientras el `README.md` cumple la función distinta de ser
la portada del repositorio en GitHub.

El prefijo `_` en `_docs` mantiene la carpeta agrupada al inicio del listado, separada de
las carpetas de práctica.

### `.gitignore` y manejo de credenciales

El `.gitignore` cubre tres frentes:

- **Artefactos de compilación:** `build/`, `*.bin`, `*.elf`, `*.o`, y los directorios de
  PlatformIO (`.pio/`, `.pioenvs/`, `.piolibdeps/`), previendo su uso posterior.
- **Credenciales:** `secrets.h`, `credentials.h`, `arduino_secrets.h`, `*.local`.
- **Archivos del sistema operativo:** `Thumbs.db`, `.DS_Store`, `*~`.

Sobre las credenciales, en las prácticas 01–03 los sketches llevan **marcadores** en el
propio código (`TU_TOKEN_AQUI`, `TU_WIFI_AQUI`) que se completan localmente y no se
versionan. La razón de fondo es que un secreto publicado en un repositorio **queda en el
historial de Git aunque después se borre del archivo**: no basta con eliminarlo en un
commit posterior. Las entradas de `secrets.h` del `.gitignore` anticipan el esquema más
robusto —credenciales en un archivo aparte, nunca versionado— que se adopta a partir de
la práctica 05.

### Licencia

Se adopta la licencia **MIT** por ser permisiva y breve: permite reutilizar el código con
la única condición de conservar el aviso de copyright, lo que encaja con material de
carácter académico pensado para ser consultado y reutilizado.

## Resultado

Repositorio público, licenciado y documentado, con las tres primeras prácticas versionadas,
sin credenciales expuestas y con una estructura y unas convenciones que las entregas
posteriores solo tienen que continuar.

---
## Enlaces
[[diseno_electronico_iot|Diseño Electrónico IoT]]
