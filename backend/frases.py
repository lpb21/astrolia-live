"""Lo que dice la voz fuera de las lecturas. Cada aviso tiene varias frases que se van rotando
para que no suene siempre igual. PROVISIONAL: Caro las ajusta a su manera de hablar; se pueden
agregar o quitar frases de cualquier grupo (mínimo una).

{n} es el nombre o los nombres. Donde hay pareja de frases, la primera es para una persona y
la segunda para varias."""

PIDE_PREGUNTA = (
    ("{n}, gracias por tu regalo. Escribe tu pregunta con tu fecha de nacimiento; si prefieres, "
     "te leo el mensaje que las cartas tienen para ti.",
     "{n}, gracias por sus regalos. Escriban su pregunta con su fecha de nacimiento; si prefieren, "
     "les leo el mensaje que las cartas tienen para ustedes."),
    ("{n}, qué lindo detalle, gracias. Cuéntame en el chat qué quieres preguntarle a las cartas "
     "y cuál es tu fecha de nacimiento.",
     "{n}, qué lindos detalles, gracias. Cuéntenme en el chat qué quieren preguntarle a las cartas "
     "y cuál es su fecha de nacimiento."),
    ("Gracias por el regalo, {n}. Ya tienes tu turno: déjame tu pregunta y tu fecha de nacimiento, "
     "o si quieres te leo un mensaje general.",
     "Gracias por los regalos, {n}. Ya tienen su turno: déjenme su pregunta y su fecha de nacimiento, "
     "o si quieren les leo un mensaje general."),
)

PIDE_FECHA = (
    ("{n}, para leerte necesito tu fecha de nacimiento. Escríbela en el chat con día, mes y año.",
     "{n}, para leerles necesito su fecha de nacimiento. Escríbanla en el chat con día, mes y año."),
    ("{n}, ya casi es tu turno. Me falta tu fecha de nacimiento: día, mes y año, aquí en el chat.",
     "{n}, ya casi es su turno. Me falta su fecha de nacimiento: día, mes y año, aquí en el chat."),
    ("{n}, cuéntame tu fecha de nacimiento con día, mes y año, que quiero ver tu signo antes de "
     "sacar las cartas.",
     "{n}, cuéntenme su fecha de nacimiento con día, mes y año, que quiero ver su signo antes de "
     "sacar las cartas."),
)

# Ya usó su pregunta gratis y vuelve a preguntar sin regalo. Se dice una vez por persona, junto con el
# cartel del overlay. Primera frase: una persona; segunda: varias.
GRATIS_AGOTADA = (
    ("{n}, ya usaste tu pregunta gratis de este live. Envía un regalo y te leo esta también.",
     "{n}, ya usaron su pregunta gratis de este live. Envíen un regalo y les leo esta también."),
    ("{n}, tu pregunta gratis ya te la respondí. Con un regalo te abro las cartas para esta.",
     "{n}, su pregunta gratis ya se la respondí. Con un regalo les abro las cartas para esta."),
)

# Preguntas de salud: no se leen las cartas; se orienta con cariño a cuidarse e ir al médico.
SALUD = (
    "{n}, lo que me cuentas merece más atención de la que pueden darte las cartas. Quererse también es "
    "cuidarse: busca a un médico y sal de dudas. Aquí estoy para acompañarte en lo demás.",
    "{n}, con la salud prefiero no adivinar. Lo más amoroso que se puede hacer es ir al doctor y que te "
    "expliquen bien qué pasa; si es urgente, que sea hoy mismo. Te mando mucha luz para ese paso.",
    "{n}, hay preguntas que las cartas no deben responder, y esta es una. Date ese cariño de consultar "
    "con un médico y no lo dejes para después. Que Dios te acompañe en eso.",
)

# Preguntó por un tema que solo se lee con regalo (embarazo) y no ha enviado lo suficiente.
PIDE_ROSQUILLA = (
    "{n}, las preguntas de embarazo las leo con una rosquilla. Envíala y te respondo con las cartas.",
    "{n}, ese tema lo vemos con calma: envía una rosquilla y te leo esa pregunta.",
)

# Regaló y dijo que mandó la pregunta por mensaje privado.
ESCRIBE_EN_CHAT = (
    "{n}, por el interno no alcanzo a leerte durante el live. Escríbeme tu pregunta aquí en el chat y te la leo.",
    "{n}, los mensajes privados no los veo mientras estoy en vivo. Déjame tu pregunta aquí en el chat, con tu fecha de nacimiento.",
)

