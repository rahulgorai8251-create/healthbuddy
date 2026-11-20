/* HealthGuard - app.js
   1) Router: one "page" at a time, driven by the address (#/home, #/checkup ...). No page reload.
   2) Language (English/Hindi), login state, check-up form (BMI helper, unknown values, reset).
   3) Report upload (OCR in the browser) and voice input for symptoms.
   4) fetch() sends the form to Flask and draws results, explanations, what-if, history.                   */

const PAGES = ["home", "checkup", "results", "history", "login", "models", "how"];
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const enc = encodeURIComponent;
const JSONH = { "Content-Type": "application/json" };
const state = { lang: "en", result: null, payload: null, metrics: null, sex: "", symptoms: new Set(), symList: [], plan: 0, user: null, tab: "login", pendingSave: false };

try { state.lang = localStorage.getItem("hg-lang") === "hi" ? "hi" : "en"; } catch (e) { /* ignore */ }
try { state.result = JSON.parse(sessionStorage.getItem("hg-result") || "null"); state.payload = JSON.parse(sessionStorage.getItem("hg-payload") || "null"); } catch (e) { /* ignore */ }
function persist() { try { sessionStorage.setItem("hg-result", JSON.stringify(state.result)); sessionStorage.setItem("hg-payload", JSON.stringify(state.payload)); } catch (e) { /* ignore */ } }

/* ------------------------------------------------------------ language */
function t(key, vars) {
  let s = (I18N[state.lang] && I18N[state.lang][key]) ?? I18N.en[key] ?? key;
  if (vars) for (const k in vars) s = s.split("{" + k + "}").join(vars[k]);
  return s;
}
function applyI18n() {
  document.documentElement.lang = state.lang;
  $$("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
  $$("[data-i18n-ph]").forEach((el) => (el.placeholder = t(el.dataset.i18nPh)));
  $("#langBtn").textContent = state.lang === "en" ? "हिन्दी" : "English";
  const submit = $("#authSubmit"); submit.textContent = t(state.tab === "login" ? "btn_do_login" : "btn_do_signup");
  updateCount(); updateEstInfo();
  const tag = $("#bmiTag"); if (tag.dataset.cat) tag.textContent = t("bmi_" + tag.dataset.cat);
}
async function setLang(l) {
  state.lang = l;
  try { localStorage.setItem("hg-lang", l); } catch (e) { /* ignore */ }
  applyI18n();
  await loadSymptoms();
  if (state.payload) { try { state.result = await analyze(state.payload, false); persist(); } catch (e) { /* keep old result */ } }
  route();
}
$("#langBtn").addEventListener("click", () => setLang(state.lang === "en" ? "hi" : "en"));

/* ------------------------------------------------------------ router */
function route() {
  let name = location.hash.replace("#/", "") || "home";
  if (!PAGES.includes(name)) name = "home";
  if (name === "login" && state.user) { location.hash = "#/history"; return; }
  PAGES.forEach((p) => $("#page-" + p).classList.toggle("active", p === name));
  $$(".nav-links a").forEach((a) => {
    const on = a.dataset.page === name;
    a.classList.toggle("active", on);
    on ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current");
  });
  window.scrollTo(0, 0);
  if (name === "results") renderResults();
  if (name === "history") renderHistory();
  if (name === "models") renderModels();
}
window.addEventListener("hashchange", route);

/* ------------------------------------------------------------ account */
function updateAuthUI() {
  const u = state.user;
  $("#loginBtn").hidden = !!u; $("#whoBox").hidden = !u; $("#navHistory").hidden = !u;
  if (u) $("#whoName").textContent = u.name;
}
async function loadMe() { try { state.user = (await (await fetch("/api/me")).json()).user; } catch (e) { state.user = null; } updateAuthUI(); }
$("#logoutBtn").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST", headers: JSONH, body: "{}" });
  state.user = null; updateAuthUI();
  location.hash = "#/home"; route();
});
$$("#authTabs button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
function setTab(tab) {
  state.tab = tab;
  $$("#authTabs button").forEach((x) => x.setAttribute("aria-pressed", x.dataset.tab === tab));
  $("#nameField").hidden = tab !== "signup"; $("#pwHint").hidden = tab !== "signup";
  $("#authPw").autocomplete = tab === "signup" ? "new-password" : "current-password";
  $("#authErr").hidden = true; applyI18n();
}
$("#authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const err = $("#authErr"), btn = $("#authSubmit"); err.hidden = true; btn.disabled = true;
  const body = { email: $("#authEmail").value, password: $("#authPw").value };
  if (state.tab === "signup") body.name = $("#authName").value;
  try {
    const r = await fetch(state.tab === "signup" ? "/api/signup" : "/api/login", { method: "POST", headers: JSONH, body: JSON.stringify(body) });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || t("err_generic"));
    state.user = d.user; updateAuthUI(); $("#authPw").value = "";
    if (state.pendingSave && state.payload) { state.pendingSave = false; try { state.result = await analyze(state.payload, true); persist(); } catch (x) { /* ignore */ } location.hash = "#/results"; }
    else location.hash = "#/history";
    route();
  } catch (x) { err.textContent = x.message === "Failed to fetch" ? t("err_server") : x.message; err.hidden = false; }
  finally { btn.disabled = false; }
});

/* ------------------------------------------------------------ check-up form */
$$("#sex button").forEach((b) => b.addEventListener("click", () => { setSex(b.dataset.v); }));
function setSex(v) { state.sex = v; $$("#sex button").forEach((x) => x.setAttribute("aria-pressed", x.dataset.v === v)); $("#pregField").hidden = v !== "Female"; }

