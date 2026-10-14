# Prompts para los videos del avatar

Imagen de partida para todos: la misma de la escena actual (vertical 9:16).
Los videos terminados van en `resources/videos/` con el nombre que se indica en cada uno.

## Resolución: lo primero que hay que mirar

Los videos que se generaron la primera vez salieron de **478×850** y el overlay es de **1080×1920**:
al ampliarlos se ven blandos. La resolución casi nunca se controla con el prompt; se elige en los
ajustes de la herramienta. En este orden:

1. **Ajuste de calidad o resolución:** busca "Resolution", "Quality", "1080p", "HD", "Professional
   mode" o "High quality" y elige **1080p** (o 720p como mínimo). Suele estar bloqueado en el plan
   gratuito o costar más créditos.
2. **Relación de aspecto:** **9:16** (vertical). Si no deja elegirla, toma la de la imagen de partida.
3. **Imagen de partida grande:** sube la imagen ya ampliada a **1080×1920**. Varias herramientas
   generan al tamaño de la imagen que reciben; con una de 768×1376 o menor el video sale pequeño.
4. **Ampliar después ("Upscale", "Enhance", "4K"):** si la herramienta solo genera en baja, casi
   todas tienen un botón para ampliar el video ya hecho. Es la salida más común.
5. **Descarga:** revisa que al descargar no esté elegida una versión "preview" o "SD".

Cada prompt termina con una línea que pide 1080×1920 y nitidez. Ayuda a que el dibujo salga limpio,
pero no reemplaza el ajuste: si la herramienta está en 480p, el archivo seguirá saliendo en 480p.

**Cómo comprobarlo:** en las propiedades del archivo (Detalles → ancho y alto del fotograma) debe
decir 1080×1920, o al menos 720×1280.

## Antes de generar

- **Modo:** imagen a video (image-to-video), con la imagen de la escena como primer fotograma. Para
  que los clips nuevos casen con los que ya tienes, usa **la misma imagen** con la que generaste
  los anteriores (la del letrero y el cuadro "STAR MAP").
- **Primer y último fotograma:** si la herramienta deja poner también el último fotograma ("start/end frame",
  "first & last frame"), pon **la misma imagen en los dos**. Es lo que más ayuda a que cada clip termine
  igual a como empezó y se pueda pasar de uno a otro sin salto.
- **Formato:** 9:16, 1080×1920, sin audio, sin marca de agua.
- **Duración:** la que se indica en cada clip. Si solo ofrece 5 o 10 segundos, usa la más cercana.
- **Mismos nombres:** guarda cada video con el nombre indicado en `resources/videos/`, reemplazando
  el anterior. El overlay los toma de ahí; no hay que cambiar nada más.
- **Si un clip sale mal:** lo más común es que cambie la cara, que mueva la cámara o que no vuelva a la
  pose inicial. Genera otra vez con el mismo prompt antes de cambiarlo; suele variar mucho entre intentos.

### Bloque común

Va **al final de todos los prompts** (ya está incluido en cada uno abajo; aquí queda para tenerlo a mano):

```
Static camera, locked-off tripod shot, no zoom, no pan, no camera shake. Keep the exact same
semi-realistic digital painting style, the same face, hair, clothes, lighting and colors as the
source image. The framed sign text at the top, the star map poster, the books and all objects stay
unchanged and perfectly readable. Tiny warm glowing motes, like fireflies, drift slowly across the
whole frame, fading in and out. Every candle flame flickers and sways gently, and its warm light
pulses softly on nearby objects. The final frame matches the first frame exactly.
Vertical 9:16 video, 1080x1920 pixels, full HD, 24 fps, crisp and sharp details, clean lines,
readable text on the sign, no blur, no compression artifacts, no audio.
```

### Prompt negativo

Para las herramientas que lo aceptan:

```
low resolution, pixelated, soft focus, camera movement, zoom, pan, cut, scene change, morphing face, changing hairstyle, extra fingers,
extra limbs, deformed hands, distorted text, changed sign text, subtitles, watermark, logo,
flickering background, objects appearing or disappearing, 3D render, photo, anime, low quality, blur
```

---

## 1. Reposo — `reposo.mp4` (bucle, 8–10 s)

Es el que más tiempo está en pantalla: movimiento mínimo.

```
Subtle idle animation of the illustrated woman sitting at her tarot table. She keeps the same pose
and the same gentle closed-mouth smile, looking at the viewer. She breathes slowly with a slight
rise and fall of her shoulders, blinks naturally two or three times and makes one very small tilt
of her head. A few strands of her long hair move almost imperceptibly. Her right hand stays resting
on the table cards and her left hand stays resting on the sleeping cat. The cat stays curled up
asleep, breathing slowly, and one ear twitches once. Her mouth stays closed the whole time.
Seamless loop.

Static camera, locked-off tripod shot, no zoom, no pan, no camera shake. Keep the exact same
semi-realistic digital painting style, the same face, hair, clothes, lighting and colors as the
source image. The framed sign text at the top, the star map poster, the books and all objects stay
unchanged and perfectly readable. Tiny warm glowing motes, like fireflies, drift slowly across the
whole frame, fading in and out. Every candle flame flickers and sways gently, and its warm light
pulses softly on nearby objects. The final frame matches the first frame exactly.
Vertical 9:16 video, 1080x1920 pixels, full HD, 24 fps, crisp and sharp details, clean lines,
readable text on the sign, no blur, no compression artifacts, no audio.
```