# La fecha que dio era de la otra persona (por el nombre de la cuenta o porque lo contestó).
PIDE_FECHA_PROPIA = (
    "{n}, ya tengo la fecha de la otra persona; me falta la tuya, con día, mes y año.",
    "{n}, esa fecha la anoté para tu pareja. Ahora escríbeme la tuya: día, mes y año.",
)

# Dos personas, una sola fecha y nada que diga de quién es. Mientras responde, se sigue leyendo a los demás.
DUDA_FECHA = (
    "{n}, la fecha que escribiste, ¿es tuya o de la otra persona? Respóndeme en el chat: mía, o de él, o de ella.",
    "{n}, para leerte bien: ¿esa fecha de nacimiento es la tuya o la de tu pareja? Escríbeme mía o suya.",
)

# Respondió la fecha a medias: se le dice qué falta y se le da el plazo otra vez.
FECHA_INCOMPLETA = {
    "anio": (
        "{n}, ya tengo el año, pero me falta el día y el mes en que naciste. Escríbelos en el chat.",
        "{n}, con solo el año no alcanzo a ver tu signo. Dime también el día y el mes de tu nacimiento.",
    ),
    "mes": (
        "{n}, ya tengo el mes, pero me falta el día en que naciste. Escríbelo en el chat.",
        "{n}, me falta el día de tu nacimiento para ver tu signo. Escríbeme la fecha completa.",
    ),
}

AVISO_GRATIS = (
    "Sígueme y deja tu pregunta gratis de sí o no en el chat, con signo de interrogación "
    "y tu fecha de nacimiento.",
    "Les recuerdo que hay una pregunta gratis de sí o no por persona. Sígueme, escríbela con signo "
    "de interrogación y tu fecha de nacimiento, y te la respondo en cuanto pueda.",
    "¿Todavía no has hecho tu pregunta gratis? Sígueme y déjala en el chat con signo de interrogación "
    "y tu fecha de nacimiento.",
)

# Turnos que no se leen. {n} no se usa aquí: el overlay ya muestra para quién es.
NO_SE_LEE = (
    "Esa pregunta no la puedo leer en el live. Si quieres, escríbeme al mensaje interno y lo vemos por allá.",
    "Ese tema prefiero no tocarlo aquí en vivo. Escríbeme al mensaje interno y lo conversamos con calma.",
    "Esa pregunta merece más cuidado del que puedo darle en el live. Te espero en el mensaje interno.",
)
SOLO_ADULTOS = (
    "Gracias por acompañarnos. Las lecturas de este live son solo para mayores de edad, "
    "así que esta vez no es posible hacer la tuya.",
    "Qué bueno tenerte por aquí. Este espacio de lecturas es solo para mayores de edad, "
    "por eso esta vez no puedo leerte.",
)
FALLO = (
    "Tuve un problema para leer tus cartas en este momento. Escríbeme al mensaje interno "
    "y te hago llegar tu lectura.",
    "Se me cruzaron las cartas y no pude leerte ahora. Escríbeme al mensaje interno y te la envío.",
)

# Boost de likes. {seg}: duración de la ronda; {n}: quien ganó; {likes}: cuántos dio.
BOOST_INICIO = (
    "¡Boost de likes! Durante {seg} segundos, quien más toque la pantalla pasa de primero con su pregunta.",
    "¡Arranca el boost! Tienen {seg} segundos: quien más likes dé se lleva el primer turno.",
    "¡A tocar la pantalla! Por {seg} segundos, quien más likes mande pasa de primero con su pregunta.",
)
BOOST_GANO = (
    "{n} ganó el boost con {likes} likes. Tu pregunta pasa de primera.",
    "¡{n} se llevó el boost con {likes} likes! Ya te leo, vas de primero.",
    "Con {likes} likes, el boost es de {n}. Tu pregunta sube al primer turno.",
)
BOOST_GANO_SIN_PREGUNTA = (
    "{n} ganó el boost con {likes} likes. Escribe tu pregunta con tu fecha de nacimiento y te leo de primero.",
    "¡{n} se llevó el boost con {likes} likes! Déjame tu pregunta y tu fecha de nacimiento, que vas de primero.",
)

