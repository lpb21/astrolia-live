# Astrolia Live — Paso a paso para transmitir

Guía para salir al aire con el sistema. La instalación y el detalle de cada regla están en `README.md`;
aquí va solo lo que hay que hacer el día del live, en orden.

> **Lo que todavía no se ha probado.** El sistema se ha probado conectado a lives ajenos y viendo el
> overlay en el navegador. **No se ha probado dentro de TikTok LIVE Studio ni en un live propio**: los
> pasos 4 y 5 están escritos según cómo funciona LIVE Studio en general, y los nombres de los botones
> pueden variar con la versión. Por eso el paso 6 (ensayo) no es opcional.

---

## 1. Antes del día del live (una sola vez)

- [ ] El proyecto está instalado y los tests pasan: `.venv/bin/python -m pytest -q` (ver `README.md`, sección 2).
- [ ] La voz está descargada (`voz/es_MX-claude-high.onnx`) y las cartas preparadas (`tarot/img_live/`).
- [ ] Los siete videos del avatar están en `resources/videos/`.
- [ ] En `.env`:

  | Variable | Valor |
  |---|---|
  | `TIKTOK_USER` | **Tu cuenta**, sin arroba (por ejemplo `soyastrolia`). Mientras probabas tenía cuentas ajenas: cámbiala. |
  | `EULER_API_KEY` | La clave de EulerStream. |
  | `ANTHROPIC_API_KEY` | La clave de Anthropic, con saldo y con un límite de gasto mensual puesto en la consola. |
  | `VOZ_MODELO` | Sin poner, o `voz/es_MX-claude-high.onnx`. Las otras voces son demasiado lentas en este equipo. |

- [ ] TikTok LIVE Studio instalado en Windows, con sesión iniciada en la cuenta de Astrolia y con permiso de transmitir.
- [ ] Revisado y reemplazado lo provisional que sale al aire: nombres de los regalos del menú (`tarot/tirada.py`), aviso legal (`overlay/index.html`) y frases (`backend/frases.py`).

## 1.1 El equipo: lo que pasó en el primer live (13 de octubre de 2026)

El portátil (Intel i3-3110M de 2 núcleos, 8 GB) **no alcanza a transmitir con LIVE Studio y generar la voz
al mismo tiempo**. Con LIVE Studio abierto, la voz tardó más de un segundo en generar cada segundo de audio
(sin él tarda 0,3), una sola frase del boost demoró dos minutos y medio, y las preguntas quedaron esperando.

Antes de volver a transmitir desde este equipo hay que resolverlo con una de estas, de la más efectiva a la menos:

1. **Voz en la nube** (ElevenLabs, Cartesia u otra de pago): el audio se genera fuera del computador.
2. **Otro computador para el sistema:** backend e ingesta en un equipo y LIVE Studio en otro, que abre el
   overlay por la red (`http://IP-DEL-OTRO:8000/overlay/`, arrancando el backend con `--host 0.0.0.0`).
3. **Aliviar este equipo:** cerrar el navegador y todo lo demás durante el live, y bajar en LIVE Studio la
   calidad de salida (720p, 30 cuadros). Ayuda, pero puede no bastar.

**Cómo saber si está pasando:** en la terminal del backend aparece `[VOZ] lenta: tarda X s por cada segundo
de audio`. Mientras dure, el sistema suspende tips, saludos y avisos para dedicar la voz solo a las lecturas.
Otra señal: `voz lista` debe aparecer a los 5 a 10 segundos de arrancar; ese día tardó casi 5 minutos.

## 2. Arrancar el sistema (10 minutos antes)

Se abren **dos terminales de Ubuntu/WSL** en la carpeta del proyecto. Primero el backend, después la ingesta.

**Terminal 1 — backend:**

```bash
cd ~/proyectos/astrolia-live
.venv/bin/python -m uvicorn backend.app:app --port 8000
```

Está listo cuando aparecen `worker iniciado` y, unos segundos después, `voz lista`.

**Terminal 2 — ingesta:**

```bash
cd ~/proyectos/astrolia-live
.venv/bin/python -m ingest.tiktok_ingest
```

Mientras no estés en vivo dirá `no está en vivo, reintento en 30 s`. Es normal: se conecta sola cuando
empieces a transmitir, y entonces dice `Conectado a @tucuenta`. Hasta ese momento la voz se queda callada.

No cierres ninguna de las dos terminales durante el live.

## 3. Comprobar en el navegador (2 minutos)

Abre en Chrome, en Windows:

| Dirección | Qué debes ver |
|---|---|
| `http://127.0.0.1:8000/overlay/` | El avatar en movimiento, la columna "Lecturas" con los regalos y, abajo, "Sin conexión con el live" o "Esperando lectura". |
| `http://127.0.0.1:8000/overlay/?demo` | Lo mismo, recorriendo solo todos los estados con datos de muestra: turnos, cartas, boost, rosa y rosquilla. Sirve para acomodar la escena. |

Si la página no abre desde Windows, el backend no está corriendo o WSL no está pasando el puerto: cierra y
vuelve a abrir la terminal 1 y prueba de nuevo.

## 4. Montar la escena en TikTok LIVE Studio (una sola vez; después solo se revisa)

1. Crea una escena **vertical (retrato), de 1080 × 1920**.
2. Agrega una fuente de tipo **Enlace / Navegador** (en inglés, "Link" o "Browser source") con:
   - URL: `http://127.0.0.1:8000/overlay/`
   - Ancho: `1080` · Alto: `1920`
