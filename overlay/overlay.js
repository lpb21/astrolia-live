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
const TITULOS = { pide_pregunta: "Astrolia", pide_fecha: "Astrolia", aviso: "Pregunta gratis", bienvenida: "Bienvenida", boost: "⚡ Boost de likes" };

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
  caja.append(cara, el("span", "carta-posicion", c.posicion), pie);
  return caja;
}

let subtitulos = { clave: null, lista: [], inicio: 0, indice: -1, pps: 2.5 };

function pintarVoz(h, pps) {
  if (cambio("voz", h && h.clave)) {
    $("voz").hidden = !h;
    $("cartas").replaceChildren(...(h ? h.cartas.map(carta) : []));
    $("cartas").dataset.n = h ? h.cartas.length : 0;
    subtitulos = { clave: h && h.clave, lista: h ? trozos(h.texto, h.tipo === "lectura" ? PALABRAS_TROZO : PALABRAS_AVISO) : [], inicio: performance.now(), indice: -1,
                   pps: pps > 0 ? pps : 2.5 };
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
  avanzarSubtitulo();
}

// El subtítulo avanza al ritmo de la voz: cada trozo dura sus palabras / palabras por segundo.
function avanzarSubtitulo() {
  const s = subtitulos;
  if (!s.clave || !s.lista.length) return;
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

function pintar(e) {
  pintarBoost(e.boost);
  pintarMenu(e.menu);
  pintarTurnos(e.turnos, e.en_cola);
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
  const c = (posicion, id, nombre) => ({ posicion, id, nombre, imagen: `cartas/${id}.jpg` });
  const seis = [c("pasado", "seis-copas", "Seis de Copas"), c("presente", "dos-espadas", "Dos de Espadas"),
                c("futuro", "la-estrella", "La Estrella"), c("obstáculo", "cinco-bastos", "Cinco de Bastos"),
                c("lo oculto", "la-luna", "La Luna"), c("consejo", "ocho-oros", "Ocho de Oros")];
  const base = { pausado: false, palabras_por_seg: 2.5, menu, turnos, en_cola: 7, actual: null, hablando: null, boost: null };
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

if (DEMO) demo();
else { consultar(); setInterval(consultar, INTERVALO); }