# Saludo a quienes van entrando al live, entre una lectura y otra. Primera frase: una persona;
# segunda: varias. {n} son los nombres.
BIENVENIDA = (
    ("{n}, bienvenida al live. Qué bueno tenerte por aquí.",
     "{n}, bienvenidos al live. Qué bueno tenerlos por aquí."),
    ("Hola, {n}, gracias por conectarte. Ponte cómoda y cuéntame qué quieres preguntarle a las cartas.",
     "Hola, {n}, gracias por conectarse. Pónganse cómodos y cuéntenme qué quieren preguntarle a las cartas."),
    ("Bienvenida, {n}. Si quieres tu pregunta gratis, déjala en el chat con signo de interrogación.",
     "Bienvenidos, {n}. Si quieren su pregunta gratis, déjenla en el chat con signo de interrogación."),
    ("Qué alegría verte llegar, {n}. Aquí estamos leyendo las cartas, quédate un ratico.",
     "Qué alegría verlos llegar, {n}. Aquí estamos leyendo las cartas, quédense un ratico."),
)
# Cuando entran más personas de las que se alcanzan a nombrar, se agrega al final de los nombres
Y_LOS_DEMAS = " y todos los que van llegando"

# Frases de fe para cerrar una lectura. No van en todas: en cada turno se le ofrecen cuatro a la
# IA, que usa una solo si la pregunta lo amerita (alguien que carga algo pesado) y la que mejor
# le quede al tema. Van rotando para que no se repitan. PROVISIONAL: Caro agrega, quita o cambia.
BENDICIONES = (
    # para cualquier tema
    "Que sea Dios quien te guíe e ilumine tu camino.",
    "Dios te bendiga, te deseo lo mejor en esto.",
    "No se te olvide que Dios siempre está contigo.",
    "Dios siempre está disponible para escucharte; solo abre tu corazón.",
    "Pon esto en manos de Dios y camina tranquila, que Él sabe lo que hace.",
    "Que Dios te dé claridad para ver lo que hoy no alcanzas a ver.",
    "Confía, que los tiempos de Dios son perfectos.",
    "Dios no te trajo hasta aquí para soltarte ahora.",
    "Que Dios te acompañe en cada paso que des.",
    "Encomienda tu día a Dios y verás cómo se acomoda todo.",
    # amor y pareja
    "Pídele a Dios que te muestre quién llega a tu vida para quedarse.",
    "Que Dios cuide tu corazón y lo llene de un amor que te haga bien.",
    "Lo que es para ti, Dios lo pone en tu camino sin que tengas que rogarlo.",
    "Que Dios sane lo que te dolió y te prepare para lo que viene.",
    "Dios conoce tu corazón; deja que Él te muestre si esa persona es para ti.",
    "Que Dios bendiga esa relación y les dé sabiduría a los dos.",
    "Si Dios cierra esa puerta, es porque tiene una mejor para ti.",
    "Ora por esa persona y suelta el resultado en las manos de Dios.",
    # familia e hijos
    "Que Dios cubra a tu familia con su amor y su protección.",
    "Dios cuida a tus hijos incluso cuando tú no puedes estar ahí.",
    "Que Dios ponga paz en tu hogar y palabras suaves en cada boca.",
    "Encomienda a los tuyos a Dios cada mañana; Él los guarda.",
    "Que Dios restaure lo que se rompió en tu familia.",
    # trabajo y dinero
    "Que Dios abra las puertas que nadie pueda cerrar.",
    "Dios provee; haz tu parte y deja el resto en sus manos.",
    "Que Dios bendiga el trabajo de tus manos y lo multiplique.",
    "No te afanes: Dios sabe lo que necesitas antes de que se lo pidas.",
    "Que Dios te dé fuerza para seguir y sabiduría para decidir.",
    # tristeza, soledad, momentos difíciles
    "No estás sola: Dios está contigo también en esta parte del camino.",
    "Que Dios te dé la paz que hoy te hace falta.",
    "Dios recoge cada una de tus lágrimas; esto también va a pasar.",
    "Descansa en Dios, que Él pelea las batallas que tú ya no puedes.",
    "Que Dios te abrace esta noche y te devuelva la calma.",
    "Después de la tormenta Dios siempre manda la calma; aguanta un poco más.",
    "Dios no te da una carga que no puedas llevar, y tampoco te deja sola con ella.",
    # decisiones y dudas
    "Antes de decidir, habla con Dios; Él te va a dar la respuesta en el corazón.",
    "Que Dios te dé discernimiento para elegir lo que te trae paz.",
    "Si sientes paz, es Dios diciéndote que vas por buen camino.",
    "Pídele a Dios una señal y mantén los ojos abiertos, que Él responde.",
    "Que Dios te quite el miedo y te dé valor para dar ese paso.",
)