$$("[data-unk]").forEach((cb) => cb.addEventListener("change", () => {
  cb.dataset.unk.split(",").forEach((id) => { const el = $("#" + id); el.disabled = cb.checked; if (cb.checked) { el.value = ""; el.classList.remove("from-report"); } });
  updateEstInfo();
}));
function updateCount() { $("#symCountLi").innerHTML = `<b>${state.symptoms.size}</b> ` + t("sym_count", { n: "" }).replace(/^\s+/, "").trim(); }
function updateEstInfo() {
  const n = $$("[data-unk]").filter((c) => c.checked).length + (!$("#bmi").value && !($("#height").value && $("#weight").value) ? 1 : 0);
  $("#estInfo").innerHTML = n ? t(n === 1 ? "est_one" : "est_n", { n: `<b>${n}</b>` }) : esc(t("est_default"));
}

let bmiTimer;
const bmiCat = (b) => (b < 18.5 ? "Underweight" : b < 25 ? "Normal" : b < 30 ? "Overweight" : "Obese");
function showBmi(v, cat) {
  $("#bmiVal").textContent = v ?? "–";
  const tag = $("#bmiTag"); tag.hidden = !cat; tag.dataset.cat = cat || ""; tag.textContent = cat ? t("bmi_" + cat) : ""; tag.className = "tag " + (cat || "");
}
function updateBmi() {
  clearTimeout(bmiTimer);
  bmiTimer = setTimeout(async () => {
    const typed = parseFloat($("#bmi").value);
    if (typed) { showBmi(typed.toFixed(1), bmiCat(typed)); return updateEstInfo(); }
    const height = parseFloat($("#height").value), weight = parseFloat($("#weight").value);
    if (!height || !weight) { showBmi(null, null); return updateEstInfo(); }
    try {
      const r = await fetch("/api/bmi", { method: "POST", headers: JSONH, body: JSON.stringify({ height, weight }) });
      const d = await r.json();
      d.error ? showBmi(null, null) : showBmi(d.bmi.toFixed(1), d.category);
    } catch (e) { const b = weight / ((height / 100) ** 2); showBmi(b.toFixed(1), bmiCat(b)); }
    updateEstInfo();
  }, 250);
}
["height", "weight", "bmi"].forEach((id) => $("#" + id).addEventListener("input", updateBmi));
$$("input[type=number]").forEach((el) => el.addEventListener("input", () => el.classList.remove("from-report")));

/* symptom chips */
async function loadSymptoms() {
  try {
    state.symList = await (await fetch("/api/symptoms?lang=" + state.lang)).json();
    $("#chips").innerHTML = state.symList.map((s) => `<button type="button" class="chip" data-id="${esc(s.id)}" aria-pressed="${state.symptoms.has(s.id)}">${esc(s.label)}</button>`).join("");
    filterChips();
  } catch (e) { $("#chips").innerHTML = `<p class="muted">${esc(t("err_server"))}</p>`; }
}
function setSymptom(id, on) {
  on ? state.symptoms.add(id) : state.symptoms.delete(id);
  const c = $(`.chip[data-id="${id}"]`); if (c) c.setAttribute("aria-pressed", on);
  updateCount();
}
$("#chips").addEventListener("click", (e) => { const c = e.target.closest(".chip"); if (c) setSymptom(c.dataset.id, c.getAttribute("aria-pressed") !== "true"); });
function filterChips() {
  const q = $("#symSearch").value.trim().toLowerCase();
  const byId = Object.fromEntries(state.symList.map((s) => [s.id, s]));
  $$(".chip").forEach((c) => { const s = byId[c.dataset.id]; c.hidden = !!q && !(s.en.includes(q) || s.hi.includes(q) || s.label.toLowerCase().includes(q)); });
}
$("#symSearch").addEventListener("input", filterChips);

/* reset */
function resetForm() {
  ["age", "height", "weight", "bmi", "sbp", "dbp", "chol", "glucose", "hr", "preg"].forEach((id) => { const e = $("#" + id); e.value = ""; e.disabled = false; e.classList.remove("from-report"); });
  $$("[data-unk]").forEach((c) => (c.checked = false));
  ["cp", "smoking", "alcohol", "activity", "diet", "stress"].forEach((id) => ($("#" + id).selectedIndex = 0));
  ["exang", "family", "prev_ha"].forEach((id) => ($("#" + id).checked = false));
  setSex(""); state.symptoms.clear();
  $$(".chip").forEach((c) => c.setAttribute("aria-pressed", "false"));
  $("#symSearch").value = ""; filterChips();
  $("#upStatus").hidden = true; $("#micSay").hidden = true; $("#reportFile").value = "";
  $("#formErr").hidden = true; showBmi(null, null); updateCount(); updateEstInfo();
}
$("#resetBtn").addEventListener("click", resetForm);