3. Estírala hasta que ocupe toda la escena. El overlay ya trae el avatar de fondo, así que **no hace falta
   cámara ni otra imagen detrás**.
4. **Sonido de la voz:** la voz de Astrolia sale de esa fuente de navegador. En las propiedades de la
   fuente, o en el mezclador de audio de LIVE Studio, deja activado su audio y con volumen. Si LIVE Studio
   no deja capturar el audio de la fuente, activa "audio del escritorio" (o "audio del sistema") y deja
   el overlay abierto también en Chrome para que suene por ahí.
5. **Micrófono:** si vas a hablar tú además de la voz, déjalo activo; si no, siléncialo para que no se
   mezcle el ruido del cuarto ni haga eco con la voz.
6. Guarda la escena.

Con el backend corriendo, la fuente debe mostrar lo mismo que viste en Chrome en el paso 3.

## 5. Salir al aire

1. En LIVE Studio escribe el título del live y revisa que la escena sea la del overlay.
2. Pulsa **Iniciar LIVE** ("Go LIVE").
3. Mira la terminal 2: en menos de un minuto debe decir `Conectado a @tucuenta`.
4. Mira la terminal 1: debe decir `[LIVE] conectado` y la voz empieza a saludar y a dar tips.
5. Abre el live **desde el celular, con otra cuenta**, y comprueba tres cosas: que se ve el avatar, que se
   oye la voz, y que el chat de TikTok no tapa las cartas ni los subtítulos.

A partir de ahí el sistema trabaja solo: recibe regalos y preguntas, pide lo que falta, lee y anima.

## 6. Ensayo antes del primer live público (no saltarlo)

Haz un live corto, de 10 a 15 minutos, con una o dos personas de confianza conectadas desde su celular, y
pídeles que hagan esto en orden:

- [ ] Escribir una pregunta con fecha de nacimiento, sin regalo → se lee como pregunta gratis ("Sí o no").
- [ ] Escribir una pregunta sin fecha → la voz pide la fecha.
- [ ] Enviar una **rosa** sin preguntar → sale la animación de la rosa, la voz agradece y dice cuánto tiempo tiene para preguntar.
- [ ] Enviar una **rosquilla** con pregunta → animación de la rosquilla y lectura de cuatro cartas.
- [ ] Tocar la pantalla durante el boost → aparecen en la lista y la voz anuncia quién ganó.
- [ ] Confirmar desde el celular que **la voz se oye clara**, sin eco y sin cortarse entre frases.
- [ ] Confirmar que las cartas y el texto **no quedan tapados por el chat** de TikTok.

Para lanzar el boost sin esperar: `curl -X POST http://127.0.0.1:8000/control/boost`

Anota lo que no se vea o no se oiga bien: son las dos cosas que no se han podido probar sin un live real.

## 7. Durante el live

Los controles se escriben en una **tercera terminal**:

```bash
curl -X POST http://127.0.0.1:8000/control/pausa       # la voz se detiene; la fila se conserva
curl -X POST http://127.0.0.1:8000/control/reanudar    # sigue donde iba
curl -X POST http://127.0.0.1:8000/control/boost       # abre ya una ronda de tap tap
curl -X POST "http://127.0.0.1:8000/cola/USUARIO/cerrar?estado=saltado"   # saca a alguien de la fila (su cuenta, sin arroba)
```

Para seguir qué está pasando: `http://127.0.0.1:8000/revision/` muestra, persona por persona, qué
escribió cada quien y qué hizo el sistema. Es privada: no la agregues a la escena.

## 8. Si algo falla en vivo

| Qué pasa | Qué hacer |
|---|---|
| La voz no suena en el live, pero el overlay se ve | Revisa el audio de la fuente en LIVE Studio (paso 4.4). Si en Chrome aparece el botón "Activar sonido", dale clic. |
| El overlay se ve en blanco o congelado | En LIVE Studio, actualiza la fuente de navegador (clic derecho → actualizar o recargar). |
| No aparecen turnos aunque escriben y regalan | Mira la terminal 2. Si no dice `Conectado`, ciérrala con `Ctrl+C` y vuelve a correr el comando de la ingesta. |
| El overlay dice "Sin conexión con el live" | Lo mismo: la ingesta no está conectada o no está corriendo. |
| El overlay dice "Volvemos en un momento" y la terminal 1 muestra `[LIMITE]` | Se alcanzó el límite de gasto de Anthropic. Súbelo en la consola y luego `curl -X POST http://127.0.0.1:8000/control/reanudar`. |
| La voz dice algo que no debe | `control/pausa` de inmediato. Después se revisa en `/revision/`. |
| Hay que reiniciar el backend en pleno live | `Ctrl+C` en la terminal 1 y volver a correr el comando. **Se pierde la fila**: quienes esperaban tendrán que escribir de nuevo. La ingesta no hay que tocarla; guarda los eventos y los reenvía. |

## 9. Al terminar

1. Termina el live en LIVE Studio.
2. `Ctrl+C` en la terminal 2 (ingesta) y luego en la terminal 1 (backend).
3. Los registros del live quedan en `logs/`, con la fecha y la hora de arranque en el nombre.
4. Para repasarlo con calma: vuelve a levantar solo el backend y abre `http://127.0.0.1:8000/revision/`;
   arriba se elige el live por fecha.

Antes del siguiente live se arrancan de nuevo los dos procesos, para que la fila empiece vacía y los
registros queden separados.