## 2. Hablando — `hablando.mp4` (bucle, 8–10 s)

Suena mientras la voz lee. Los labios no van sincronizados con el audio; por eso el movimiento debe
ser parejo y continuo, sin gestos marcados.

```
The illustrated woman speaks calmly and warmly to the viewer, looking straight at the camera. Her
mouth opens and closes in a natural, continuous, even talking rhythm, as in a relaxed conversation,
with soft and gentle changes in her eyebrows and small nods. She blinks naturally. Her shoulders and
body stay in the same pose, her right hand stays on the table cards and her left hand stays resting
on the sleeping cat. The cat stays asleep, breathing slowly. She never laughs, never shows surprise
and never turns her head away. The clip starts and ends with her mouth closed in the same gentle
smile as the first frame. Seamless loop.

Static camera, locked-off tripod shot, no zoom, no pan, no camera shake. Keep the exact same
semi-realistic digital painting style, the same face, hair, clothes, lighting and colors as the
source image. The framed sign text at the top, the star map poster, the books and all objects stay
unchanged and perfectly readable. Tiny warm glowing motes, like fireflies, drift slowly across the
whole frame, fading in and out. Every candle flame flickers and sways gently, and its warm light
pulses softly on nearby objects. The final frame matches the first frame exactly.
Vertical 9:16 video, 1080x1920 pixels, full HD, 24 fps, crisp and sharp details, clean lines,
readable text on the sign, no blur, no compression artifacts, no audio.
```

## 3. Acaricia al gato — `gato.mp4` (una vez, 6–8 s)

```
The illustrated woman glances down at the calico cat sleeping beside her with a tender smile and
slowly strokes its back two times with the hand that is already resting on it. The cat stays lying
down, purrs, stretches its front paws a little and curls its tail, eyes closed and content. She
then looks back up at the viewer and returns to exactly the same pose and the same gentle
closed-mouth smile as the first frame, with her hand resting on the cat again. Her mouth stays
closed the whole time. Her other hand stays on the table cards.

Static camera, locked-off tripod shot, no zoom, no pan, no camera shake. Keep the exact same
semi-realistic digital painting style, the same face, hair, clothes, lighting and colors as the
source image. The framed sign text at the top, the star map poster, the books and all objects stay
unchanged and perfectly readable. Tiny warm glowing motes, like fireflies, drift slowly across the
whole frame, fading in and out. Every candle flame flickers and sways gently, and its warm light
pulses softly on nearby objects. The final frame matches the first frame exactly.
Vertical 9:16 video, 1080x1920 pixels, full HD, 24 fps, crisp and sharp details, clean lines,
readable text on the sign, no blur, no compression artifacts, no audio.
```

## 4. El gato se levanta y camina por la mesa — `gato_camina.mp4` (una vez, 10 s)

Es el más difícil: el gato tiene que salir y volver al mismo sitio. Aquí sí o sí conviene poner la
misma imagen como primer y último fotograma. Si la herramienta no lo permite, es probable que el
gato no termine donde empezó; en ese caso pide solo la primera mitad (se levanta y camina) y otra
toma aparte donde vuelve y se acuesta.

```
The calico cat sleeping on the wooden table wakes up, opens its eyes, stretches with a long arched
back and stands up. The woman lifts her hand slightly to let it go and watches it with a tender,
amused closed-mouth smile. The cat walks slowly and gracefully along the table in front of her,
from the right side to the left side, passing behind the row of tarot cards without touching or
moving them, sniffs the purple crystal, turns around and walks calmly back to its original spot
beside her. It circles once, lies down, curls up in exactly the same position as the first frame
and closes its eyes. The woman rests her hand on its back again and looks at the viewer with the
same gentle smile as the first frame. The cat keeps the same size, fur pattern and colors the whole
time. The cards, the candle, the crystal, the mug and the open book never move.

Static camera, locked-off tripod shot, no zoom, no pan, no camera shake. Keep the exact same
semi-realistic digital painting style, the same face, hair, clothes, lighting and colors as the
source image. The framed sign text at the top, the star map poster, the books and all objects stay
unchanged and perfectly readable. Tiny warm glowing motes, like fireflies, drift slowly across the
whole frame, fading in and out. Every candle flame flickers and sways gently, and its warm light
pulses softly on nearby objects. The final frame matches the first frame exactly.
Vertical 9:16 video, 1080x1920 pixels, full HD, 24 fps, crisp and sharp details, clean lines,
readable text on the sign, no blur, no compression artifacts, no audio.
```

## 5. Baraja las cartas — `barajar.mp4` (una vez, 8–10 s)

Para el momento "Barajando para…". También pide que las cartas vuelvan a quedar como al principio:
usa la misma imagen de primer y último fotograma.