/* collect + send */
function val(id) { const el = $("#" + id); return el.disabled || el.value === "" ? null : el.value; }
function collectPayload() {
  return {
    age: val("age"), sex: state.sex, height: val("height"), weight: val("weight"), bmi: val("bmi"),
    sbp: val("sbp"), dbp: val("dbp"), chol: val("chol"), glucose: val("glucose"), hr: val("hr"),
    cp: $("#cp").value, exang: $("#exang").checked ? 1 : 0, preg: val("preg"),
    smoking: $("#smoking").value, alcohol: $("#alcohol").value, activity: $("#activity").value, diet: $("#diet").value, stress: $("#stress").value,
    family: $("#family").checked ? 1 : 0, prev_ha: $("#prev_ha").checked ? 1 : 0, symptoms: [...state.symptoms],
  };
}
async function analyze(payload, save) {
  const r = await fetch("/api/predict", { method: "POST", headers: JSONH, body: JSON.stringify({ ...payload, lang: state.lang, save }) });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || t("err_generic"));
  return d;
}
$("#submitBtn").addEventListener("click", async () => {
  const err = $("#formErr"), btn = $("#submitBtn");
  const fail = (m) => { err.textContent = m; err.hidden = false; };
  err.hidden = true;
  if (!val("age")) return fail(t("err_age"));
  if (!state.sex) return fail(t("err_sex"));
  const payload = collectPayload();
  btn.disabled = true; btn.textContent = "…";
  try {
    state.result = await analyze(payload, true); state.payload = payload; state.plan = 0; persist();
    location.hash = "#/results";
  } catch (e) { fail(e.message === "Failed to fetch" ? t("err_server") : e.message); }
  finally { btn.disabled = false; btn.textContent = t("btn_check"); }
});

/* ------------------------------------------------------------ report upload (OCR in the browser) */
const PDFJS = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";
const PDFJS_WORKER = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
const TESS = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js";
const loaded = {};
function loadScript(src) {
  return new Promise((res, rej) => {
    if (loaded[src]) return res();
    const s = document.createElement("script"); s.src = src;
    s.onload = () => { loaded[src] = true; res(); }; s.onerror = () => rej(new Error("script"));
    document.head.appendChild(s);
  });
}
/* turns the text of a report into form values (pure function, easy to test) */
function parseReport(raw) {
  const low = String(raw).toLowerCase().replace(/\u00a0/g, " ").replace(/[ \t]+/g, " ");
  const out = {}, n = parseFloat, inr = (v, a, b) => v >= a && v <= b;
  let m = low.match(/(?:bp|b\.p\.?|blood\s*pressure)[^\d]{0,20}(\d{2,3})\s*[\/\\-]\s*(\d{2,3})/) || low.match(/(\d{2,3})\s*\/\s*(\d{2,3})\s*mm\s*hg/) || low.match(/\b(\d{2,3})\s*\/\s*(\d{2,3})\b/);
  if (m) { const a = n(m[1]), b = n(m[2]); if (inr(a, 70, 260) && inr(b, 40, 160) && a > b) { out.sbp = a; out.dbp = b; } }
  for (const g of low.matchAll(/cholesterol([^\d]{0,25})(\d{1,3}(?:\.\d+)?)/g)) {
    if (/hdl|ldl|vldl|ratio/.test(g[1])) continue;
    let v = n(g[2]); if (v < 15) v = Math.round(v * 38.67);
    if (inr(v, 100, 500)) { out.chol = v; break; }
  }
  const gl = (re) => { for (const g of low.matchAll(re)) { if (/hba1c|post|random|pp\b/.test(g[1])) continue; let v = n(g[2]); if (v < 25) v = Math.round(v * 18); if (inr(v, 40, 500)) return v; } return null; };
  const g1 = gl(/(?:fasting\s*(?:blood\s*)?(?:sugar|glucose)|\bfbs\b|\bfbg\b)([^\d]{0,25})(\d{1,3}(?:\.\d+)?)/g) ?? gl(/(?:blood\s*sugar|blood\s*glucose|glucose)([^\d]{0,25})(\d{1,3}(?:\.\d+)?)/g);
  if (g1) out.glucose = g1;
  m = low.match(/(?:pulse(?:\s*rate)?|heart\s*rate|\bhr\b)[^\d]{0,15}(\d{2,3})/);
  if (m && inr(n(m[1]), 30, 220)) out.hr = n(m[1]);
  m = low.match(/height[^\d]{0,12}(\d{1,3}(?:\.\d+)?)\s*(cm|m|ft|feet)?/);
  if (m) { let v = n(m[1]); if (m[2] === "ft" || m[2] === "feet") v *= 30.48; else if (m[2] === "m" || v < 3) v *= 100; if (inr(v, 50, 250)) out.height = Math.round(v); }
  m = low.match(/weight[^\d]{0,12}(\d{1,3}(?:\.\d+)?)\s*(kgs?|lbs?)?/);
  if (m) { let v = n(m[1]); if (/lb/.test(m[2] || "")) v *= 0.4536; if (inr(v, 10, 300)) out.weight = Math.round(v * 10) / 10; }
  m = low.match(/\bage\b[^\d]{0,10}(\d{1,3})/) || low.match(/\b(\d{1,3})\s*(?:yrs?|years?)\b/);
  if (m && inr(n(m[1]), 1, 110)) out.age = n(m[1]);
  m = low.match(/\b(?:sex|gender)\b[^a-z]{0,6}(male|female|m|f)\b/) || low.match(/\b(female|male)\b/);
  if (m) out.sex = m[1][0] === "f" ? "Female" : "Male";
  return out;
}
function applyReport(f) {
  const found = [];
  const put = (id, v) => { const el = $("#" + id); el.disabled = false; el.value = v; el.classList.add("from-report"); };
  const untick = (id) => $$("[data-unk]").forEach((c) => { if (c.dataset.unk.split(",").includes(id)) c.checked = false; });
  if (f.age) { put("age", f.age); found.push(t("fl_age") + " " + f.age); }
  if (f.sex) { setSex(f.sex); found.push(t("fl_sex") + " " + (f.sex === "Male" ? t("sex_m") : t("sex_f"))); }
  if (f.height) { put("height", f.height); found.push(t("fl_height") + " " + f.height); }
  if (f.weight) { put("weight", f.weight); found.push(t("fl_weight") + " " + f.weight); }
  if (f.sbp) { untick("sbp"); put("sbp", f.sbp); put("dbp", f.dbp); found.push(t("fl_bp") + ` ${f.sbp}/${f.dbp}`); }
  if (f.chol) { untick("chol"); put("chol", f.chol); found.push(t("fl_chol") + " " + f.chol); }
  if (f.glucose) { untick("glucose"); put("glucose", f.glucose); found.push(t("fl_glucose") + " " + f.glucose); }
  if (f.hr) { untick("hr"); put("hr", f.hr); found.push(t("fl_hr") + " " + f.hr); }
  updateBmi(); updateEstInfo();
  return found;
}
async function readFileText(file, progress) {
  if (file.type === "application/pdf" || /\.pdf$/i.test(file.name)) {
    await loadScript(PDFJS); pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER;
    const pdf = await pdfjsLib.getDocument({ data: await file.arrayBuffer() }).promise;
    let text = "";
    for (let p = 1; p <= Math.min(pdf.numPages, 5); p++) { const c = await (await pdf.getPage(p)).getTextContent(); text += c.items.map((i) => i.str).join(" ") + "\n"; }
    if (text.trim().length < 20) throw new Error("scanned");
    return text;
  }
  await loadScript(TESS);
  const r = await Tesseract.recognize(file, "eng", { logger: (m) => { if (m.status === "recognizing text") progress(Math.round(m.progress * 100)); } });
  return r.data.text;
}
$("#reportFile").addEventListener("change", async (e) => {
  const file = e.target.files[0], box = $("#upStatus"); if (!file) return;
  const show = (m, cls) => { box.textContent = m; box.className = "up-status " + (cls || ""); box.hidden = false; };
  show(t("up_reading"));
  try {
    const text = await readFileText(file, (p) => show(t("up_pct", { p })));
    const found = applyReport(parseReport(text));
    found.length ? show(t("up_found", { list: found.join(", ") }), "ok") : show(t("up_none"), "warn");
  } catch (x) { show(x.message === "scanned" ? t("up_scanned") : t("up_fail"), "warn"); }
});

