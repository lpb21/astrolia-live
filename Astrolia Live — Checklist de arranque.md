# Astrolia Live — Checklist de arranque

Oct 8, 2026 · @caro

Todo lo necesario, en orden, desde cero hasta el primer live con IA asistida. Cada tarea indica quién la hace: Caro, Leo o ambos.

## 1. Equipo y cuentas

- [x] Cuenta de Astrolia con acceso a LIVE (Caro)
- [ ] Computador para transmitir, con conexión estable; idealmente por cable (Caro y Leo)
- [ ] Micrófono externo o audífonos con micrófono; el del portátil se oye a eco (Caro)
- [ ] Luz frontal o aro de luz si Caro aparece en cámara (Caro)
- [ ] Correo exclusivo de Astrolia para registrar todas las herramientas (Caro)
- [ ] Gestor de contraseñas compartido o lugar seguro para guardar claves de API (Leo)

## 2. Transmisión: LIVE Studio y TikFinity

- [ ] Descargar TikTok LIVE Studio e iniciar sesión con Astrolia; confirmar que deja transmitir (Caro)
- [ ] Crear una escena base: fondo, cámara o avatar, zona para el overlay (Caro y Leo)
- [ ] Crear cuenta en TikFinity con el correo de Astrolia y conectar el usuario @soyastrolia (Leo)
- [ ] Configurar una alerta de prueba con la rosa (Leo)
- [ ] Live privado de 10 minutos: alguien de confianza manda una rosa y se confirma que la alerta sale (ambos)
- [ ] Revisar las normas vigentes de TikTok LIVE sobre contenido automatizado y lecturas por regalos (Caro)

## 3. Contenido de Caro

Es la parte que más define la calidad de la IA, y solo la puede hacer Caro.

- [ ] Cerrar el menú de regalos: regalo, nombre de la lectura, duración (Caro)
- [ ] Verificar en la app cuántas monedas cuesta hoy cada regalo elegido (Caro)
- [ ] Escribir 20 a 30 respuestas cortas reales, de 40 a 80 palabras, como ejemplos de estilo (Caro)
- [ ] Lista de temas que no se responden: salud, embarazo, muerte, dinero, legal, "trabajos" a terceros, menores (Caro)
- [ ] Lista de frases prohibidas: "sí asegurado", "él volverá", cualquier promesa de resultado (Caro)
- [ ] Textos fijos: bienvenida, aviso legal, cierre con link a servicios de Astrolia (Caro)
- [ ] Identidad visual del live: colores, logo, avatar o ilustración (Caro)

## 4. Entorno de desarrollo (Leo)

Stack definido: todo en Python. Captura con TikTokLive, firma con Euler Stream, backend FastAPI.

- [ ] Repositorio privado en GitHub para el proyecto (Leo)
- [ ] Python 3.11 o superior, entorno virtual, FastAPI, Uvicorn y SDK de Anthropic instalados (Leo)
- [ ] Instalar TikTokLive con versión fija en requirements.txt (`TikTokLive==<versión probada>`) (Leo)
- [ ] Cuenta en Euler Stream con el correo de Astrolia y API key; configurarla en `tiktok_sign_api_key` (Leo)
- [ ] Cuenta en la consola de Anthropic con el correo de Astrolia; clave de API y límite de gasto mensual (Leo)
- [ ] Archivo .env para todas las claves; nunca subirlo al repositorio (Leo)
- [ ] Proceso de ingesta separado: TikTokLive escucha a @soyastrolia y normaliza cada evento a `{user, tipo, regalo, valor, texto}` antes de enviarlo al backend (Leo)
- [ ] Plan B de ingesta: TikFinity enviando webhooks al mismo endpoint con el mismo formato (Leo)
- [ ] Health check: alerta si pasan 2 minutos sin eventos durante un live activo (Leo)
- [ ] No usar sessionId ni enviar mensajes al chat desde la librería; respuestas solo por overlay y voz (Leo)
- [ ] Cola con prioridad por valor de regalo y base SQLite para el historial (Leo)
- [ ] Simulador de eventos: script que inyecta regalos y comentarios falsos en el formato normalizado (Leo)

## 5. Motor astrológico con efemérides

- [ ] Instalar pyswisseph con versión fija y descargar los archivos de efemérides .se1 (Leo)
- [ ] Función que devuelva posiciones planetarias y fase lunar para fecha y hora dadas, en hora de Bogotá convertida a UTC (Leo)
- [ ] Función de tránsitos del día para cada signo solar: aspectos mayores a 0° del signo (Leo)
- [ ] Función opcional de carta rápida: fecha, hora y ciudad → Sol, Luna, Ascendente (Leo)
- [ ] Validar 10 fechas contra una efeméride de referencia; Caro revisa que coincidan (ambos)
- [ ] Definir con Caro qué tránsitos importan para cada tipo de lectura del menú (ambos)

## 6. IA asistida: borradores y panel de Caro

- [ ] Prompt de sistema con la voz de Caro, sus 20 a 30 ejemplos, temas y frases prohibidas (ambos)
- [ ] Filtro previo que detecta temas prohibidos y salta la pregunta antes de llamar a la IA (Leo)
- [ ] Función que arme la petición: pregunta + tipo de lectura + tránsitos calculados → borrador (Leo)
- [ ] Probar 50 preguntas reales de lives ajenos; Caro marca cada borrador como bueno, editable o malo (ambos)
- [ ] Ajustar el prompt hasta que la mayoría salgan buenos (ambos)
- [ ] Panel local para Caro: ver cola, ver borrador, aprobar, editar, saltar, pausar todo (Leo)
- [ ] Overlay HTML en LIVE Studio: menú fijo, "Leyendo a…", próximos en cola, aviso legal (Leo)

## 7. Pruebas y primer live

- [ ] Ensayo completo con el simulador: 30 minutos de regalos y preguntas falsas sin fallas (ambos)
- [ ] Live privado o con pocos amigos usando el sistema real (ambos)
- [ ] Probar el botón de pausa en pleno live (Caro)
- [ ] Anunciar el primer live en el perfil y en historias con fecha y hora (Caro)
- [ ] Primer live público de 45 a 60 minutos (Caro)
- [ ] Revisión al día siguiente: preguntas sin atender, borradores descartados, errores, regalos recibidos (ambos)
