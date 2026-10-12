"use strict";
// Overlay de Astrolia Live: consulta /overlay/estado y dibuja turnos, menú y la lectura en curso.
// Todo texto que viene del chat entra con textContent, nunca como HTML.

const INTERVALO = 700;            // ms entre consultas
const PALABRAS_TROZO = 18;        // tamaño aproximado de cada subtítulo de una lectura
const PALABRAS_AVISO = 40;        // los avisos y mensajes fijos, que son cortos, salen completos
const SIMBOLOS = { bastos: "🜂", copas: "☾", espadas: "⚔", oros: "✪" };
const GLIFOS = { Aries: "♈", Tauro: "♉", "Géminis": "♊", "Cáncer": "♋", Leo: "♌", Virgo: "♍", Libra: "♎",
                 Escorpio: "♏", Sagitario: "♐", Capricornio: "♑", Acuario: "♒", Piscis: "♓" };
// El signo confirma en pantalla que la fecha llegó, sin mostrarla. \uFE0E: glifo de texto, no emoji.
const signoTxt = (signo) => `${(GLIFOS[signo] || "") + "\uFE0E"} ${signo}`;
const TITULOS = { pide_pregunta: "Astrolia", pide_fecha: "Astrolia", pide_regalo: "Astrolia", aviso: "Pregunta gratis", agotada: "Pregunta gratis", bienvenida: "Bienvenida", boost: "⚡ Boost de likes" };

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const DEMO = params.has("demo");
if (params.has("fondo")) document.body.classList.add("fondo");

function escalar() {
  const escala = Math.min(innerWidth / 1080, innerHeight / 1920);
  $("lienzo").style.setProperty("--escala", escala);
}
addEventListener("resize", escalar);
escalar();

// ---------- avatar ----------
// Imagen fija de base y, si existen, bucles de video encima: "reposo" casi siempre, "hablando" mientras
// la voz dice algo y "gato" (acaricia al gato) cada tanto en los ratos de reposo.
const avatar = { videos: {}, actual: "", proximoGato: 0 };

function iniciarAvatar() {
  const fija = $("avatar-fija");
  fija.onload = () => { $("avatar").hidden = false; };
  fija.onerror = () => fija.remove();
  if (fija.complete && fija.naturalWidth) $("avatar").hidden = false;
  for (const nombre of ["reposo", "hablando", "gato"]) {
    const v = document.createElement("video");
    v.muted = true;
    v.playsInline = true;
    v.loop = nombre !== "gato";
    v.preload = "auto";
    v.oncanplaythrough = () => { avatar.videos[nombre] = v; $("avatar").hidden = false; };
    v.onerror = () => v.remove();                      // ese bucle aún no existe: se sigue con lo que haya
    v.onended = () => mostrarAvatar("reposo");
    v.src = `avatar/${nombre}.mp4`;
    $("avatar").append(v);
  }
  avatar.proximoGato = performance.now() + 40000;
}

function mostrarAvatar(nombre) {
  if (!avatar.videos[nombre]) nombre = avatar.videos.reposo ? "reposo" : "";
  if (nombre === avatar.actual) return;
  avatar.actual = nombre;
  for (const [n, v] of Object.entries(avatar.videos)) {
    v.classList.toggle("visible", n === nombre);
    if (n === nombre) { v.currentTime = 0; v.play().catch(() => {}); } else if (n !== "reposo") v.pause();
  }
}

function pintarAvatar(hablando) {
  const ahora = performance.now();
  if (hablando) { mostrarAvatar("hablando"); avatar.proximoGato = ahora + 30000; return; }
  if (avatar.actual === "gato") return;                // deja terminar la caricia
  if (avatar.videos.gato && ahora > avatar.proximoGato) {
    avatar.proximoGato = ahora + 40000 + Math.random() * 30000;
    mostrarAvatar("gato");
    return;
  }
  mostrarAvatar("reposo");
}

function el(etiqueta, clase, texto) {
  const e = document.createElement(etiqueta);
  if (clase) e.className = clase;
  if (texto != null) e.textContent = texto;
  return e;
}

// Cada bloque se vuelve a dibujar solo cuando cambian sus datos, para no reiniciar animaciones.
const previo = {};
function cambio(nombre, datos) {
  const s = JSON.stringify(datos);
  if (previo[nombre] === s) return false;
  previo[nombre] = s;
  return true;
}