/* ------------------------------------------------------------ voice input */
const SYN = {
  "fever": "high_fever", "high temperature": "high_fever", "tired": "fatigue", "tiredness": "fatigue", "weakness": "fatigue", "throwing up": "vomiting", "vomit": "vomiting",
  "loose motion": "diarrhoea", "body pain": "muscle_pain", "body ache": "muscle_pain", "breathing problem": "breathlessness", "shortness of breath": "breathlessness",
  "difficulty breathing": "breathlessness", "stomach ache": "stomach_pain", "tummy pain": "stomach_pain", "sneezing": "continuous_sneezing", "sore throat": "throat_irritation",
  "dizzy": "dizziness", "nauseous": "nausea", "rash": "skin_rash", "itchy": "itching", "chest tightness": "chest_pain", "back ache": "back_pain", "neck ache": "neck_pain",
  "blurry vision": "blurred_and_distorted_vision", "yellow eyes": "yellowing_of_eyes", "yellow skin": "yellowish_skin", "frequent urination": "polyuria",
  "burning urination": "burning_micturition", "pain while urinating": "burning_micturition", "constipated": "constipation", "anxious": "anxiety", "depressed": "depression",
  "बुखार": "high_fever", "सिरदर्द": "headache", "सर दर्द": "headache", "सिर में दर्द": "headache", "खांसी": "cough", "खाँसी": "cough", "उल्टी": "vomiting", "थकान": "fatigue",
  "कमजोरी": "fatigue", "दस्त": "diarrhoea", "सीने में दर्द": "chest_pain", "पेट दर्द": "stomach_pain", "पेट में दर्द": "stomach_pain", "खुजली": "itching",
  "सांस फूल": "breathlessness", "सांस लेने में": "breathlessness", "चक्कर": "dizziness", "जी मिचल": "nausea", "ठंड": "chills", "पसीना": "sweating",
  "जोड़ों में दर्द": "joint_pain", "जोड़ों का दर्द": "joint_pain", "गले में खराश": "throat_irritation", "गले में दर्द": "throat_irritation", "पीठ दर्द": "back_pain",
  "पीठ में दर्द": "back_pain", "मांसपेशियों में दर्द": "muscle_pain", "बदन दर्द": "muscle_pain", "शरीर में दर्द": "muscle_pain", "कब्ज": "constipation", "छींक": "continuous_sneezing",
  "नाक बह": "runny_nose", "पेशाब में जलन": "burning_micturition", "धुंधला": "blurred_and_distorted_vision",
};
function matchSymptoms(text) {
  const low = String(text).toLowerCase(), ids = new Set(), known = new Set(state.symList.map((s) => s.id));
  for (const k in SYN) if (low.includes(k) && known.has(SYN[k])) ids.add(SYN[k]);
  state.symList.forEach((s) => {
    const words = s.en.split(" ").filter((w) => w.length > 2);
    if (low.includes(s.en) || (words.length > 1 && words.every((w) => low.includes(w))) || (s.hi && low.includes(s.hi.toLowerCase()))) ids.add(s.id);
  });
  return [...ids];
}
function setupMic() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition, btn = $("#micBtn"), say = (m) => { $("#micSay").textContent = m; $("#micSay").hidden = false; };
  if (!SR) { btn.classList.add("off"); btn.addEventListener("click", () => say(t("mic_unsupported"))); return; }
  let rec = null, on = false;
  btn.addEventListener("click", () => {
    if (on) { rec.stop(); return; }
    rec = new SR(); rec.lang = state.lang === "hi" ? "hi-IN" : "en-IN"; rec.interimResults = false; rec.maxAlternatives = 1;
    rec.onstart = () => { on = true; btn.classList.add("live"); $("#micTxt").textContent = t("mic_listening"); };
    rec.onend = () => { on = false; btn.classList.remove("live"); $("#micTxt").textContent = t("mic_btn"); };
    rec.onerror = () => say(t("mic_error"));
    rec.onresult = (e) => {
      const text = e.results[0][0].transcript, ids = matchSymptoms(text);
      ids.forEach((id) => setSymptom(id, true));
      const names = ids.map((id) => (state.symList.find((s) => s.id === id) || {}).label);
      say(t("mic_heard", { t: text }) + " · " + (ids.length ? t("mic_added", { list: names.join(", ") }) : t("mic_none")));
    };
    try { rec.start(); } catch (x) { say(t("mic_error")); }
  });
}

