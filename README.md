# Astrolia Live

Sistema que atiende un live de TikTok de tarot y astrología: escucha el chat, arma la fila de turnos según regalos y preguntas, saca las cartas, redacta la lectura con IA y la muestra en un overlay para TikTok LIVE Studio.

Este documento recoge **qué hace cada parte, cómo se ejecuta y por qué se tomó cada decisión**. Las decisiones salen de las conversaciones de diseño y de revisar los logs de cinco lives de prueba (8, 9, 11 y 12 de octubre de 2026).

> **Estado (12 de octubre de 2026).** Toda la lógica está cubierta por 266 tests. Se ha probado conectado a lives ajenos en curso, siempre con el generador de prueba. **No se ha probado todavía:** la IA real (falta `ANTHROPIC_API_KEY`), la voz (no existe aún), el overlay dentro de LIVE Studio ni un live propio.

---

## Índice

1. [Cómo funciona, de punta a punta](#1-cómo-funciona-de-punta-a-punta)
2. [Puesta en marcha](#2-puesta-en-marcha)
3. [Estructura del proyecto](#3-estructura-del-proyecto)
4. [Reglas del live y por qué](#4-reglas-del-live-y-por-qué)
5. [Qué cuenta como pregunta](#5-qué-cuenta-como-pregunta)
6. [Fechas de nacimiento y signos](#6-fechas-de-nacimiento-y-signos)
7. [Temas delicados](#7-temas-delicados)
8. [La lectura con IA](#8-la-lectura-con-ia)
9. [Lo que dice la voz](#9-lo-que-dice-la-voz)
10. [Overlay](#10-overlay)
11. [Logs y página de revisión](#11-logs-y-página-de-revisión)
12. [Configuración](#12-configuración)
13. [Tests](#13-tests)
14. [Contenido provisional que debe reemplazar Caro](#14-contenido-provisional-que-debe-reemplazar-caro)
15. [Pendientes y limitaciones conocidas](#15-pendientes-y-limitaciones-conocidas)

---

## 1. Cómo funciona, de punta a punta

```
TikTok LIVE ──► ingest/tiktok_ingest.py ──► POST /eventos ──► backend (FastAPI)
                 (solo escucha)                                  │
                                                                 ├─ Cola      quién sigue y qué le falta
                                                                 ├─ Worker    un turno a la vez: avisa, tira cartas, pide la lectura
                                                                 ├─ Boost     ronda de likes
                                                                 └─ Bitácora  todo lo que pasó, por persona
                                                                 │
                         overlay (LIVE Studio)  ◄── GET /overlay/estado
                         revisión (privada)     ◄── GET /revision/datos
```

1. **La ingesta** se conecta al live con la librería TikTokLive y convierte cada evento (comentario, regalo, like, follow, entrada) a un formato único. Solo escucha: nunca envía mensajes al chat.
2. **El backend** recibe los eventos. Los comentarios pasan por la detección de pregunta, de fecha y de tema; los regalos crean o mejoran un turno.
3. **La cola** ordena los turnos: primero quien ganó el boost, luego por monedas, luego por llegada. Cada turno sabe si le falta la pregunta o la fecha.
4. **El worker** hace una cosa a la vez, como una sola voz: avisa lo que falta, y cuando un turno está listo saca las cartas, arma el prompt y pide la lectura.
5. **El overlay** consulta el estado cada 0,7 s y dibuja turnos, menú, cartas y el texto que se está diciendo.

Todo el estado vive en memoria: al reiniciar el backend se vacía la fila y se olvida quién usó su pregunta gratis. Lo único que persiste son los archivos de `logs/`.

---

## 2. Puesta en marcha

> **Para transmitir:** el paso a paso del día del live (arrancar, montar la escena en LIVE Studio, ensayo, controles y qué hacer si algo falla) está en [`README_LIVE.md`](README_LIVE.md).

Todos los comandos se corren desde la carpeta del proyecto (`astrolia-live/`), en una terminal de Ubuntu/WSL.

### 2.1 Instalación (una sola vez)

Requisitos: Python 3.12. En Ubuntu hace falta `build-essential` y `python3-dev` antes de instalar (por `pyswisseph`).

```bash
sudo apt install build-essential python3-dev     # solo si falta
python3 -m venv .venv                            # crea el entorno
.venv/bin/pip install -r requirements.txt        # instala las dependencias
cp .env.example .env                             # crea la configuración; luego se completa (ver abajo)
```

En `.env` hay que poner como mínimo:

| Variable | Qué va |
|---|---|
| `TIKTOK_USER` | La cuenta del live, sin arroba. Para probar, una cuenta ajena que esté transmitiendo. |
| `EULER_API_KEY` | Clave de EulerStream, que usa la conexión con TikTok. |
| `ANTHROPIC_API_KEY` | Clave de la consola de Anthropic. Sin ella las lecturas salen del generador de prueba. |

El resto de variables son opcionales y están en la sección 12.

### 2.2 Archivos que se descargan o generan (una sola vez)

```bash
.venv/bin/python -m tools.descargar_cartas     # baja las 78 imágenes originales a tarot/img/
.venv/bin/python -m tools.preparar_cartas      # las deja listas para el live en tarot/img_live/
.venv/bin/python -m tools.descargar_voz        # baja la voz local a voz/ (63 MB)
```

Los videos del avatar van en `resources/videos/` con estos nombres: `reposo.mp4`, `hablando.mp4`, `gato.mp4`, `gato_camina.mp4`, `barajar.mp4`, `rosa.mp4`, `rosquilla.mp4`. No hay que correr nada: el backend los toma de ahí al arrancar. Los prompts para generarlos están en `contextoVideos.md`.

Para escoger otra voz (opcional):

```bash
.venv/bin/python -m tools.muestras_voz               # baja las voces en español (unos 480 MB) y graba una muestra de cada una
.venv/bin/python -m tools.muestras_voz --instaladas  # solo las que ya están en voz/, sin descargar
```

Después se abre `voz/muestras/index.html` en el navegador, se escuchan y se copia en `.env` la línea que aparece debajo de la elegida.

### 2.3 Arrancar un live

Son **dos procesos, cada uno en su terminal, y hacen falta los dos**. Primero el backend, después la ingesta.

```bash
# Terminal 1: backend (fila, IA, voz y overlay)
.venv/bin/python -m uvicorn backend.app:app --port 8000
```

Está listo cuando aparece `worker iniciado` y, unos segundos después, `voz lista`.

```bash
# Terminal 2: ingesta (escucha el live de TIKTOK_USER y le pasa los eventos al backend)
.venv/bin/python -m ingest.tiktok_ingest
```

Está conectada cuando aparece `Conectado a @cuenta`. Si la cuenta no está en vivo dice `no está en vivo, reintento en 30 s` y sigue intentando sola.

**Sin la ingesta el backend no recibe a nadie:** no hay fila de turnos ni lecturas, y a los 3 minutos la voz deja de rellenar (ver 4.8.1).

Luego, en TikTok LIVE Studio se agrega una fuente de enlace (navegador) de 1080×1920 con la dirección del overlay:

| Para | URL |
|---|---|
| Overlay en LIVE Studio (fuente de enlace) | `http://127.0.0.1:8000/overlay/` |
| Ver el overlay en el navegador | `http://127.0.0.1:8000/overlay/` |
| Overlay con datos de muestra, recorriendo todos los estados (sin live) | `http://127.0.0.1:8000/overlay/?demo` |
| Overlay fijo en un estado de muestra (del 1 al 9) | `http://127.0.0.1:8000/overlay/?demo=4` |
| Revisión por persona (privada) | `http://127.0.0.1:8000/revision/` |
| Estado en crudo | `http://127.0.0.1:8000/estado` |

Si el navegador muestra el botón "Activar sonido", hay que darle clic una vez para que suene la voz (en LIVE Studio no aparece).

### 2.4 Detener y reiniciar

- **Detener:** `Ctrl+C` en cada terminal.
- **Reiniciar:** `Ctrl+C` y volver a correr el mismo comando. Hay que reiniciar el **backend** después de cualquier cambio en el código o en `.env`, y **recargar la página del overlay** después de un cambio en `overlay/`.
- **Antes de cada live** conviene reiniciar backend e ingesta, para que los logs queden separados y la fila empiece vacía.
- Con `--reload` el backend se reinicia solo al cambiar el código (`.venv/bin/python -m uvicorn backend.app:app --port 8000 --reload`). Sirve para desarrollar, no para un live, porque cada reinicio borra la fila.

### 2.5 Controles durante el live

Desde una tercera terminal, con el backend corriendo:

```bash
curl -X POST http://127.0.0.1:8000/control/pausa       # la voz se detiene (la fila se conserva)
curl -X POST http://127.0.0.1:8000/control/reanudar    # sigue
curl -X POST http://127.0.0.1:8000/control/boost       # abre ya una ronda de tap tap
curl -X POST "http://127.0.0.1:8000/cola/USUARIO/cerrar?estado=saltado"   # saca a alguien de la fila (USUARIO = su cuenta, sin arroba)
curl http://127.0.0.1:8000/estado                      # la fila y el estado, en crudo
```

### 2.6 Probar

```bash
.venv/bin/python -m pytest -q          # los tests (no llaman a TikTok ni a la IA)
.venv/bin/python -m tools.simular      # con el backend corriendo: inyecta cuatro preguntas con regalo de prueba
```

**Probar con un live ajeno:** poner en `TIKTOK_USER` una cuenta que esté transmitiendo y arrancar los dos procesos. Sirve para ver la fila y los filtros con tráfico real. Ese público no oye la voz de Astrolia, así que casi nadie responde cuando se le pide la fecha.

**Para ver el boost sin esperar 10 minutos:** el comando de `control/boost` de arriba, o `BOOST_CADA_MIN=3` en `.env`.

### 2.7 Después del live

Los logs de cada arranque quedan en `logs/` con fecha y hora (sección 11). Para repasar qué escribió cada persona y qué hizo el sistema: `http://127.0.0.1:8000/revision/` con el backend corriendo.

---

## 3. Estructura del proyecto

| Ruta | Qué contiene |
|---|---|
| `ingest/tiktok_ingest.py` | Conexión a TikTok, reintentos, reenvío de eventos si el backend está caído. |
| `ingest/normalize.py` | Formato único de evento y limpieza de texto (letras estiradas, emotes, relleno). |
| `backend/app.py` | API, arranque, lectura de `.env`, montaje del overlay y de la revisión. |
| `backend/cola.py` | La fila: turnos, esperas, pregunta gratis, pase del boost, qué es pregunta. |
| `backend/worker.py` | El ciclo de la voz: avisos, tirada, lectura, bienvenida, boost. |
| `backend/filtro.py` | Temas delicados por palabras clave y qué se hace con cada uno. |
| `backend/prompt.py` | Instrucciones y contexto que recibe la IA para cada lectura. |
| `backend/generador.py` | Llamada a Claude para la lectura. |
| `backend/tips.py` | Llamada a Claude para escribir tips nuevos por tandas. |
| `backend/clasificador.py` | Llamada a Claude para decidir mensajes dudosos (¿consulta o comentario?). |
| `backend/frases.py` | Todo lo que dice la voz fuera de las lecturas, con variantes. |
| `backend/boost.py` | Ronda de likes. |
| `backend/voz.py` | Voz local (Piper): troceo del texto, limpieza y síntesis. |
| `backend/overlay.py` | Lo que se le entrega al overlay, sin datos privados. |
| `backend/bitacora.py`, `backend/revision.py` | Registro por persona y su resumen. |
| `astro/cielo.py` | Posiciones planetarias con Swiss Ephemeris. |
| `astro/signos.py` | Lectura de fechas en el chat, signo, edad, de quién es cada fecha. |
| `tarot/mazo.json`, `tarot/mazo.py` | Las 78 cartas con sus claves. |
| `tarot/tirada.py` | Niveles de lectura según monedas y la tirada. |
| `overlay/` | HTML, CSS y JS del overlay. |
| `revision/index.html` | Página de revisión por persona. |
| `tools/simular.py` | Simulador de eventos. |
| `tools/descargar_cartas.py` | Baja las 78 cartas originales a `tarot/img/` (JPG). |
| `tools/descargar_voz.py` | Baja el modelo de voz a `voz/`. |
| `tools/muestras_voz.py` | Graba el mismo texto con cada voz disponible y deja `voz/muestras/index.html` para escucharlas y escoger. |
| `tools/preparar_cartas.py` | Genera las cartas del live en `tarot/img_live/` (WebP) a partir de las originales. |
| `tests/` | 266 tests. |
| `resources/` | Capturas de lives de referencia (no se suben al repo). |
| `logs/` | Un juego de archivos por live (no se suben al repo). |

---

## 4. Reglas del live y por qué

### 4.1 Niveles de lectura

El nivel sale del total de monedas del turno (`tarot/tirada.py`):

| Monedas | Nivel | Cartas | Extra |
|---|---|---|---|
| 0 | Sí o no | 1 | Pregunta gratis |
| 1 | Mensaje del oráculo | 1 | |
| 5 | Tres tiempos | 3 | |
| 10 | Tres tiempos con consejo | 4 | |
| 20 | Lectura con ritual | 4 | Ritual (pendiente) |
| 30 | Lectura doble | 4 | Responde también la segunda pregunta |
| 50 | Lectura profunda | 5 | Segunda pregunta |
| 99 | Lectura completa | 6 | Segunda pregunta |
| 199 | Lectura maestra | 6 | Segunda pregunta; solar, lunar y ascendente (pendiente) |

Los cortes del menú coinciden con regalos vistos en los logs (Rose 1, Finger Heart 5, Doughnut 30, Singing Mushroom 99, Confetti y Hand Heart 100, Dancing Hands 199); por eso los dos más altos son 99 y 199 y no 100 y 200. Los nombres en español que muestra el menú son provisionales: hay que confirmarlos contra el panel de regalos de la app. No hay cartas invertidas y una tirada nunca repite carta.

### 4.2 Orden de la fila

1. Quien ganó el boost de likes.
2. Más monedas primero.
3. A igual valor, quien llegó antes.

Un turno que todavía espera algo (la pregunta, la fecha) **no frena a los demás**: se salta y se lee al siguiente que esté listo.

### 4.3 Regalos

- **El regalo entra a la fila de inmediato**, con o sin pregunta. *Por qué:* así la persona ve su nombre en pantalla en cuanto regala.
- **Varios regalos de la misma persona se suman** mientras espera su turno.
- **Un regalo mientras se le está leyendo abre un turno nuevo** al terminar.
- **Quien regala sin preguntar tiene 3 minutos** para escribir; si no, recibe un mensaje general de las cartas. La voz se lo dice al agradecer el regalo ("Tienes 3 minutos para enviarme tu pregunta…"; si la voz venía ocupada, dice el tiempo que de verdad le queda) y en la lista de turnos corre una cuenta regresiva junto a su nombre ("escribe tu pregunta · 2:41"). *Por qué 3 minutos:* en los logs, la mitad de quienes regalan primero tardan más de un minuto en escribir.
- **Regalo pequeño sin pregunta (menos de 5 monedas): una carta corta, en grupo.** Vencido el plazo, se les lee junta una sola carta a quienes estén en esa situación (hasta 5 personas, 45 a 65 palabras; si es una sola, 30 a 45), nombrándolas a todas. Los regalos de 5 monedas o más conservan su lectura individual. *Por qué:* en el live del 13 de octubre 24 de 34 lecturas fueron mensajes individuales para regalos de 1 moneda sin pregunta, la espera típica llegó a 13 minutos y 11 personas que regalaron no alcanzaron a ser leídas.
- **Lo escrito antes de regalar vale como pregunta durante 5 minutos**, pero solo si tiene forma de pregunta, es una frase larga o toca un tema delicado. *Por qué:* antes se le pegaba cualquier comentario ("De acuerdo totalmente", "yo falto") y se leía como consulta.
- **Pregunta que llega tarde:** si se le leyó el mensaje general y escribe su pregunta en los 5 minutos siguientes, se le lee con el nivel de su regalo, una sola vez. *Por qué:* pagó y solo fue lenta escribiendo.
- **Preguntó, se le leyó gratis y luego regaló:** el regalo se lee con esa misma pregunta. *Por qué:* en los logs casi todos regalan entre 7 y 110 segundos después de preguntar, cuando la gratis ya salió.

### 4.4 Pregunta gratis

- **Una por persona por live**, de nivel "Sí o no".
- **Solo cuando no hay ningún regalo listo para leer.** Un regalo que aún espera su pregunta no la bloquea.
- **Máximo 3 gratis en la fila a la vez**; las demás esperan cupo y caducan a los 5 minutos. *Por qué:* sin tope, la voz se la pasaría pidiendo fechas.
- **Espera 15 segundos antes de leerse.** Si en ese margen llega un regalo, la pregunta sube al nivel del regalo y la gratis no se gasta.
- **Exige una pregunta clara** (ver sección 5).
- **Sin fecha de nacimiento no hay lectura gratis.** Si no la da en 90 segundos sale de la fila, sin gastar su turno, y solo vuelve a entrar cuando ya se conoce su fecha.
- **Si cae en tema prohibido, el turno se gasta.** Con regalo puede seguir preguntando.
- **Cuando alguien que ya la usó vuelve a preguntar sin regalo**, sale un cartel rojo en el overlay ("Agotó su pregunta gratis. ¡Envía un regalo para responderte!"). El cartel vuelve a salir cada vez que insiste (con 45 segundos de pausa por persona, 25 segundos en pantalla, hasta tres nombres); la voz se lo dice una sola vez por live. *Por qué:* antes esa persona insistía sin saber por qué no la leían, y es la invitación natural a regalar; la voz no se repite para no llenar el live de avisos.
- **"¿Hay preguntas gratis?"** no entra a la fila: la voz responde con el recordatorio de cómo pedirla (no más de una vez por minuto).
- El registro de quién ya la usó vive en memoria: se reinicia con el backend. Pasará a base de datos.

### 4.5 Pregunta ya respondida

Si alguien repite una pregunta que ya se le leyó, **no se vuelve a leer** ni se pega a un regalo futuro. Solo se relee si regala y la vuelve a escribir. *Por qué:* en un live de prueba a una persona se le leyó tres veces lo mismo.

### 4.6 Boost de likes

- **Quien gana una ronda queda fuera de las siguientes** de ese live: sus toques no cuentan y no aparece en la lista. *Por qué:* el 13 de octubre la misma persona ganó tres rondas.
- En voz y en pantalla se llama **tap tap**, nunca "likes" (la voz lo leía tal cual).
- Ronda de 60 segundos; gana quien más tap tap dé. En empate, quien llegó primero a la cifra. Se evaluó cambiarla por una meta colectiva de taps o por "500 taps = pregunta adicional", como en un live de referencia, y se decidió dejarla así.
- Arranca sola cada 10 minutos, o a pedido.
- **Quien gana pasa al primer turno**, por encima de cualquier regalo. Si regaló, conserva su nivel; si no, recibe "Sí o no". No gasta su pregunta gratis.
- Si ganó sin haber preguntado, el pase le dura 10 minutos.
- Los anuncios se dicen entre lecturas; los likes cuentan por su hora, no por cuándo se anuncia.

### 4.7 Bienvenida

- Saluda a quienes entran, **solo cuando no hay nadie por leer** y como máximo cada 3 minutos.
- Nombra hasta tres personas; si entraron más, agrega "y todos los que van llegando".
- Una vez por persona por live.

### 4.8 Ratos sin preguntas

La idea es que siempre haya algo sonando. Cuando pasan 3 segundos sin nada que decir y no hay nadie a quien leer, la voz llena el rato:

- **Un tip**, que es lo que sale casi siempre. Los escribe la IA sobre la marcha (`backend/tips.py`, Claude Haiku 5.5): una llamada trae 8, y cuando quedan 2 se pide otra tanda en segundo plano, así la voz nunca espera por ellos. A la IA se le pasan el cielo de hoy, seis cartas al azar y los últimos 24 tips dichos para que no los repita; se descartan los que salgan muy cortos, muy largos o toquen un tema delicado. Los 30 tips fijos de `TIPS` (`backend/frases.py`) sirven de ejemplo de tono y de respaldo: salen mientras llega la primera tanda, si no hay clave o si la IA falla.
- **La carta del momento**, como máximo cada 3 minutos: saca una carta para todos los conectados, la muestra en pantalla y la IA la comenta con el modelo rápido. Sin IA, usa una frase fija con las claves de la carta.
- **El cielo de hoy**, como máximo cada 10 minutos: signo y fase de la Luna, con un consejo según la fase, y un aviso si Mercurio, Venus o Marte están retrógrados.

Nunca se adelanta a un turno: solo corre cuando la fila no tiene a nadie listo. Si llega una pregunta mientras suena un tip, se lee al terminar esa frase. Se ajusta con `RELLENO_SEG` (0 lo apaga).

**Eventos astrológicos (preparado, sin usar).** `astro/eventos.py` consulta una API externa de eventos (eclipses, ingresos, lunas) y, si está configurada, la voz cuenta uno en los ratos sin preguntas, como máximo cada 15 minutos. Hoy no hace nada: se activa al poner `ASTRO_API_URL` (y `ASTRO_API_KEY`) en `.env`. Queda pendiente elegir la API y ajustar `_leer` a su formato, junto con la conexión a la base de datos.

### 4.8.1 Sin live

Sin live no hay a quién hablarle. La voz deja de rellenar (tips, carta del momento, cielo, boost, saludos y aviso de pregunta gratis) en dos casos:

- **La ingesta avisa** que el live terminó, que la cuenta no está en vivo o que se cayó la conexión (evento `conexion`). Vuelve sola cuando se reconecta.
- **Pasan 3 minutos sin recibir ningún evento** (`SIN_LIVE_MIN`; 0 lo apaga). Cubre que la ingesta no esté corriendo. *Por qué:* el 13 de octubre el backend corrió sin la ingesta y siguió hablando solo, gastando llamadas a la IA en cartas del momento.

Lo que ya estaba en la fila se termina de leer. El overlay muestra "Sin conexión con el live".

### 4.9 Menores de edad

- Si la fecha de nacimiento da menos de 18 años, no se lee. La voz dice que las lecturas son solo para mayores de edad, sin decir "eres menor". Se lo dice **una sola vez por live**; si sigue escribiendo, sus turnos se saltan en silencio (en el live del 12 de octubre la voz se lo repitió cuatro veces a la misma persona).
- Ese mensaje sale únicamente cuando la fecha lo confirma. Palabras como "colegio" o "mis papás" bloquean con el mensaje genérico, porque también las escribe un adulto.
- Una fecha que no se sabe de quién es nunca descarta a nadie.

---

## 5. Qué cuenta como pregunta

Hay tres niveles (`backend/cola.py`):

1. **Charla evidente — se descarta por reglas.** Saludos, agradecimientos, reacciones a la lectura ("sí, fue horrible el pasado"), comentarios sobre el live ("ya envié la rosa", "cuánto me falta", "mi pregunta te salió?", "no se escucha"), y respuestas a otra persona del chat.
2. **Pregunta segura — entra directo.** Tiene "?", "quiero saber", "saber si", "puedes decirme", "léeme".
3. **Dudoso — lo decide la IA** (si hay clave): afirmaciones sin signo de interrogación, como "mi esposo tiene otra" o "todavía me dice que me hablaba por humanidad". Claude Haiku 5.5 responde "pregunta" o "comentario". Si falla o tarda más de 6 segundos, deciden las reglas.

Sin IA, lo dudoso se trata así: vale como pregunta de quien ya regaló, pero para la gratis se exige una señal clara (interrogativos, futuros, "me ama", "volverá"…).

Decisiones puntuales:

- **Arroba inicial.** Mucha gente escribe su pregunta empezando con "@". Se le quita y se procesa normal; solo se ignora si lo que sigue es el nombre de alguien que está en el chat. *Por qué:* al tratarla como mención, cuatro personas que regalaron se quedaron sin su pregunta.
- **Nombre con fecha sin pregunta** ("Juan Pablo Yepes 16/09/2004"): se guarda el signo y la persona sigue debiendo su pregunta.
- **Segunda pregunta junto a la fecha** ("soy Ana 05/05/90 y en el trabajo, ¿me ascenderán?"): se guarda el signo y la pregunta queda como adicional.
- **La pregunta clara reemplaza a la charla:** si a quien regaló se le había pegado una frase sin forma de pregunta, la siguiente pregunta clara la sustituye.
- **"Te la envié al interno":** el sistema no lee mensajes privados; la voz le pide escribirla en el chat.
- **La cuenta anfitriona** no cuenta: lo que escribe la propia cuenta del live se ignora en la ingesta.
- **Temas delicados** se atienden siempre, diga lo que diga la IA.

---

## 6. Fechas de nacimiento y signos

`astro/signos.py` lee las fechas como llegan del chat:

- `05/05/90`, `5-5-1990`, `05.05.90`, `05 05 90`, `3_8_1988`, `30'06'08`, `17;04 89`
- de corrido: `08112007`, `050489`, `05 0489`
- con el año primero: `1998-04-09`, `1998/4/9`
- con mes: `3 de mayo`, `15 octubre 92`, `junio 11 90`, `19 feb 94`
- al estilo mes/día: `12/30/82`
- sin fecha: "soy aries", "mi signo es leo", o el glifo ♌

Reglas:

- **La fecha se pide para todas las preguntas**, también las gratis. Con regalo, si no la da en 90 segundos se lee sin signo.
- **En pantalla nunca sale la fecha**, solo el signo. *Por qué:* el overlay es público y queda grabado.
- **Respuesta a medias:** si solo da el año o solo el mes, la voz le dice qué falta y le da el plazo otra vez, una vez por cada caso.
- **De la pareja solo se guarda el signo**, nunca su fecha.
- **Día de cambio de signo:** se avisa a la IA que puede sentirse también del signo vecino.
- Un evento ("este sábado 10 de octubre") no es un cumpleaños.

### De quién es la fecha

**Si ya se le pidió su fecha** y responde repitiendo la pregunta con una fecha ("Mi ex Carlos volverá a buscarme 12 06 90"), esa fecha es la suya aunque venga después de nombrar a la otra persona. Sin haberla pedido, una fecha después de "mi ex…" sigue siendo de la otra persona.

Cuando el mensaje nombra a dos personas:

1. **El nombre de la cuenta lo aclara.** "…entre Carmen 12-10-93 y Fernando", escrito por la cuenta "Fernando Salazar": la fecha es de Carmen y a él se le pide la suya. Con dos fechas, cada una va con el nombre que tiene al lado.
2. **Se presentó aparte.** "soy Lesly, Simón Velásquez 28-2-96…": la fecha va con Simón. "…me llamo Ricardo 17;04 89": la suya es la que sigue a "me llamo".
3. **Ya había dado la suya.** Una fecha distinta que escriba después es de la otra persona; la suya no se cambia.
4. **No hay cómo saberlo.** La voz pregunta "¿es tuya o de la otra persona?" y espera 45 segundos sin frenar a los demás. Si no responde, se le lee igual y la IA recibe la duda: debe deducirlo o hablar de esa energía en la relación sin atribuírsela a nadie.

Los formatos de siempre ("Soy Ana 05/05/90 y Juan me quiere?") se toman como fecha propia sin preguntar.

---

## 7. Temas delicados

Dos filtros: uno por palabras clave antes de llamar a la IA (`backend/filtro.py`) y otro dentro del prompt.

El del prompt está escrito como **lista cerrada**: la IA solo puede marcar una pregunta como sensible si cae en uno de ocho temas con nombre (salud, crisis, violencia, brujería, embarazo, acusación, paternidad, menor), y debajo va la lista de lo que **siempre se lee** (pareja e infidelidad, lo que siente o hace otra persona, relaciones de terceros, familia, dinero, trabajo, visas y residencias, embarazo), con la regla "ante la duda, responde". *Por qué:* con la redacción anterior, el modelo rápido bloqueó dos preguntas válidas de pareja ("¿está interesado en otra mujer?", "¿es feliz con ella y se van a casar?"). La versión nueva acertó 8 de 8 preguntas de prueba contra la API.

| Tema | Qué se hace | Por qué |
|---|---|---|
| Crisis, autolesión | Mensaje fijo de cuidado | No lo responden las cartas; se orienta a buscar ayuda. |
| Salud | No se leen cartas. La voz da una orientación corta y cálida, por su nombre: quererse es cuidarse, ir al médico (3 variantes en `frases.py`). | No se adivina con la salud, pero tampoco se despacha a la persona con una frase seca. |
| Violencia, peligro | Mensaje fijo: seguridad primero | Igual. |
| Embarazo | **No se lee en el live.** La voz invita a escribir por mensaje directo ("esa pregunta pide una lectura detallada…"), con cualquier regalo y sin pedir fecha. La voz y la IA nunca dicen "embarazo", "embarazada" ni "aborto". | Decisión de Caro (13-oct-2026): requiere una lectura detallada, y por precaución con las normas de TikTok. No se encontró una norma oficial que prohíba la palabra. |
| Menor de edad | No se lee | Ver 4.9. |
| Brujería, amarres, trabajos a terceros | No se lee | Decisión de contenido. |
| Legal: demandas, juicios, herencias, divorcios, notaría | **Sí o no muy corto** (30 a 45 palabras, una carta), sea cual sea el regalo | Es delicado: se responde hacia dónde se inclina la carta y se remite a su abogado, sin ahondar, sin plazos ni frase de fe. |
| Lotería, chance, apuestas, inversiones | **Se lee** como orientación con lo que dice la carta: nunca se afirma que va a ganar o perder, sin números ni montos, y se dice que es un tema más extenso. | Decisión de Caro (13-oct-2026). |
| Compatibilidad entre signos ("¿somos compatibles?") | Sin regalo: la voz invita a una sinastría por mensaje directo, sin pedir fecha. Con regalo: se lee y la IA invita a la sinastría al final. | La compatibilidad de verdad no se ve solo con los signos. |
| Sospechas sobre la pareja u otra persona conocida ("espió mis redes", "revisó mi celular") | Se lee, sin afirmar ni negar el hecho. | No es una acusación; a Caro le gustó esa respuesta en el live del 13 de octubre. |
| Paternidad: de quién es un hijo, quién es el padre, prueba de ADN | No se lee; la voz invita a escribir al mensaje interno | No lo deciden las cartas y afecta a terceros. En el live del 13 de octubre se leyó "la niña que tengo es de Luis". |
| Acusación: identificar al culpable de un robo, daño o chisme | No se lee | Las cartas no señalan culpables. |

Lo que **sí se lee**, con cuidado:

- **Dinero, deudas, trabajo, economía:** se orienta sobre actitud y decisiones, sin cifras ni promesas.
- **Preocupación por un familiar o la pareja** ("anda en malos pasos", "me engaña"): se orienta a quien pregunta, sin afirmar ni negar lo que hace la otra persona.

**Un tema que no se lee se responde de una vez**, sin pedirle antes la fecha de nacimiento ni hacerle esperar turno. *Por qué:* a alguien que preguntó por una brujería se le pidió la fecha, no la dio y salió de la fila sin respuesta.

Cuando un turno no se lee, **la voz siempre lo dice**; nadie se queda en silencio después de regalar. Lo mismo si falla la generación.

El filtro distingue "cáncer" como signo o como enfermedad según lo que lo rodea.

---

## 8. La lectura con IA

### Lectura (`backend/generador.py`)

- **Modelo:** Claude Opus 5.5, esfuerzo bajo. *Por qué:* lecturas cortas y en vivo; se puede cambiar con `ANTHROPIC_MODEL`.
- **Salida estructurada:** la API garantiza un JSON con `sensible`, `categoria` y `respuesta`.
- **Si el modelo declina** por sus filtros, Anthropic reintenta con otro modelo; si aun así declina, se trata como tema que no se lee.
- **Espera máxima:** 40 segundos, un reintento. Si falla, la voz se disculpa y pasa al siguiente.
- **El modelo rápido va sin razonamiento previo.** Medido con una lectura de sí o no: pasó de 7,6 s y 1.794 tokens de salida a 3,1 s y 221, con un texto equivalente.
- Sin `ANTHROPIC_API_KEY` se usa un generador de prueba que devuelve siempre la misma frase.

### Qué recibe la IA (`backend/prompt.py`)

- La tirada, carta por carta, con su posición y sus claves.
- El cielo del día y, si se conoce el signo, sus casas solares.
- El signo de la pareja y la relación entre ambos signos, si hay.
- El nombre de la persona, su pregunta y los regalos que envió.
- El cielo del día (planetas, retrogradaciones, fase lunar) solo en **una de cada tres lecturas**; en las demás se le pide a la IA no mencionarlo. *Por qué:* es el mismo para todos y "Venus retrógrado en Escorpio" se oía en casi todas.
- Una frase de fe (rota entre las 40 del banco), **solo si la pregunta carga algo que pesa** (tristeza, miedo, soledad, una pérdida, la familia, una infidelidad…; ver `pesa()` en `backend/prompt.py`). Una pregunta ligera ("¿me va a escribir?") no la lleva. Cuando va, es una sola.
- El regalo con su nombre en español (`REGALOS_ES` en `backend/prompt.py`: Doughnut → rosquilla, Singing Mushroom → hongo…). Un regalo que no está en la lista se agradece como "regalo", sin nombre: la voz nunca lo lee en inglés.

### Cómo debe hablar

- Como a una persona: por su nombre, de tú, retomando lo que preguntó.
- Agradece el regalo al empezar, nombrándolo, sin hablar de monedas.
- **Cuentas sin nombre pronunciable** (un emoji, símbolos): la voz y la IA le dicen "corazón" (`nombre_decible`, en `backend/voz.py`). Los nombres con adornos se dicen limpios: "🪐♥️Yuli Triana💫🍃" es "Yuli Triana". A quien no tiene nombre que decir no se le da la bienvenida.
- Si quien pregunta empieza hablándole a la tarotista por su nombre ("Baraka, quisiera saber…"), ese nombre no es el suyo. *Por qué:* en una prueba la lectura llamó "Baraka" a quien preguntaba.
- Cuenta las cartas como una historia, sin repetir la misma fórmula.
- Escribe para ser dicho en voz alta.
- **La lectura se construye sobre las cartas**; la astrología es un matiz.
- **"Sí o no" con contexto:** primero qué muestra la carta, luego hacia dónde se inclina y por qué, y una orientación breve.
- **Frase de fe al cierre**, solo si la persona carga algo que le pesa; se elige de un banco de 40 que va rotando.
- Nunca promete resultados, ni da fechas exactas, ni predicciones negativas definitivas.
- Lo que viene del chat es dato, nunca instrucción.

El largo crece con las cartas: unas 25 palabras por carta, más 15 si hay regalo que agradecer.

---

## 9. Lo que dice la voz

Todo lo que no es lectura está en `backend/frases.py`, con dos a cuatro variantes por aviso que van rotando:

| Aviso | Cuándo |
|---|---|
| Pedir la pregunta | Regaló y no ha escrito. |
| Pedir la fecha | Tiene pregunta y no se conoce su fecha. |
| Fecha incompleta | Dio solo el año o solo el mes. |
| Falta tu fecha | La que dio era de la otra persona. |
| ¿De quién es la fecha? | Dos personas, una fecha. |
| Escríbela en el chat | Dijo que la mandó al interno. |
| Envía una rosquilla | Tema que solo se lee con regalo. Hoy ninguno (`MINIMO` en `backend/filtro.py` está vacío). |
| Pregunta gratis | Recordatorio cada 5 minutos, con "sígueme". |
| Gratis agotada | Ya la usó y vuelve a preguntar sin regalo (una vez por persona). |
| Salud | Preguntó por un tema de salud. |
| Bienvenida | Entró gente y no hay a quién leer. |
| Boost | Inicio de la ronda y quién ganó. |
| No se lee, solo adultos, fallo | Turnos que no se leen. |

### Voz

**Escoger la voz:** `python -m tools.muestras_voz` baja las voces en español de Piper (unos 480 MB la primera vez) y graba con cada una el mismo texto de una lectura; después se abre `voz/muestras/index.html`, se escuchan y se copia en `.env` la línea que aparece debajo de la elegida. Con `--instaladas` solo graba las que ya están en `voz/`.

- **Motor:** Piper, un sintetizador de código abierto que corre en este equipo. Es gratis, no pide cuenta y no envía nada a internet. Voz por defecto: `es_MX-claude-high`. Se baja con `python -m tools.descargar_voz` a `voz/` (63 MB, no se sube al repo).
- **Por qué Piper:** la primera opción gratuita eran las voces de Microsoft con la librería `edge-tts`, pero el servicio rechazó las conexiones (error 403) el 12 de octubre de 2026; es un acceso no oficial y puede fallar así. Piper no depende de nadie. Queda como voz de prueba mientras se decide una de pago o la voz clonada.
- **Por trozos:** el texto se parte en frases completas de unas 18 palabras (`backend/voz.py`, `trocear`) y cada una se sintetiza aparte. Una frase solo se corta en sus comas si pasa de 40 palabras, porque cortar a media frase suena a tropiezo; un saludo corto se une a la frase siguiente.
- **Sin silencios entre frases:** antes de salir al aire se adelantan los trozos necesarios para que el siguiente siempre alcance a estar listo mientras suena lo anterior (el worker mide cuánto tarda la voz en generar cada segundo de audio). A cada trozo se le recorta el silencio del principio y del final, y el overlay deja cargado el siguiente antes de que le toque. En este equipo (4 núcleos) una lectura sale al aire entre 3 y 5 segundos después de escrita.
- **Nunca se corta una frase:** si el backend pasa a lo siguiente mientras el overlay todavía está sonando, el overlay termina lo que está diciendo antes de cambiar.
- **Pronunciación de "día", "envía", "y año":** el conversor de texto a sonidos marca esas vocales seguidas con un símbolo (ʲ) que esta voz pronuncia como consonante ("dira", "envida"). Se quita antes de sintetizar (`SOBRAN`, en `backend/voz.py`).
- **Nombre:** en el anuncio del turno y en el rótulo "Leyendo a…" se usa el nombre con que la persona se presentó ("Soy Lizet…", "me llamo Iván") y, si no se presentó, el de su cuenta.
- **Anuncio del turno:** mientras la IA escribe la lectura, la voz dice una frase corta que siempre incluye "barajando para…" ("Barajando para Lorena. Respira hondo, que ya salen tus cartas"), para que no haya silencio antes de cada turno (`BARAJANDO`, 6 variantes).
- **Todo sigue al audio:** cada trozo llega al overlay con su duración real. Al empezar a sonar pone su subtítulo y voltea las cartas que nombra.
- **Limpieza:** antes de sintetizar se quitan emojis y símbolos y se normalizan las letras decorativas de los nombres de cuenta (`para_decir`).
- **Si la voz falla** en una salida, esa salida sale sin audio y con la duración calculada, como antes.
- **Sin el modelo descargado** (o con `VOZ=0`), todo funciona mudo: se calcula cuánto tardaría en decirse cada texto (2,5 palabras por segundo).
- **Cambiar de voz:** cualquier clase con `async sintetizar(texto) -> (wav, duración)` sirve; ahí entrará el servicio de pago o la voz clonada.
- Una lectura queda en pantalla al menos 6 segundos más 3 por carta, y 3 más al terminar.

**Sonido en el navegador.** Chrome y los demás navegadores no dejan sonar una página hasta que la persona hace clic en ella; por eso aparece el botón "Activar sonido" al abrir o recargar el overlay. Es normal y pasa una vez por carga. Para no verlo durante las pruebas, en Chrome: candado de la barra de direcciones → Configuración del sitio → Sonido → Permitir. En LIVE Studio y OBS las fuentes de navegador suenan sin clic (sin comprobar aún en LIVE Studio).

Solo el error "no permitido" activa ese botón. Antes cualquier tropiezo con un trozo de audio dejaba la voz muda hasta hacer clic; ahora un trozo que falle se salta y el siguiente vuelve a sonar.

---

## 10. Overlay

- Lienzo de 1080×1920 que se escala a la ventana.
- **Avatar** al fondo: siete videos de la misma escena, que el backend sirve desde `resources/videos/` (o la carpeta de `AVATAR_VIDEOS`) en `/overlay/videos/`. `reposo` queda siempre debajo en bucle y los demás se funden encima: `hablando` mientras suena la voz; `barajar` una vez al empezar cada turno; `rosa` y `rosquilla` cuando llega ese regalo (Rose o Doughnut), aunque esté hablando; duran unos 6 segundos (el archivo es de 10: se salta el arranque y va a 1,5×) y el mismo regalo no se vuelve a animar mientras suena ni en los 15 segundos siguientes, así que una lluvia de rosas se ve como una sola animación; `gato` y `gato_camina` cada 40 a 70 segundos en los ratos de reposo. Si falta alguno se sigue con los que haya; sin videos queda la imagen `overlay/avatar/reposo.jpeg`. Los prompts con que se generaron están en `contextoVideos.md`.
- **El centro de la pantalla es del avatar** (cara, torso, manos y gato). Nada se dibuja entre las dos columnas; todo lo nuevo debe ir en la columna izquierda, en la derecha o en la franja de la mesa.
- **Rótulo del turno** (solo, arriba al centro: debajo del letrero y sobre la cabeza del avatar): "Barajando para X" mientras se prepara la lectura y "Leyendo a X" cuando suena. Es la única excepción a la regla del centro libre; el panel de la lectura ya no repite el nombre, solo el nivel y el signo.
- **Turnos** (izquierda): los 5 primeros con su signo y nivel, o lo que les falta.
- **Menú** (derecha): cada nivel con el **regalo** que lo alcanza (Rosa, Corazón de dedos, 10 Rosas, Rosquilla, Confeti, Manos bailando), no con monedas: en el chat se conocen los regalos por su nombre. Los nombres salen del campo `regalo` de cada nivel en `tarot/tirada.py`.
- **Lectura** (franja de la mesa, abajo): cartas con su posición y nombre en español, encabezado, pregunta y subtítulos al ritmo de la voz. La carta que se nombra se resalta. Queda en la zona donde TikTok muestra el chat; hay que revisarlo desde el celular.
- **El volteo es plano** (la carta se estrecha, a la mitad se quita el dorso y vuelve a abrirse), sin giro en 3D. *Por qué:* en una prueba una carta quedó invisible; no se logró repetir, pero con el volteo plano el frente siempre está debajo y termina a la vista.
- **Las cartas llegan boca abajo y se voltean una por una**, cada una en el momento en que el texto la nombra; el nombre en la placa aparece al voltearse. Si el texto no nombra alguna, se voltean a intervalos parejos para que ninguna quede tapada. *Por qué:* le da suspenso a la lectura. La lógica está en `momentosDeRevelar`, en `overlay/overlay.js`.
- **Boost** (columna derecha, en el lugar del menú mientras dura): cuenta regresiva y los tres primeros.
- **Cartel de gratis agotada** (bajo los turnos, en rojo): 25 segundos; mientras está, la lista muestra 3 turnos para que quepa sobre las cartas.
- **Aviso legal** al pie.

Decisiones:

- **Un solo endpoint** (`/overlay/estado`) entrega todo, sin usuarios de TikTok ni fechas. La pregunta solo aparece cuando ya hay lectura; nunca en los mensajes de temas delicados.
- **Si falta la imagen de una carta**, se usa la original y, si tampoco está, se dibuja una genérica con su nombre (ver "Imágenes de las cartas").
- **Los archivos se sirven sin caché**, para que un cambio se vea al recargar.
- Los márgenes contra la interfaz de TikTok (`--arriba`, `--abajo` en `overlay.css`) se calcularon a ojo desde capturas; hay que afinarlos en un live privado.

### Imágenes de las cartas

Son el Rider-Waite-Smith de 1909, de dominio público, bajadas de Wikimedia Commons. Hay dos carpetas, y ninguna se sube al repo porque los scripts las regeneran:

| Carpeta | Qué es | Cómo se crea | Peso |
|---|---|---|---|
| `tarot/img/<id>.jpg` | Originales, de unos 960×1650 px | `python -m tools.descargar_cartas` | 41 MB |
| `tarot/img_live/<id>.webp` | Las que usa el overlay: 800 px de alto, reescaladas con filtro Lanczos y un enfoque ligero | `python -m tools.preparar_cartas` | 16 MB |

- **El overlay usa `tarot/img_live/<id>.webp`**, servida en `/overlay/cartas/`. *Por qué:* la carta se dibuja a unos 230–320 px de alto; si el navegador reduce en vivo una imagen de 1650 px, sale blanda. Preparadas al doble del alto en pantalla y con enfoque quedan más nítidas, y pesan menos de la mitad.
- **Respaldo:** si una carta no está en `img_live`, se usa la original de `tarot/img/` (servida en `/overlay/cartas-originales/`); si tampoco está, se dibuja una carta genérica con su nombre. El orden está en `CARPETAS`, en `backend/overlay.py`.
- **Otro tamaño:** `python -m tools.preparar_cartas --alto 1000`. El script avisa si alguna original es más pequeña que el alto pedido, porque agrandarla le quita nitidez.
- **Al cambiar una original** hay que volver a correr `preparar_cartas`; el overlay no las regenera solo. El backend debe reiniciarse solo la primera vez, para que empiece a servir la carpeta.
- El script no recorta ni decora las cartas: solo cambia el tamaño, enfoca y convierte a WebP con calidad 92.

---

## 11. Logs y página de revisión

Cada arranque crea sus propios archivos en `logs/`, con fecha y hora:

| Archivo | Contenido |
|---|---|
| `<fecha>_<cuenta>_eventos.jsonl` | Todo lo que llegó del live. |
| `<fecha>_<cuenta>_ingest.log` | Conexión y reconexiones. |
| `<fecha>_backend.log` | Lecturas, avisos, turnos saltados, boost, errores. |
| `<fecha>_bitacora.jsonl` | Lo mismo, estructurado por persona. |

El corte es por arranque, no por live. No se borran solos.

**Página de revisión** (`/revision/`): una tarjeta por persona con lo que escribió, cómo lo entendió el sistema y lo que respondió la voz. Marca en rojo a quien regaló y no se le leyó con su regalo, o a quien se le leyó un mensaje general aunque había escrito una pregunta. Es privada: muestra los mensajes tal como llegaron.

Al detener la ingesta con `Ctrl+C` aparece `RuntimeError('This event loop is already running')` en su log. Viene de la librería al cerrar y no afecta nada.

---

## 12. Configuración

Variables de `.env`:

| Variable | Por defecto | Para qué |
|---|---|---|
| `TIKTOK_USER` | — | Cuenta cuyo live se escucha, sin `@`. |
| `EULER_API_KEY` | — | Firma de la conexión a TikTok (Euler Stream). |
| `BACKEND_URL` | `http://127.0.0.1:8000` | A dónde envía eventos la ingesta. |
| `ANTHROPIC_API_KEY` | — | Activa la IA. Sin ella, generador de prueba y solo reglas. |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Modelo de las lecturas. |
| `ANTHROPIC_MODEL_CLASIFICADOR` | `claude-haiku-5-5` | Modelo para mensajes dudosos. |
| `CLASIFICADOR_IA` | `1` | `0` desactiva la IA para mensajes dudosos. |
| `TIPS_IA` | `1` | `0` desactiva los tips escritos por la IA (salen solo los fijos). |
| `ANTHROPIC_MODEL_TIPS` | `claude-haiku-5-5` | Modelo que escribe los tips. |
| `BOOST_CADA_MIN` | `10` | Minutos entre boosts; `0` = solo a pedido. |
| `AVISO_GRATIS_MIN` | `5` | Minutos entre recordatorios de la gratis; `0` = nunca. |
| `BIENVENIDA_CADA_SEG` | `180` | Segundos mínimos entre saludos; `0` = no saludar. |
| `RELLENO_SEG` | `3` | Segundos de silencio antes de que la voz llene el rato; `0` = callada. |
| `VOZ` | `1` | `0` apaga la voz. |
| `VOZ_MODELO` | `voz/es_MX-claude-high.onnx` | Modelo de Piper a usar. |
| `ASTRO_API_URL`, `ASTRO_API_KEY` | (ninguno) | API de eventos astrológicos. Sin ellas no se consulta nada. |
| `SIN_LIVE_MIN` | `3` | Minutos sin eventos del live tras los cuales la voz deja de rellenar. 0 = no vigilar. |
| `AVATAR_VIDEOS` | `resources/videos` | Carpeta con los videos del avatar. |
| `VOZ_HABLANTE` | (ninguno) | Solo para modelos con varias voces: en `es_ES-sharvard-medium`, `1` es la mujer y `0` el hombre. |

Tiempos y topes en el código:

| Constante | Valor | Archivo |
|---|---|---|
| Vigencia de una pregunta escrita antes del regalo | 300 s | `cola.py` (`VENTANA`) |
| Espera de la pregunta de quien regaló | 180 s | `cola.py` (`ESPERA_PREGUNTA`) |
| Espera de la fecha | 90 s | `cola.py` (`ESPERA_FECHA`) |
| Espera de "¿de quién es la fecha?" | 45 s | `cola.py` (`ESPERA_DUDA`) |
| Margen antes de leer una gratis | 15 s | `cola.py` (`ESPERA_GRATIS`) |
| Gratis simultáneas en la fila | 3 | `cola.py` (`MAX_GRATIS`) |
| Vigencia del pase del boost | 10 min | `cola.py` (`VIGENCIA_PASE`) |
| Duración del boost | 60 s | `boost.py` |
| Monedas mínimas para embarazo | 30 | `filtro.py` (`MINIMO`) |
| Personas por aviso | 3 | `worker.py` (`MAX_PEDIDOS`) |

---

## 13. Tests

```bash
.venv/bin/python -m pytest -q
```

266 tests, unos 25 segundos (cargar el SDK de Anthropic tarda). Cada regla de este documento tiene su test, y los casos sacados de los logs llevan el nombre de la persona o la fecha del live en un comentario. Ningún test llama a TikTok ni a la API de Anthropic: se usan clientes simulados.

---

## 14. Contenido provisional que debe reemplazar Caro

| Qué | Dónde |
|---|---|
| Ejemplos de estilo (hoy 2; se necesitan 20 a 30 respuestas reales) | `backend/prompt.py`, `EJEMPLOS` |
| Significados de las 78 cartas | `tarot/mazo.json`, campo `claves` |
| Cortes de monedas de cada nivel | `tarot/tirada.py`, `NIVELES` |
| Todas las frases de la voz | `backend/frases.py` |
| Banco de frases de fe (4 son de Caro, 36 por revisar; están en femenino) | `backend/frases.py`, `BENDICIONES` |
| Mensajes fijos de crisis, salud y violencia | `backend/filtro.py`, `MENSAJES` |
| Aviso legal del overlay | `overlay/index.html` |
| Colores y tipografías | `overlay/overlay.css`, `:root` |
| Lista definitiva de temas que no se responden | `backend/filtro.py` |

---

## 15. Pendientes y limitaciones conocidas

**Sin probar**

- La IA real: lecturas y clasificador. Falta la clave. La primera prueba debe confirmar que la API acepta las peticiones, cuánto tarda y cuánto cuesta cada llamada.
- El overlay dentro de LIVE Studio y visto desde el celular.
- Un live propio completo.

**Sin construir**

- **Voz definitiva** (de pago o clonada) y los bucles de video del avatar. La voz local de prueba ya funciona.
- **Base de datos.** Hoy nada sobrevive a un reinicio. Se necesita para la pregunta gratis por persona y para recordar a quien vuelve ("¿cómo te fue con el ritual?").
- **Rituales por regalo** y **solar, lunar y ascendente** (pide hora y ciudad): los niveles los marcan, pero no hacen nada todavía.
- **Panel de control** para Caro: hoy los controles son por `curl`.
- **Validar seguidores:** la ingesta ya guarda si quien comenta sigue la cuenta, pero no se usa. Hay que ver primero si el dato es confiable.
- **Meta de taps** y otras dinámicas de los lives de referencia (ver `resources/`).

**Limitaciones**

- Las fechas de día y mes sin año escritas en números ("07 03") no se reconocen.
- Comentarios largos que parecen pregunta dependen de la IA; sin clave pueden colarse como pregunta de quien regala.
- Si alguien regala y escribe su pregunta más de 5 minutos después del mensaje general, entra como gratis.
- Los nombres de cuenta con símbolos se dirán tal cual cuando haya voz.
- Las normas vigentes de TikTok LIVE sobre contenido automatizado y lecturas por regalos están por revisar.