// ---------- menú y turnos ----------
function pintarMenu(menu) {
  if (!cambio("menu", menu)) return;
  $("menu").hidden = !menu.length;
  $("menu-lista").replaceChildren(...menu.map((n) => {
    const li = el("li");
    li.append(el("span", n.monedas ? "monedas" : "monedas gratis", n.monedas ? `${n.monedas} 🪙` : "Gratis"),
              el("span", "menu-nombre", n.nombre));
    return li;
  }));
}

function pintarTurnos(turnos, enCola) {
  if (!cambio("turnos", [turnos, enCola])) return;
  $("turnos").hidden = !turnos.length;
  $("turnos-total").textContent = enCola ? `· ${enCola}` : "";
  $("turnos-lista").replaceChildren(...turnos.map((t) => {
    const li = el("li");
    const falta = t.falta.includes("pregunta") ? "escribe tu pregunta"
                : t.falta.includes("fecha") ? "falta tu fecha" : "";
    const detalle = falta || (t.signo ? `${signoTxt(t.signo)} · ${t.nivel}` : t.nivel);   // el signo primero: la columna es angosta
    li.append(el("span", "turno-nombre", t.nickname),
              t.pase ? el("span", "turno-detalle pase", `⚡ Ganó el boost${falta ? " · " + falta : ""}`)
                     : el("span", falta ? "turno-detalle falta" : "turno-detalle", detalle));
    return li;
  }));
  const mas = enCola - turnos.length;
  $("turnos-mas").hidden = mas <= 0;
  $("turnos-mas").textContent = `+${mas} más en la fila`;
}