```
The illustrated woman looks down at the tarot cards on the wooden table with a calm, focused
expression. With both hands she gathers the face-down cards into a single deck, lifts it slightly
and shuffles it with slow, elegant overhand movements, the dark blue card backs with golden stars
clearly visible. She then spreads the cards again in a neat fan on the table, face down, in exactly
the same arrangement as the first frame, places her right hand on the center card and her left hand
back on the sleeping cat, and looks up at the viewer with the same gentle closed-mouth smile as the
first frame. Her hands have five natural fingers at all times. The cat stays asleep, breathing
slowly. Her mouth stays closed the whole time. No card is ever turned face up.

Static camera, locked-off tripod shot, no zoom, no pan, no camera shake. Keep the exact same
semi-realistic digital painting style, the same face, hair, clothes, lighting and colors as the
source image. The framed sign text at the top, the star map poster, the books and all objects stay
unchanged and perfectly readable. Tiny warm glowing motes, like fireflies, drift slowly across the
whole frame, fading in and out. Every candle flame flickers and sways gently, and its warm light
pulses softly on nearby objects. The final frame matches the first frame exactly.
Vertical 9:16 video, 1080x1920 pixels, full HD, 24 fps, crisp and sharp details, clean lines,
readable text on the sign, no blur, no compression artifacts, no audio.
```

## 6. Regalo de rosa — `rosa.mp4` (una vez, 5 s)

```
A single glowing red rose with a short green stem enters the frame from the left edge, at the
height of the woman's shoulders, leaving a soft trail of golden sparkles and a few falling red
petals. It floats in a gentle rising arc across the air toward the red rose pinned in her hair, on
the right side of her head. When it reaches the rose in her hair it merges into it with a soft
burst of golden light and dissolves completely, and the rose in her hair glows warmly for a moment
and then returns to normal. The woman follows the flying rose with her eyes, smiles a little wider
with her mouth closed, and then looks back at the viewer with the same gentle smile as the first
frame. Her body and hands keep the same pose and the cat stays asleep. At the end nothing new
remains in the scene: only the one rose in her hair, exactly as in the first frame.

Static camera, locked-off tripod shot, no zoom, no pan, no camera shake. Keep the exact same
semi-realistic digital painting style, the same face, hair, clothes, lighting and colors as the
source image. The framed sign text at the top, the star map poster, the books and all objects stay
unchanged and perfectly readable. Tiny warm glowing motes, like fireflies, drift slowly across the
whole frame, fading in and out. Every candle flame flickers and sways gently, and its warm light
pulses softly on nearby objects. The final frame matches the first frame exactly.
Vertical 9:16 video, 1080x1920 pixels, full HD, 24 fps, crisp and sharp details, clean lines,
readable text on the sign, no blur, no compression artifacts, no audio.
```

## 7. Regalo de rosquilla — `rosquilla.mp4` (una vez, 5 s)

```
A pink frosted doughnut with colorful sprinkles appears in the air above the wooden table, in front
of the woman at chest height, materializing out of a swirl of golden sparkles. It floats and spins
slowly, rising a little, glowing softly, while a few sprinkles and sparkles drift around it. Then
it fades and dissolves into a cloud of golden dust that rises and disappears completely. The woman
looks at the doughnut with delighted eyes and a slightly wider closed-mouth smile, and then looks
back at the viewer with the same gentle smile as the first frame. Her body and hands keep the same
pose and the cat stays asleep; the cat's nose twitches once. At the end nothing new remains in the
scene: the table and the air are exactly as in the first frame.

Static camera, locked-off tripod shot, no zoom, no pan, no camera shake. Keep the exact same
semi-realistic digital painting style, the same face, hair, clothes, lighting and colors as the
source image. The framed sign text at the top, the star map poster, the books and all objects stay
unchanged and perfectly readable. Tiny warm glowing motes, like fireflies, drift slowly across the
whole frame, fading in and out. Every candle flame flickers and sways gently, and its warm light
pulses softly on nearby objects. The final frame matches the first frame exactly.
Vertical 9:16 video, 1080x1920 pixels, full HD, 24 fps, crisp and sharp details, clean lines,
readable text on the sign, no blur, no compression artifacts, no audio.
```

---

## Notas

- **Luciérnagas y velas** van escritas en el bloque común, así que salen en todos los clips. Al
  pasar de un clip a otro las luciérnagas no coinciden exactamente; el overlay hace un fundido
  corto entre videos y no se nota.
- **Rosa y rosquilla mientras habla:** un regalo puede llegar en mitad de una lectura. Si se pone
  el clip en ese momento, la boca deja de moverse mientras la voz sigue sonando. Alternativa: que
  la rosa y la rosquilla sean un efecto dibujado por el overlay encima del video (vuela, se
  difumina), que funciona en cualquier momento sin interrumpir el clip de "hablando".
- **El letrero:** en `avatarvivi2.jpeg` el cuadro de estrellas todavía dice "STARL MAP". El rótulo
  "Leyendo a… / Barajando para…" del overlay lo tapa mientras hay turno; el resto del tiempo se ve.
- **Qué usa el overlay:** los siete clips, desde `resources/videos/`.