/* ------------------------------------------------------------ results */
const COLORS = { Low: "#3C9D6B", Intermediate: "#D9A441", High: "#D9534F" };
const SCORE_COLORS = { Good: "#3C9D6B", Fair: "#D9A441", Attention: "#D9534F" };
function gauge(pct, level, sub) {
  const L = 251.33, dash = (Math.max(pct, 1) / 100 * L).toFixed(1);
  return `<svg viewBox="0 0 200 120" role="img" aria-label="${esc(sub)} ${pct}%, ${esc(t("lv_" + level))}">
    <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="#E1ECE8" stroke-width="16" stroke-linecap="round"/>
    <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="${COLORS[level]}" stroke-width="16" stroke-linecap="round" stroke-dasharray="${dash} ${L}"/>
    <text x="100" y="92" text-anchor="middle" font-size="32" font-weight="500" fill="#0B3B38" font-family="Georgia,serif">${pct}%</text></svg>`;
}
function ring(v, label) {
  const C = 326.7;
  return `<svg viewBox="0 0 120 120" role="img" aria-label="${esc(t("score_h"))} ${v}"><circle cx="60" cy="60" r="52" fill="none" stroke="#E1ECE8" stroke-width="12"/>
    <circle cx="60" cy="60" r="52" fill="none" stroke="${SCORE_COLORS[label]}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${(C * (1 - v / 100)).toFixed(1)}" transform="rotate(-90 60 60)"/>
    <text x="60" y="68" text-anchor="middle" font-size="34" font-weight="500" fill="#0B3B38" font-family="Georgia,serif">${v}</text></svg>`;
}
const mapsLink = (q) => `https://www.google.com/maps/search/?api=1&query=${enc(q)}`;
function learnLinks(it) {
  const hi = state.lang === "hi", nm = hi ? it.name : it.query;
  const a = (href, label) => `<a class="ext" href="${href}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`;
  return `<div class="learn"><h4>${esc(t("learn_h"))}</h4><div class="learn-links">
    ${a(`https://${hi ? "hi" : "en"}.wikipedia.org/wiki/Special:Search?search=${enc(nm)}`, t("l_wiki"))}
    ${a(`https://www.youtube.com/results?search_query=${enc(nm + (hi ? " लक्षण और उपाय डॉक्टर" : " symptoms causes treatment explained by doctor"))}`, t("l_yt"))}
    ${a(`https://www.google.com/search?q=${enc(nm + (hi ? " लक्षण इलाज" : " symptoms causes treatment"))}`, t("l_google"))}
    ${a(`https://www.nhs.uk/search/results?q=${enc(it.query)}`, t("l_nhs"))}
    ${a(mapsLink(it.sp + " near me"), t("l_doc", { sp: it.sp }))}</div><p class="sub-note">${esc(t("learn_note"))}</p></div>`;
}
function planHtml(p) {
  return `<div class="plan-cols"><div><h4>${esc(t("prec_h"))}</h4><ul>${p.pre.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
    <div><h4>${esc(t("diet_h"))}</h4><ul>${p.diet.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div></div>${learnLinks(p)}`;
}
function whyList(r) {
  if (!r.why.length) return `<p class="muted">${esc(t("why_none"))}</p>`;
  const max = Math.max(...r.why.map((w) => Math.abs(w.impact)));
  return `<ul class="why">${r.why.map((w) => {
    const up = w.impact > 0, wd = Math.max(6, Math.abs(w.impact) / max * 100).toFixed(0);
    return `<li><div class="why-top"><span>${esc(w.factor)} <small>${esc(w.value)}</small></span><b class="${up ? "up" : "down"}">${up ? "+" : ""}${w.impact} ${esc(t("pts"))}</b></div>
      <div class="bar"><i class="${up ? "High" : "Low"}" style="width:0" data-w="${wd}"></i></div></li>`;
  }).join("")}</ul>`;
}
function chips(list, cls) { return list.length ? `<div class="mini-chips">${list.map((x) => `<span class="mchip ${cls}">${esc(x)}</span>`).join("")}</div>` : ""; }

function renderResults() {
  const box = $("#resultsBody"), d = state.result;
  if (!d) {
    box.innerHTML = `<div class="card empty"><h2>${esc(t("no_results"))}</h2><p>${esc(t("no_results_p"))}</p><a class="btn" href="#/checkup">${esc(t("btn_start"))}</a></div>`;
    return;
  }
  const items = [...d.diseases.map((x) => ({ name: x.name, query: x.disease, pre: x.precautions, diet: x.diet, sp: x.specialist })),
                 ...d.risks.map((x) => ({ name: x.name, query: x.key === "heart" ? "heart disease" : "diabetes", pre: x.precautions, diet: x.diet, sp: x.specialist }))];
  if (state.plan >= items.length) state.plan = 0;
  const alert = d.alerts.length ? `<div class="alert" role="alert"><div><b>${esc(t("alert_h"))}</b><p>${esc(t("alert_p", { names: d.alerts.join(", ") }))}</p>
      <div class="alert-actions"><a class="btn small danger" href="tel:112">${esc(t("btn_call"))}</a><a class="btn small ghost" target="_blank" rel="noopener noreferrer" href="${mapsLink("emergency hospital near me")}">${esc(t("btn_er"))}</a></div></div></div>` : "";
  const est = d.estimated.length ? `<p class="note">${esc(t("est_note", { list: d.estimated.join(", ") }))} <a href="#/checkup">${esc(t("enter_real"))}</a></p>` : "";
  const save = d.saved || state.user ? (d.saved ? `<p class="note ok">${esc(t("saved_ok"))}</p>` : "") : `<p class="note info">${esc(t("save_login"))} <a href="#/login" id="saveLoginLink">${esc(t("btn_login"))}</a></p>`;
  const gauges = d.risks.map((r) => `<div class="card gauge-card"><h3>${esc(r.name)}</h3>${gauge(r.risk, r.level, r.name)}
      <div class="tags"><span class="tag ${r.level}">${esc(t("risk_tag", { lv: t("lv_" + r.level) }))}</span><span class="tag conf">${esc(t("cert_tag", { c: t("cc_" + r.certainty) }))}</span></div>
      <p class="sub-note">${esc(t("conf_small", { c: r.confidence }))}${r.clinical_model !== undefined ? " · " + esc(t("gauge_note", { a: r.clinical_model, b: r.lifestyle_model })) : ""}</p></div>`).join("");
  const dis = d.diseases.length ? d.diseases.map((x) => `<div class="dis"><div class="dis-top"><b>${esc(x.name)}</b><span class="tag ${x.stage}">${esc(t("risk_tag", { lv: t("lv_" + x.stage) }))}</span></div>
      <div class="bar" role="img" aria-label="${x.score}%"><i class="${x.stage}" style="width:0" data-w="${x.score}"></i></div>
      <small>${esc(t("cond_small", { p: x.confidence, share: x.share, m: x.match }))}</small>
      <div class="dis-meta"><span class="tag conf">${esc(t("cert_tag", { c: t("cc_" + x.certainty) }))}</span><small>${esc(t("urg_" + x.urgency))}</small></div></div>`).join("")
    : `<p class="muted">${esc(t("cond_none"))} <a href="#/checkup">${esc(t("add_sym"))}</a></p>`;
  const whyDis = d.diseases.map((x) => `<div class="why-dis"><b>${esc(x.name)}</b>
      <p class="sub-note">${esc(t("matched_h"))}</p>${chips(x.matched, "on")}
      ${x.missing.length ? `<p class="sub-note">${esc(t("missing_h"))}</p>${chips(x.missing, "off")}` : ""}
      ${x.certainty !== "High" ? `<p class="sub-note hint">${esc(t("cond_hint"))}</p>` : ""}</div>`).join("");
  const why = `<div class="card"><h3>${esc(t("why_h"))}</h3><p class="muted" style="margin-bottom:14px">${esc(t("why_p"))}</p>
      ${d.risks.map((r) => `<h4 class="why-title">${esc(r.name)}</h4>${whyList(r)}`).join("")}${whyDis}</div>`;
  const tabs = items.map((p, i) => `<button type="button" data-i="${i}" aria-pressed="${i === state.plan}">${esc(p.name)}</button>`).join("");
  const rows = (id, label, min, max, step, v) => `<label class="wi-row"><span>${esc(label)} <output id="o_${id}">${v}</output></span><input type="range" id="w_${id}" min="${Math.min(min, v)}" max="${Math.max(max, v)}" step="${step}" value="${v}"></label>`;
  const sel = (id, label, opts, cur) => `<label class="wi-row"><span>${esc(label)}</span><select id="w_${id}">${opts.map((o) => `<option value="${o}" ${o === cur ? "selected" : ""}>${esc(t("o_" + o))}</option>`).join("")}</select></label>`;
  const P = state.payload || {};
  const whatif = state.payload ? `<div class="card" id="whatif"><h3>${esc(t("whatif_h"))}</h3><p class="muted" style="margin-bottom:14px">${esc(t("whatif_p"))}</p>
      <div class="wi-grid">${rows("bmi", t("wi_bmi"), 15, 45, 0.5, d.bmi.value)}${rows("sbp", t("wi_sbp"), 90, 200, 1, d.vitals.sbp)}${rows("chol", t("wi_chol"), 120, 320, 1, d.vitals.chol)}${rows("glucose", t("wi_glucose"), 70, 250, 1, d.vitals.glucose)}
      ${sel("smoking", t("wi_smoking"), ["Never", "Former", "Current"], P.smoking || "Never")}${sel("activity", t("wi_activity"), ["Sedentary", "Moderate", "Active"], P.activity || "Moderate")}</div>
      <div id="wiRes" class="wi-res" aria-live="polite"></div><button type="button" class="btn ghost small" id="wiReset">${esc(t("wi_reset"))}</button></div>` : "";
  box.innerHTML = `
    <div class="page-head"><h1>${esc(t("res_h1"))}</h1><p>${esc(t("res_sub", { bmi: d.bmi.value, cat: t("bmi_" + d.bmi.category), n: d.n_symptoms }))}</p></div>
    ${alert}${est}${save}
    <div class="res-grid">
      <div class="gauges">
        <div class="card score-card"><div class="ring">${ring(d.score.value, d.score.label)}</div><div><h3>${esc(t("score_h"))}</h3><span class="tag ${d.score.label === "Good" ? "Low" : d.score.label === "Fair" ? "Intermediate" : "High"}">${esc(t("score_" + d.score.label))}</span><p class="sub-note">${esc(t("score_note"))}</p></div></div>
        ${gauges}${whatif}
      </div>
      <div class="gauges">
        <div class="card"><h3 style="margin-bottom:18px">${esc(t("cond_h"))}</h3>${dis}</div>
        ${why}
        <div class="card"><h3>${esc(t("plan_h"))}</h3><p class="muted">${esc(t("plan_p"))}</p><div class="plan-tabs" id="planTabs">${tabs}</div><div id="planBody">${planHtml(items[state.plan])}</div></div>
      </div>
    </div>
    <div class="actions"><button class="btn" id="pdfBtn" type="button">${esc(t("btn_pdf"))}</button><button class="btn ghost" id="printBtn" type="button">${esc(t("btn_print"))}</button><button class="btn ghost" id="newBtn" type="button">${esc(t("btn_new"))}</button></div>
    <p class="sub-note" id="pdfMsg">${esc(t("pdf_note"))}</p>
    <p class="disclaimer">${esc(t("disc_res"))}</p>`;
  requestAnimationFrame(() => $$(".bar > i[data-w]").forEach((i) => (i.style.width = i.dataset.w + "%")));
  $("#planTabs").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    state.plan = +b.dataset.i; $$("#planTabs button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    $("#planBody").innerHTML = planHtml(items[state.plan]);
  });
  $("#printBtn").addEventListener("click", () => window.print());
  $("#newBtn").addEventListener("click", () => { resetForm(); state.result = null; state.payload = null; persist(); location.hash = "#/checkup"; });
  $("#pdfBtn").addEventListener("click", () => downloadPdf(state.payload));
  const sl = $("#saveLoginLink"); if (sl) sl.addEventListener("click", () => (state.pendingSave = true));
  if (state.payload) setupWhatIf(d);
}
async function downloadPdf(payload) {
  const msg = $("#pdfMsg") || { textContent: "" };
  try {
    const r = await fetch("/api/report", { method: "POST", headers: JSONH, body: JSON.stringify(payload) });
    if (!r.ok) throw new Error("pdf");
    const url = URL.createObjectURL(await r.blob()), a = document.createElement("a");
    a.href = url; a.download = "HealthGuard_Report.pdf"; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 3000);
  } catch (e) { msg.textContent = t("pdf_err"); }
}

/* what-if simulator */
function setupWhatIf(d) {
  const ids = ["bmi", "sbp", "chol", "glucose"], base = {}; ids.forEach((i) => (base[i] = $("#w_" + i).value));
  const baseSel = { smoking: $("#w_smoking").value, activity: $("#w_activity").value };
  let timer, seq = 0;
  const row = (label, now, nw, isScore) => {
    const delta = nw - now, good = isScore ? delta >= 0 : delta <= 0;
    return `<div class="wi-line"><span>${esc(label)}</span><span>${now}${isScore ? "" : "%"} → <b>${nw}${isScore ? "" : "%"}</b> <em class="${delta === 0 ? "" : good ? "down" : "up"}">${delta > 0 ? "+" : ""}${delta}</em></span></div>`;
  };
  async function run() {
    ids.forEach((i) => ($("#o_" + i).textContent = $("#w_" + i).value));
    const my = ++seq;
    const body = { ...state.payload, bmi: $("#w_bmi").value, sbp: $("#w_sbp").value, dbp: d.vitals.dbp, chol: $("#w_chol").value, glucose: $("#w_glucose").value, hr: d.vitals.hr,
                   smoking: $("#w_smoking").value, activity: $("#w_activity").value };
    try {
      const r = await (await fetch("/api/whatif", { method: "POST", headers: JSONH, body: JSON.stringify(body) })).json();
      if (my !== seq || r.error) return;
      $("#wiRes").innerHTML = row(t("wi_heart"), d.risks[0].risk, r.heart.risk) + row(t("wi_diab"), d.risks[1].risk, r.diabetes.risk) + row(t("wi_score"), d.score.value, r.score.value, true);
    } catch (e) { /* ignore */ }
  }
  const go = () => { clearTimeout(timer); timer = setTimeout(run, 180); };
  $$("#whatif input, #whatif select").forEach((el) => el.addEventListener("input", go));
  $("#wiReset").addEventListener("click", () => { ids.forEach((i) => ($("#w_" + i).value = base[i])); $("#w_smoking").value = baseSel.smoking; $("#w_activity").value = baseSel.activity; run(); });
  run();
}

/* ------------------------------------------------------------ history */
function trendSvg(items) {
  const pts = [...items].reverse(), W = 640, H = 190, x = (i) => 40 + (pts.length === 1 ? 0.5 : i / (pts.length - 1)) * (W - 70), y = (v) => 160 - v * 1.4;
  const line = (key, color) => `<polyline fill="none" stroke="${color}" stroke-width="3" stroke-linejoin="round" points="${pts.map((p, i) => `${x(i)},${y(p.result.risks[key].risk)}`).join(" ")}"/>` +
    pts.map((p, i) => `<circle cx="${x(i)}" cy="${y(p.result.risks[key].risk)}" r="4" fill="${color}"/>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" class="trend" role="img" aria-label="${esc(t("hist_trend"))}">
    ${[0, 50, 100].map((g) => `<line x1="40" x2="${W - 20}" y1="${y(g)}" y2="${y(g)}" stroke="#E1ECE8"/><text x="8" y="${y(g) + 4}" font-size="11" fill="#4F6B67">${g}%</text>`).join("")}
    ${line(0, "#D9534F")}${line(1, "#0B5D57")}</svg>
    <div class="legend"><span><i style="background:#D9534F"></i>${esc(t("hist_heart"))}</span><span><i style="background:#0B5D57"></i>${esc(t("hist_diab"))}</span></div>`;
}
async function renderHistory() {
  const box = $("#historyBody");
  if (!state.user) { box.innerHTML = `<div class="card empty"><h2>${esc(t("hist_h1"))}</h2><p>${esc(t("hist_login"))}</p><a class="btn" href="#/login">${esc(t("btn_login"))}</a></div>`; return; }
  box.innerHTML = `<div class="page-head"><h1>${esc(t("hist_h1"))}</h1><p>${esc(t("hist_p"))}</p></div><p class="muted">…</p>`;
  let items = [];
  try { items = (await (await fetch("/api/history")).json()).items || []; } catch (e) { /* ignore */ }
  const head = `<div class="page-head"><h1>${esc(t("hist_h1"))}</h1><p>${esc(t("hist_p"))}</p></div>`;
  if (!items.length) { box.innerHTML = head + `<div class="card empty"><p>${esc(t("hist_empty"))}</p><a class="btn" href="#/checkup">${esc(t("btn_start"))}</a></div>`; return; }
  const fmtDate = (s) => new Date(s + "Z").toLocaleString(state.lang === "hi" ? "hi-IN" : "en-IN", { dateStyle: "medium", timeStyle: "short" });
  box.innerHTML = head + (items.length > 1 ? `<div class="card" style="margin-bottom:24px"><h3 style="margin-bottom:10px">${esc(t("hist_trend"))}</h3>${trendSvg(items)}</div>` : "") +
    `<div class="hist-list">${items.map((it) => {
      const r = it.result, top = r.diseases[0];
      return `<div class="card hist"><div><b>${esc(fmtDate(it.created))}</b><p class="muted">${esc(top ? top.name : t("hist_none_sym"))}</p></div>
        <div class="hist-nums"><span>${esc(t("hist_heart"))} <b>${r.risks[0].risk}%</b></span><span>${esc(t("hist_diab"))} <b>${r.risks[1].risk}%</b></span><span>${esc(t("hist_score"))} <b>${r.score.value}</b></span></div>
        <div class="hist-actions"><button class="btn small" data-act="view" data-id="${it.id}">${esc(t("hist_view"))}</button><button class="btn small ghost" data-act="pdf" data-id="${it.id}">${esc(t("hist_pdf"))}</button><button class="btn small ghost" data-act="del" data-id="${it.id}">${esc(t("hist_del"))}</button></div></div>`;
    }).join("")}</div>`;
  box.onclick = async (e) => {
    const b = e.target.closest("button[data-act]"); if (!b) return;
    const it = items.find((x) => x.id === +b.dataset.id); if (!it) return;
    if (b.dataset.act === "view") {
      try { state.payload = it.payload; state.result = await analyze(it.payload, false); state.plan = 0; persist(); location.hash = "#/results"; } catch (x) { /* ignore */ }
    } else if (b.dataset.act === "pdf") downloadPdf(it.payload);
    else if (confirm(t("hist_conf_del"))) { await fetch("/api/history/" + it.id, { method: "DELETE" }); renderHistory(); }
  };
}

/* ------------------------------------------------------------ models page */
const pc = (v) => (v * 100).toFixed(1) + "%";
function modelRows(algos, field, best) {
  return Object.entries(algos).sort((a, b) => b[1][field] - a[1][field]).map(([n, m]) =>
    `<div class="m-row ${n === best ? "best" : ""}"><span>${esc(n)}</span><div class="bar"><i style="width:${(m[field] * 100).toFixed(1)}%"></i></div><span>${pc(m[field])}</span></div>`).join("");
}
async function renderModels() {
  const box = $("#modelsBody");
  if (!state.metrics) {
    try { state.metrics = await (await fetch("/api/metrics")).json(); }
    catch (e) { box.innerHTML = `<p class="muted">${esc(t("err_server"))}</p>`; return; }
  }
  box.innerHTML = Object.values(state.metrics).map((m) => {
    const sym = m.final_test_file_accuracy !== undefined;
    const extra = sym ? `<p class="m-sub">${esc(t("m_partial"))}</p>${modelRows(m.algorithms, "partial_symptom_accuracy", m.best)}`
      : `<p class="m-note">${esc(t("m_test", { a: m.best, acc: pc(m.test_accuracy), f1: pc(m.test_f1) }))}</p>`;
    return `<div class="card"><h3>${esc(m.title)}<span class="best-tag">${esc(t("m_best", { a: m.best }))}</span></h3>
      <p class="m-sub">${esc(t(sym ? "m_cv_all" : "m_cv"))} · ${esc(t("m_n", { n: Object.keys(m.algorithms).length }))}</p>${modelRows(m.algorithms, "cv_accuracy", m.best)}${extra}
      <p class="m-note">${esc(m.note || "")}</p></div>`;
  }).join("");
}

/* ------------------------------------------------------------ start */
window.HG = { parseReport, applyReport, matchSymptoms, state, t };   // used by the automatic tests
(async function start() {
  applyI18n(); setupMic();
  await Promise.all([loadMe(), loadSymptoms()]);
  fetch("/api/metrics").then((r) => r.json()).then((m) => (state.metrics = m)).catch(() => {});
  route();
})();