// ---------- lectura ----------
function trozos(texto, maximo) {
  const frases = texto.match(/[^.!?…]+[.!?…]+["”»)]*|[^.!?…]+$/g) || [texto];
  const salida = [];
  let actual = "";
  for (const f of frases.map((x) => x.trim()).filter(Boolean)) {
    const junto = actual ? `${actual} ${f}` : f;
    if (actual && junto.split(/\s+/).length > maximo) { salida.push(actual); actual = f; }
    else actual = junto;
  }
  if (actual) salida.push(actual);
  return salida;
}

function carta(c, i) {
  const caja = el("div", "carta");
  caja.style.setProperty("--i", i);
  caja.dataset.nombre = c.nombre.toLowerCase();
  const cara = el("div", "carta-cara");
  const giro = el("div", "carta-giro");               // llega boca abajo; se voltea al llegarle la lectura
  giro.append(cara, el("div", "carta-cara carta-dorso"));
  const pie = el("span", "carta-pie", c.nombre);      // las imágenes traen el nombre en inglés
  const dibujar = () => {
    const palo = c.id.split("-").pop();
    cara.className = "carta-cara sin-imagen";
    cara.replaceChildren(el("span", "carta-simbolo", SIMBOLOS[palo] || "✦"), el("span", "carta-nombre", c.nombre));
    pie.hidden = true;
  };
  if (c.imagen) {
    const img = el("img");
    img.alt = c.nombre;
    img.onerror = dibujar;
    img.src = c.imagen;
    cara.append(img);
  } else dibujar();
  const rotulo = el("div", "carta-rotulo");
  rotulo.append(el("span", "carta-posicion", c.posicion), pie);
  caja.append(giro, rotulo);
  return caja;
}

// ---------- voz ----------
// Con voz, el backend manda la lectura en trozos, cada uno con su audio. Se reproducen en fila y cada
// trozo, al empezar a sonar, pone su subtítulo y voltea las cartas que nombra: todo sigue al audio real.
const voz = { trozos: [], completo: false, k: -1, sonando: false, audio: null, bloqueada: false, reloj: 0 };

function reiniciarVoz() {
  if (voz.audio) voz.audio.pause();
  clearTimeout(voz.reloj);
  Object.assign(voz, { trozos: [], completo: false, k: -1, sonando: false, audio: null });
}

function mostrarTrozo(texto) {
  const caja = $("voz-texto");
  caja.textContent = texto;
  caja.classList.remove("cambia");
  void caja.offsetWidth;                      // reinicia la animación de entrada
  caja.classList.add("cambia");
  const dicho = texto.toLowerCase();
  for (const c of $("cartas").children) {
    const nombrada = dicho.includes(c.dataset.nombre);
    if (nombrada) c.classList.add("revelada");
    c.classList.toggle("activa", nombrada);
  }
}

function sonarSiguiente() {
  if (voz.sonando) return;
  const t = voz.trozos[voz.k + 1];
  if (!t) {
    if (voz.completo && voz.k >= 0)           // terminó: que ninguna carta quede boca abajo
      for (const c of $("cartas").children) c.classList.add("revelada");
    return;
  }
  voz.k++;
  voz.sonando = true;
  mostrarTrozo(t.texto);
  const fin = () => { clearTimeout(voz.reloj); voz.sonando = false; sonarSiguiente(); };
  const sinAudio = () => { voz.reloj = setTimeout(fin, t.dur * 1000); };     // mantiene el ritmo aunque no suene
  if (voz.bloqueada) return sinAudio();
  const a = new Audio(t.audio);
  voz.audio = a;
  a.onended = fin;
  a.onerror = sinAudio;
  a.play().catch(() => {                       // el navegador exige un clic antes de dejar sonar
    voz.bloqueada = true;
    $("sonido").hidden = false;
    sinAudio();
  });
}

$("sonido").addEventListener("click", () => {
  voz.bloqueada = false;
  $("sonido").hidden = true;
});

let subtitulos = { clave: null, lista: [], inicio: 0, indice: -1, pps: 2.5, revelar: [] };

function pintarVoz(h, pps) {
  if (cambio("voz", h && h.clave)) {
    $("voz").hidden = !h;
    $("cartas").replaceChildren(...(h ? h.cartas.map(carta) : []));
    $("cartas").dataset.n = h ? h.cartas.length : 0;
    subtitulos = { clave: h && h.clave, lista: h ? trozos(h.texto, h.tipo === "lectura" ? PALABRAS_TROZO : PALABRAS_AVISO) : [], inicio: performance.now(), indice: -1,
                   pps: pps > 0 ? pps : 2.5 };
    subtitulos.revelar = h ? momentosDeRevelar(h.cartas, subtitulos.lista, subtitulos.pps) : [];
    reiniciarVoz();
    if (h && h.trozos.length) subtitulos.lista = [];      // con voz manda el audio, no el reloj
    if (h) {
      const quien = el("p");
      if (h.tipo === "lectura") {
        quien.append("Leyendo a ", el("strong", "", h.nickname));
        if (h.nivel) quien.append(el("small", "", h.signo ? `${h.nivel} · ${signoTxt(h.signo)}` : h.nivel));
      } else {
        quien.textContent = TITULOS[h.tipo] || `Para ${h.nickname}`;   // los avisos ya nombran a quién van
      }
      $("voz-quien").replaceChildren(...quien.childNodes);
      $("voz-pregunta").hidden = !h.pregunta;
      $("voz-pregunta").textContent = h.pregunta ? `“${h.pregunta}”` : "";
    }
  }
  if (h && h.trozos.length) {
    voz.trozos = h.trozos;
    voz.completo = h.completo;
    sonarSiguiente();
  }
  avanzarSubtitulo();
}

// Cuándo se voltea cada carta, en segundos desde que empieza la lectura: en el momento en que el texto
// la nombra. Si el texto no la nombra, se reparten a intervalos parejos para que ninguna quede boca abajo.
function momentosDeRevelar(cartas, lista, pps) {
  const inicios = [];
  let t = 0;
  for (const trozo of lista) { inicios.push(t); t += trozo.split(/\s+/).length / pps; }
  const total = Math.max(t, 6 + 3 * cartas.length);     // lo mínimo que la lectura queda en pantalla
  return cartas.map((c, i) => {
    const k = lista.findIndex((trozo) => trozo.toLowerCase().includes(c.nombre.toLowerCase()));
    const reparto = 1.4 + i * (total - 2.5) / Math.max(cartas.length, 1);
    return k >= 0 ? Math.max(inicios[k], .9 + i * .25) : reparto;   // nunca antes de que termine de llegar
  });
}

function revelarCartas() {
  const t = (performance.now() - subtitulos.inicio) / 1000;
  [...$("cartas").children].forEach((c, i) => {
    if (t >= (subtitulos.revelar[i] ?? 0)) c.classList.add("revelada");
  });
}

// El subtítulo avanza al ritmo de la voz: cada trozo dura sus palabras / palabras por segundo.
function avanzarSubtitulo() {
  const s = subtitulos;
  if (!s.clave || !s.lista.length) return;
  revelarCartas();
  let t = (performance.now() - s.inicio) / 1000;
  let i = 0;
  while (i < s.lista.length - 1) {
    const dur = s.lista[i].split(/\s+/).length / s.pps;
    if (t < dur) break;
    t -= dur;
    i++;
  }
  if (i === s.indice) return;
  s.indice = i;
  const texto = $("voz-texto");
  texto.textContent = s.lista[i];
  texto.classList.remove("cambia");
  void texto.offsetWidth;                     // reinicia la animación de entrada
  texto.classList.add("cambia");
  const dicho = s.lista[i].toLowerCase();
  for (const c of $("cartas").children) c.classList.toggle("activa", dicho.includes(c.dataset.nombre));
}

function pintarEstado(e) {
  const estado = $("estado");
  let texto, espera = false;
  if (e.hablando) texto = "";
  else if (e.pausado) texto = "Volvemos en un momento";
  else if (e.actual) { texto = `Barajando para ${e.actual.nickname}`; espera = true; }
  else { texto = e.en_cola ? "Preparando la siguiente lectura" : "Esperando lectura"; espera = true; }
  estado.hidden = !texto;
  estado.textContent = texto;
  estado.classList.toggle("espera", espera);
}

function pintarBoost(b) {
  $("boost").hidden = !b;
  $("menu").classList.toggle("cede", Boolean(b));       // el boost va en el lugar del menú, no sobre el avatar
  if (!b) return;
  const seg = Math.max(b.restante, 0);
  $("boost-reloj").textContent = `0:${String(seg).padStart(2, "0")}`;
  if (!cambio("boost", b.top)) return;
  $("boost-top").replaceChildren(...b.top.map((p) => {
    const li = el("li");
    li.append(el("span", "nombre", p.nickname), el("span", "likes", `${p.likes} ♥`));
    return li;
  }));
}

function pintarCartel(nombres) {
  $("cartel").hidden = !nombres;
  if (nombres) $("cartel-quien").textContent = nombres;
}

function pintar(e) {
  pintarAvatar(Boolean(e.hablando));
  pintarBoost(e.boost);
  pintarCartel(e.cartel);
  pintarMenu(e.menu);
  pintarTurnos(e.cartel ? e.turnos.slice(0, 3) : e.turnos, e.en_cola);   // con cartel, menos turnos: cabe sobre las cartas
  pintarVoz(e.hablando, e.palabras_por_seg);
  pintarEstado(e);
}

// ---------- datos ----------
async function consultar() {
  try {
    const r = await fetch("estado", { cache: "no-store" });
    if (r.ok) pintar(await r.json());
  } catch (err) {
    console.warn("overlay: sin conexión con el backend", err);   // al aire se conserva lo último dibujado
  }
}

// ?demo=1: recorre los estados con datos de muestra, para acomodar la escena sin un live.
function demo() {
  const menu = [[0, "Sí o no"], [1, "Mensaje del oráculo"], [5, "Tres tiempos"], [10, "Tres tiempos con consejo"],
                [30, "Lectura doble"], [100, "Lectura completa"], [200, "Lectura maestra"]]
    .map(([monedas, nombre]) => ({ monedas, nombre, cartas: 1 }));
  const turnos = [
    { nickname: "Valentina Robledo", nivel: "Lectura completa", falta: [], signo: "Libra" },
    { nickname: "Xenia25", nivel: "Lectura doble", falta: ["pregunta"] },
    { nickname: "María Eugenia 🌙", nivel: "Tres tiempos", falta: ["fecha"] },
    { nickname: "Roo Ramírez", nivel: "Mensaje del oráculo", falta: [], signo: "Cáncer" },
    { nickname: "chiquiz sandoval", nivel: "Mensaje del oráculo", falta: [] },
  ];
  const c = (posicion, id, nombre) => ({ posicion, id, nombre, imagen: `cartas/${id}.webp` });
  const seis = [c("pasado", "seis-copas", "Seis de Copas"), c("presente", "dos-espadas", "Dos de Espadas"),
                c("futuro", "la-estrella", "La Estrella"), c("obstáculo", "cinco-bastos", "Cinco de Bastos"),
                c("lo oculto", "la-luna", "La Luna"), c("consejo", "ocho-oros", "Ocho de Oros")];
  const base = { pausado: false, palabras_por_seg: 2.5, menu, turnos, en_cola: 7, actual: null, hablando: null, boost: null, cartel: null };
  const leyendo = { nickname: "Daihana", nivel: "Lectura completa", signo: "Escorpio" };
  const pasos = [
    [3, base],
    [6, { ...base, hablando: { clave: "a", tipo: "pide_pregunta", nickname: "Xenia25", nivel: "", pregunta: "", cartas: [],
        texto: "Xenia25: gracias por tu regalo. Escribe tu pregunta con tu fecha de nacimiento; si prefieres, te leo el mensaje que las cartas tienen para ti." } }],
    [3, { ...base, actual: leyendo }],
    [26, { ...base, actual: leyendo, hablando: { clave: "b", tipo: "lectura", ...leyendo, cartas: seis,
        pregunta: "quiero saber si Ricardo volverá a escribirme",
        texto: "En tu pasado sale el Seis de Copas: hubo ternura real y por eso cuesta soltar. "
             + "En el presente, el Dos de Espadas muestra que ninguno quiere mirar lo que pasó. "
             + "Hacia el futuro aparece La Estrella: vuelve la calma, contigo en el centro. "
             + "El obstáculo es el Cinco de Bastos, el orgullo de los dos. "
             + "Lo oculto lo trae La Luna: hay cosas que todavía no te han dicho. "
             + "Tu consejo es el Ocho de Oros: constancia, no prisa." } }],
    [8, { ...base, boost: { restante: 37, top: [{ nickname: "Luz de Fuego 🔥", likes: 240 },
        { nickname: "chiquiz sandoval", likes: 185 }, { nickname: "Xenia25", likes: 96 }] },
        hablando: { clave: "d", tipo: "boost", nickname: "", nivel: "", pregunta: "", cartas: [],
          texto: "¡Boost de likes! Durante 60 segundos, quien más toque la pantalla pasa de primero con su pregunta." } }],
    [6, { ...base, turnos: [{ nickname: "Luz de Fuego 🔥", nivel: "Sí o no", falta: [], signo: "Aries", pase: true }, ...turnos.slice(0, 4)],
        hablando: { clave: "e", tipo: "boost", nickname: "Luz de Fuego 🔥", nivel: "", pregunta: "", cartas: [],
          texto: "Luz de Fuego 🔥 ganó el boost con 240 likes. Tu pregunta pasa de primera." } }],
    [7, { ...base, cartel: "Migdalia Jiménez",
        hablando: { clave: "f", tipo: "agotada", nickname: "Migdalia Jiménez", nivel: "", pregunta: "", cartas: [],
          texto: "Migdalia Jiménez, ya usaste tu pregunta gratis de este live. Envía un regalo y te leo esta también." } }],
    [8, { ...base, actual: { nickname: "Roo Ramírez", nivel: "Mensaje del oráculo" },
        hablando: { clave: "c", tipo: "lectura", nickname: "Roo Ramírez", nivel: "Mensaje del oráculo", pregunta: "",
          cartas: [c("mensaje", "la-emperatriz", "La Emperatriz")],
          texto: "Tu mensaje es La Emperatriz: lo que cuidas con paciencia está por dar fruto. Date permiso de recibir." } }],
  ];
  const fijo = params.get("demo");                     // ?demo=4 deja fijo el paso 4
  let i = fijo > 0 ? Math.min(fijo, pasos.length) - 1 : 0;
  let hasta = 0;
  setInterval(() => {
    const ahora = performance.now();
    if (!hasta) hasta = ahora + pasos[i][0] * 1000;
    else if (ahora > hasta && !(fijo > 0)) { i = (i + 1) % pasos.length; hasta = ahora + pasos[i][0] * 1000; }
    pintar(pasos[i][1]);
  }, 250);
}

iniciarAvatar();
setInterval(avanzarSubtitulo, 200);      // subtítulos y volteo de cartas a tiempo, sin esperar la siguiente consulta
if (DEMO) demo();
else { consultar(); setInterval(consultar, INTERVALO); }
