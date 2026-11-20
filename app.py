"""
app.py  -  HealthGuard backend (Flask)

Flow:  Browser (HTML/CSS/JS)  --fetch POST /api/predict-->  Flask  -->  ML models (.pkl)  -->  JSON  -->  Browser
Run :  python app.py   then open http://127.0.0.1:5000
"""
import io
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)                       # create the web application
BASE = os.path.dirname(os.path.abspath(__file__))


def path(*p):
    return os.path.join(BASE, *p)


# ------------------------------------------------------------------ 0. SECURITY SETTINGS
def secret_key():
    """Key that signs the login cookie. Created once and saved, so logins survive a restart."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    f = path(".secret_key")
    if not os.path.exists(f):
        open(f, "w").write(secrets.token_hex(32))
    return open(f).read().strip()


app.secret_key = secret_key()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  PERMANENT_SESSION_LIFETIME=timedelta(days=14))


# ------------------------------------------------------------------ 1. LOAD EVERYTHING ONCE (at start-up)
def load_all():
    global sym_bundle, heart_clin, heart_life, diab_bundle, profiles, KB, HI, METRICS
    sym_bundle = joblib.load(path("models", "symptom_model.pkl"))        # Random Forest for 41 diseases
    heart_clin = joblib.load(path("models", "heart_clinical.pkl"))       # heart.csv model
    heart_life = joblib.load(path("models", "heart_lifestyle.pkl"))      # lifestyle + vitals model
    diab_bundle = joblib.load(path("models", "diabetes.pkl"))            # diabetes model
    profiles = json.load(open(path("models", "symptom_profiles.json")))  # list of symptoms + typical symptoms per disease
    KB = json.load(open(path("data", "knowledge.json")))                 # English precautions + diet + doctor type
    HI = json.load(open(path("data", "hindi.json"), encoding="utf-8"))   # Hindi names, precautions, diet
    METRICS = json.load(open(path("models", "metrics.json")))            # accuracy of every algorithm


try:
    load_all()
except Exception as err:   # e.g. the .pkl files were saved with a different scikit-learn version
    import subprocess
    import sys
    print("Could not load saved models (%s). Re-training them now, this takes a few minutes..." % err)
    subprocess.run([sys.executable, "train_models.py"], cwd=BASE, check=True)
    load_all()

SYMPTOMS = profiles["symptoms"]
PROFILES = profiles["profiles"]

# ------------------------------------------------------------------ 2. DATABASE (SQLite, built into Python)
DB_PATH = path("healthguard.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, created TEXT NOT NULL,
    payload TEXT NOT NULL, result TEXT NOT NULL);
"""


def connect():
    """Open the database. The tables are created if they are missing (for example if the file was deleted)."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def rows(sql, args=()):
    con = connect()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def run(sql, args=()):
    con = connect()
    try:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


connect().close()                                           # create the database file and tables at start-up

# ------------------------------------------------------------------ 3. SMALL HELPER FUNCTIONS
LABEL_FIX = {"foul_smell_ofurine": "foul smell of urine", "dischromic_patches": "discoloured patches",
             "scurring": "skin scarring", "toxic_look_(typhos)": "toxic look", "spotting_urination": "spotting while urinating",
             "extra_marital_contacts": "unprotected sexual contact", "cold_hands_and_feets": "cold hands and feet",
             "swollen_extremeties": "swollen hands and feet", "blackheads": "blackheads", "yellow_crust_ooze": "yellow crust and ooze"}
RISK_TITLE = {"heart": ("Heart disease risk", "हृदय रोग का जोखिम"), "diabetes": ("Diabetes risk", "मधुमेह का जोखिम")}
EST_HI = {"BMI": "बीएमआई", "top BP": "ऊपरी BP", "bottom BP": "निचला BP", "cholesterol": "कोलेस्ट्रॉल",
          "blood sugar": "ब्लड शुगर", "heart rate": "हृदय गति"}


def label(s, lang="en"):
    """'skin_rash' -> 'skin rash' (or its Hindi name)"""
    if lang == "hi" and s in HI["symptoms"]:
        return HI["symptoms"][s]
    return LABEL_FIX.get(s, s.replace("_", " ")).strip()


def calc_bmi(height_cm, weight_kg):
    """BMI = weight (kg) / height (m)^2"""
    return weight_kg / ((height_cm / 100) ** 2)


def bmi_category(b):
    return "Underweight" if b < 18.5 else "Normal" if b < 25 else "Overweight" if b < 30 else "Obese"


def level(p):
    """Turn a probability (0 to 1) into a 3-stage risk level."""
    return "Low" if p < 0.30 else "Intermediate" if p < 0.60 else "High"


def num(data, key, lo, hi):
    """Read a number from the request. Empty -> None (unknown). Out of range -> error."""
    v = data.get(key)
    if v in (None, "", "null"):
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a number")
    if not lo <= v <= hi:
        raise ValueError(f"{key} must be between {lo} and {hi}")
    return v


def estimate(age, bmi):
    """When the user does not know a value we estimate a typical one from age and BMI (rough averages)."""
    excess = max(bmi - 22, 0)
    clip = lambda v, a, b: float(min(max(v, a), b))
    return {"sbp": clip(108 + 0.45 * (age - 20) + 0.8 * excess, 95, 160),
            "dbp": clip(68 + 0.25 * (age - 20) + 0.4 * excess, 60, 100),
            "chol": clip(170 + 0.6 * (age - 20) + 1.2 * excess, 150, 260),
            "glucose": clip(88 + 0.2 * (age - 20) + 0.8 * excess, 80, 125), "hr": 72.0}


def parse(d):
    """Validate the form and fill unknown values. Returns (values, estimated names, selected symptoms)."""
    age = num(d, "age", 1, 110)
    if age is None:
        raise ValueError("Age is required")
    sex = d.get("sex", "")
    if sex not in ("Male", "Female"):
        raise ValueError("Select your sex")
    h, w, bmi = num(d, "height", 50, 250), num(d, "weight", 10, 300), num(d, "bmi", 10, 70)
    if bmi is None and h and w:
        bmi = calc_bmi(h, w)                                # calculate BMI if the user does not know it
    given = {"sbp": num(d, "sbp", 70, 260), "dbp": num(d, "dbp", 40, 160), "chol": num(d, "chol", 80, 500),
             "glucose": num(d, "glucose", 40, 500), "hr": num(d, "hr", 30, 220)}
    estimated = []
    if bmi is None:
        bmi = 25.0
        estimated.append("BMI")
    est = estimate(age, bmi)
    vals = {"age": age, "sex": sex, "bmi": bmi}
    for key, name in (("sbp", "top BP"), ("dbp", "bottom BP"), ("chol", "cholesterol"), ("glucose", "blood sugar"), ("hr", "heart rate")):
        if given[key] is None:
            vals[key] = est[key]
            estimated.append(name)
        else:
            vals[key] = given[key]
    pick = lambda k, ok, default: d.get(k) if d.get(k) in ok else default
    yes = lambda k: 1 if d.get(k) in (1, "1", True, "yes") else 0
    vals.update({
        "smoking": pick("smoking", ("Never", "Former", "Current"), "Never"),
        "alcohol": pick("alcohol", ("None", "Low", "Moderate", "High"), "None"),
        "activity": pick("activity", ("Sedentary", "Moderate", "Active"), "Moderate"),
        "diet": pick("diet", ("Healthy", "Average", "Unhealthy"), "Average"),
        "stress": pick("stress", ("Low", "Medium", "High"), "Medium"),
        "family": yes("family"), "prev_ha": yes("prev_ha"), "exang": yes("exang"),
        "cp": int(num(d, "cp", 0, 3) if num(d, "cp", 0, 3) is not None else 2),
        "preg": int(num(d, "preg", 0, 20) or 0) if sex == "Female" else 0})
    selected = [s for s in (d.get("symptoms") or []) if s in SYMPTOMS]
    return vals, estimated, selected


# ------------------------------------------------------------------ 4. PREDICTION FUNCTIONS
def certainty_from_p(p):
    return "High" if p >= 0.60 else "Medium" if p >= 0.30 else "Low"


def predict_symptoms(selected, lang):
    """Symptoms -> top diseases with confidence, certainty, risk stage, matched and missing symptoms."""
    if not selected:
        return []
    x = np.zeros((1, len(SYMPTOMS)))
    for s in selected:
        x[0, SYMPTOMS.index(s)] = 1
        if s == "fluid_overload":                           # the dataset has this column twice
            x[0, SYMPTOMS.index("fluid_overload.1")] = 1
    model = sym_bundle["model"]
    proba = model.predict_proba(x)[0]                       # probability for every disease
    out = []
    for i in np.argsort(proba)[::-1][:4]:
        p = float(proba[i])
        if p < 0.04 and out:
            continue
        disease = model.classes_[i]
        typical = PROFILES.get(disease, [])
        matched = [s for s in typical if s in selected]
        missing = [s for s in typical if s not in selected]
        coverage = len(matched) / len(typical) if typical else 0
        score = 0.6 * p + 0.4 * coverage                    # risk score = model probability + symptom match
        info = KB["diseases"].get(disease, {})
        hi = HI["diseases"].get(disease, {})
        src = hi if lang == "hi" and hi else info
        out.append({
            "disease": disease, "name": hi.get("name", disease) if lang == "hi" else disease,
            "confidence": round(min(p, 0.99) * 100, 1), "certainty": certainty_from_p(p), "p": p,
            "match": round(coverage * 100), "matched": [label(s, lang) for s in matched],
            "missing": [label(s, lang) for s in missing[:5]],
            "stage": "High" if score >= 0.55 else "Intermediate" if score >= 0.30 else "Low", "score": round(score * 100),
            "urgency": info.get("urgency", "routine"), "specialist": info.get("specialist", "general physician"),
            "precautions": src.get("precautions", []), "diet": src.get("diet", [])})
    out = out[:3]
    total = sum(o["p"] for o in out) or 1
    for o in out:
        o["share"] = round(o.pop("p") / total * 100)       # strength compared with the other likely diseases
    return out


def heart_probs(v):
    """Two heart models (clinical data + lifestyle data). Returns both probabilities."""
    age, male = v["age"], 1 if v["sex"] == "Male" else 0
    clin = pd.DataFrame([{"age": age, "sex": male, "cp": v["cp"], "trestbps": v["sbp"], "chol": v["chol"],
                          "fbs": 1 if v["glucose"] > 120 else 0, "thalach": round(0.85 * (220 - age)), "exang": v["exang"]}])
    life = pd.DataFrame([{"Age": age, "Gender": v["sex"], "BMI": v["bmi"], "Smoking": v["smoking"],
                          "Alcohol_Intake": v["alcohol"], "Physical_Activity": v["activity"], "Diet": v["diet"],
                          "Stress_Level": v["stress"], "Hypertension": int(v["sbp"] >= 140 or v["dbp"] >= 90),
                          "Diabetes": int(v["glucose"] >= 126), "Hyperlipidemia": int(v["chol"] >= 240),
                          "Family_History": v["family"], "Previous_Heart_Attack": v["prev_ha"],
                          "Systolic_BP": v["sbp"], "Diastolic_BP": v["dbp"], "Heart_Rate": v["hr"],
                          "Blood_Sugar_Fasting": v["glucose"], "Cholesterol_Total": v["chol"]}])
    p1 = float(heart_clin["model"].predict_proba(clin[heart_clin["features"]])[0][1])
    p2 = float(heart_life["model"].predict_proba(life[heart_life["features"]])[0][1])
    return p1, p2


def heart_p(v):
    p1, p2 = heart_probs(v)
    return (p1 + p2) / 2                                    # heart risk = average of the two models


def diabetes_p(v):
    row = pd.DataFrame([{"Pregnancies": v["preg"], "Glucose": v["glucose"], "BloodPressure": v["dbp"],
                         "BMI": v["bmi"], "Age": v["age"]}])
    return float(diab_bundle["model"].predict_proba(row[diab_bundle["features"]])[0][1])


# ---- "Why this result?"  (explainable AI by perturbation)
# For each factor we replace the user's value with a healthy value and see how much the risk drops.
HEALTHY = {"bmi": 22.0, "sbp": 118.0, "dbp": 76.0, "chol": 175.0, "glucose": 88.0, "hr": 68.0, "smoking": "Never",
           "alcohol": "None", "activity": "Active", "diet": "Healthy", "stress": "Low", "cp": 2, "exang": 0}
FACTOR = {"bmi": ("BMI", "बीएमआई", ""), "sbp": ("Blood pressure (top)", "ब्लड प्रेशर (ऊपरी)", " mmHg"),
          "dbp": ("Blood pressure (bottom)", "ब्लड प्रेशर (निचला)", " mmHg"), "chol": ("Cholesterol", "कोलेस्ट्रॉल", " mg/dL"),
          "glucose": ("Blood sugar", "ब्लड शुगर", " mg/dL"), "hr": ("Heart rate", "हृदय गति", " bpm"),
          "smoking": ("Smoking", "धूम्रपान", ""), "alcohol": ("Alcohol", "शराब", ""),
          "activity": ("Physical activity", "शारीरिक गतिविधि", ""), "diet": ("Diet", "खान-पान", ""),
          "stress": ("Stress", "तनाव", ""), "cp": ("Chest pain", "सीने में दर्द", ""),
          "exang": ("Chest pain on exercise", "कसरत में सीने का दर्द", "")}
CAT_HI = {"Never": "कभी नहीं", "Former": "पहले", "Current": "अभी", "None": "नहीं", "Low": "कम", "Moderate": "मध्यम",
          "High": "ज्यादा", "Sedentary": "बैठे रहना", "Active": "सक्रिय", "Healthy": "स्वस्थ", "Average": "सामान्य",
          "Unhealthy": "अस्वस्थ", "Medium": "मध्यम"}
CP_TEXT = {0: ("pain during activity", "मेहनत में दर्द"), 1: ("sharp or mild pain", "हल्का या तेज दर्द")}


def fmt_value(f, v, lang):
    i = 1 if lang == "hi" else 0
    if f == "cp":
        return CP_TEXT.get(v, ("", ""))[i]
    if f == "exang":
        return "हां" if lang == "hi" else "yes"
    if isinstance(v, str):
        return CAT_HI.get(v, v) if lang == "hi" else v
    return (f"{v:.1f}" if f == "bmi" else f"{round(v)}") + FACTOR[f][2]


def explain(v, fn, factors, lang):
    now = fn(v)
    out = []
    for f in factors:
        if v[f] == HEALTHY[f]:
            continue
        alt = dict(v)
        alt[f] = HEALTHY[f]
        impact = (now - fn(alt)) * 100                      # + raises the risk, - lowers it
        if abs(impact) >= 1.5:
            out.append({"factor": FACTOR[f][1 if lang == "hi" else 0], "value": fmt_value(f, v[f], lang), "impact": round(impact, 1)})
    out.sort(key=lambda x: -abs(x["impact"]))
    return out[:5]


def finish(key, p, n_est, lang, extra=None, disagree=0.0, why=None):
    lv = level(p)
    decisive = max(p, 1 - p)                                # how far the probability is from a coin flip
    base = 2 if decisive >= 0.85 else 1 if decisive >= 0.70 else 0
    drop = (1 if n_est >= 2 else 0) + (1 if disagree > 0.4 else 0)
    cert = ["Low", "Medium", "High"][max(base - drop, 0)]
    src = HI["risk_advice"][key][lv] if lang == "hi" else KB["risk_advice"][key][lv]
    return {"key": key, "name": RISK_TITLE[key][1 if lang == "hi" else 0], "risk": round(p * 100), "level": lv,
            "confidence": round(decisive * 100, 1), "certainty": cert, "precautions": src["precautions"], "diet": src["diet"],
            "specialist": KB["risk_advice"][key]["specialist"], "why": why or [], **(extra or {})}


def health_score(heart, diab, bmi):
    """Overall score 0-100 (higher is better) from the two risks and BMI distance from the healthy range."""
    pen = 0 if 18.5 <= bmi < 25 else min(100, (bmi - 25) * 8) if bmi >= 25 else min(100, (18.5 - bmi) * 8)
    s = round(100 - (0.45 * heart + 0.35 * diab + 0.20 * pen))
    return {"value": max(0, min(100, s)), "label": "Good" if s >= 75 else "Fair" if s >= 50 else "Attention"}


def analyze(d, lang="en"):
    """Everything the Results page needs, computed from the form data."""
    vals, estimated, selected = parse(d)
    n = len(estimated)
    p1, p2 = heart_probs(vals)
    ph, pd_ = (p1 + p2) / 2, diabetes_p(vals)
    risks = [
        finish("heart", ph, n, lang, {"clinical_model": round(p1 * 100), "lifestyle_model": round(p2 * 100)},
               abs(p1 - p2), explain(vals, heart_p, ["bmi", "sbp", "dbp", "chol", "glucose", "hr", "smoking", "alcohol",
                                                    "activity", "diet", "stress", "cp", "exang"], lang)),
        finish("diabetes", pd_, n, lang, why=explain(vals, diabetes_p, ["bmi", "glucose", "dbp"], lang)),
    ]
    diseases = predict_symptoms(selected, lang)
    alerts = [x["name"] for x in diseases if x["urgency"] == "emergency" and x["stage"] != "Low"]
    if vals["cp"] <= 1 and vals["exang"]:
        alerts.append("मेहनत करते समय सीने में दर्द" if lang == "hi" else "Chest pain on exertion")
    return {"lang": lang, "bmi": {"value": round(vals["bmi"], 1), "category": bmi_category(vals["bmi"])},
            "vitals": {k: round(vals[k]) for k in ("sbp", "dbp", "chol", "glucose", "hr")},
            "estimated": [EST_HI[e] if lang == "hi" else e for e in estimated], "n_estimated": n,
            "diseases": diseases, "risks": risks, "alerts": alerts, "n_symptoms": len(selected),
            "score": health_score(ph * 100, pd_ * 100, vals["bmi"]),
            "accuracy": {k: {"best": v["best"], "title": v["title"]} for k, v in METRICS.items()}}


# ------------------------------------------------------------------ 5. LOGIN HELPERS
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ATTEMPTS = {}                                               # simple brute-force protection


def body():
    d = request.get_json(silent=True)
    return d if isinstance(d, dict) else {}


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    r = rows("SELECT id, name, email FROM users WHERE id = ?", (uid,))
    return dict(r[0]) if r else None


def too_many(key):
    now = time.time()
    ATTEMPTS[key] = [t for t in ATTEMPTS.get(key, []) if now - t < 600]
    return len(ATTEMPTS[key]) >= 8


@app.before_request
def only_json_posts():
    """Extra protection: our POST APIs accept only JSON (a normal cross-site form cannot send JSON)."""
    if request.method == "POST" and request.path.startswith("/api/") and not request.is_json:
        return jsonify({"error": "JSON required"}), 415


# ------------------------------------------------------------------ 6. ROUTES (web addresses)
@app.route("/")
def home():
    """The only HTML page. JavaScript switches between Home / Check-up / Results / ... without reloading."""
    return render_template("index.html")


@app.route("/api/symptoms")
def api_symptoms():
    lang = "hi" if request.args.get("lang") == "hi" else "en"
    return jsonify([{"id": s, "label": label(s, lang), "en": label(s).lower(), "hi": label(s, "hi")}
                    for s in SYMPTOMS if not s.endswith(".1")])


@app.route("/api/bmi", methods=["POST"])
def api_bmi():
    d = body()
    try:
        h, w = num(d, "height", 50, 250), num(d, "weight", 10, 300)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not h or not w:
        return jsonify({"error": "Enter height and weight"}), 400
    b = calc_bmi(h, w)
    return jsonify({"bmi": round(b, 1), "category": bmi_category(b)})


@app.route("/api/metrics")
def api_metrics():
    return jsonify(METRICS)


@app.route("/api/predict", methods=["POST"])
def api_predict():
    """Main endpoint: receives the form as JSON, returns diseases, risks, certainty, precautions, diet, explanations."""
    d = body()
    lang = "hi" if d.get("lang") == "hi" else "en"
    try:
        res = analyze(d, lang)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    user = current_user()
    res["saved"] = False
    if user and d.get("save", True):                        # logged-in users keep their history
        keep = {k: v for k, v in d.items() if k not in ("lang", "save")}
        hid = run("INSERT INTO history(user_id, created, payload, result) VALUES (?,?,?,?)",
                  (user["id"], datetime.utcnow().isoformat(timespec="seconds"), json.dumps(keep), json.dumps(res)))
        run("DELETE FROM history WHERE user_id = ? AND id NOT IN (SELECT id FROM history WHERE user_id = ? ORDER BY id DESC LIMIT 100)",
            (user["id"], user["id"]))
        res["saved"], res["history_id"] = True, hid
    return jsonify(res)


@app.route("/api/whatif", methods=["POST"])
def api_whatif():
    """What-if simulator: recompute only the two risks with changed values (sliders)."""
    d = body()
    try:
        vals, _, _ = parse(d)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    ph, pd_ = heart_p(vals), diabetes_p(vals)
    return jsonify({"heart": {"risk": round(ph * 100), "level": level(ph)},
                    "diabetes": {"risk": round(pd_ * 100), "level": level(pd_)},
                    "score": health_score(ph * 100, pd_ * 100, vals["bmi"])})


# ---- accounts
@app.route("/api/signup", methods=["POST"])
def api_signup():
    d = body()
    name, email, pw = str(d.get("name", "")).strip(), str(d.get("email", "")).strip().lower(), str(d.get("password", ""))
    if not 1 <= len(name) <= 60:
        return jsonify({"error": "Enter your name"}), 400
    if not EMAIL_RE.match(email) or len(email) > 120:
        return jsonify({"error": "Enter a valid email"}), 400
    if len(pw) < 6 or len(pw) > 100:
        return jsonify({"error": "Password must have at least 6 characters"}), 400
    if rows("SELECT id FROM users WHERE email = ?", (email,)):
        return jsonify({"error": "This email is already registered. Please log in."}), 409
    uid = run("INSERT INTO users(name, email, password_hash, created) VALUES (?,?,?,?)",
              (name, email, generate_password_hash(pw), datetime.utcnow().isoformat(timespec="seconds")))
    session.clear()
    session["uid"] = uid
    session.permanent = True
    return jsonify({"user": {"id": uid, "name": name, "email": email}})


@app.route("/api/login", methods=["POST"])
def api_login():
    d = body()
    email, pw = str(d.get("email", "")).strip().lower(), str(d.get("password", ""))
    key = (request.remote_addr, email)
    if too_many(key):
        return jsonify({"error": "Too many attempts. Try again in 10 minutes."}), 429
    r = rows("SELECT * FROM users WHERE email = ?", (email,))
    if not r or not check_password_hash(r[0]["password_hash"], pw):   # the password is never stored, only its hash
        ATTEMPTS.setdefault(key, []).append(time.time())
        return jsonify({"error": "Wrong email or password"}), 401
    session.clear()
    session["uid"] = r[0]["id"]
    session.permanent = True
    return jsonify({"user": {"id": r[0]["id"], "name": r[0]["name"], "email": r[0]["email"]}})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
def api_me():
    return jsonify({"user": current_user()})


@app.route("/api/history")
def api_history():
    user = current_user()
    if not user:
        return jsonify({"error": "Please log in"}), 401
    out = [{"id": r["id"], "created": r["created"], "payload": json.loads(r["payload"]), "result": json.loads(r["result"])}
           for r in rows("SELECT * FROM history WHERE user_id = ? ORDER BY id DESC", (user["id"],))]
    return jsonify({"items": out})


@app.route("/api/history/<int:hid>", methods=["DELETE"])
def api_history_delete(hid):
    user = current_user()
    if not user:
        return jsonify({"error": "Please log in"}), 401
    run("DELETE FROM history WHERE id = ? AND user_id = ?", (hid, user["id"]))   # only your own records
    return jsonify({"ok": True})


# ---- PDF report (English)
def clean(t):
    t = str(t).replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"').replace("\u2013", "-").replace("\u2014", "-")
    return t.encode("latin-1", "replace").decode("latin-1")


def make_pdf(res, d, user_name):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    teal, ink, line = colors.HexColor("#0B5D57"), colors.HexColor("#0B3B38"), colors.HexColor("#C9DAD5")
    st = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=st["Title"], textColor=teal, fontSize=22, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=st["Heading2"], textColor=teal, fontSize=13, spaceBefore=12, spaceAfter=4)
    p = ParagraphStyle("p", parent=st["BodyText"], textColor=ink, fontSize=10, leading=14)
    small = ParagraphStyle("s", parent=p, fontSize=8.5, textColor=colors.HexColor("#4F6B67"))
    lvc = {"Low": colors.HexColor("#1F6B3B"), "Intermediate": colors.HexColor("#7A5200"), "High": colors.HexColor("#8A1F1B")}

    def table(data, widths, head=True):
        t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
        style = [("GRID", (0, 0), (-1, -1), 0.5, line), ("FONTSIZE", (0, 0), (-1, -1), 9.5), ("TEXTCOLOR", (0, 0), (-1, -1), ink),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
        if head:
            style += [("BACKGROUND", (0, 0), (-1, 0), teal), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        t.setStyle(TableStyle(style))
        return t

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="HealthGuard report")
    s = [Paragraph("HealthGuard report", h1),
         Paragraph(clean(f"Date: {datetime.now().strftime('%d %b %Y, %H:%M')}" + (f" &nbsp;|&nbsp; Name: {user_name}" if user_name else "")), small),
         Paragraph(f"Overall health score: <b>{res['score']['value']}/100</b> ({res['score']['label']})", p)]
    v = res["vitals"]
    s += [Paragraph("Your details", h2), table([
        ["Age", "Sex", "BMI", "Blood pressure", "Cholesterol", "Blood sugar", "Heart rate"],
        [clean(d.get("age", "")), clean(d.get("sex", "")), f"{res['bmi']['value']} ({res['bmi']['category']})", f"{v['sbp']}/{v['dbp']}",
         f"{v['chol']} mg/dL", f"{v['glucose']} mg/dL", f"{v['hr']} bpm"]], [16 * mm, 18 * mm, 34 * mm, 26 * mm, 25 * mm, 25 * mm, 22 * mm])]
    if res["estimated"]:
        s.append(Paragraph(clean("Estimated from age and BMI (not entered): " + ", ".join(res["estimated"])), small))
    s.append(Paragraph("Risk results", h2))
    data = [["Check", "Risk", "Level", "Certainty"]] + [[r["name"], f"{r['risk']}%", r["level"], r["certainty"]] for r in res["risks"]]
    t = table(data, [70 * mm, 25 * mm, 40 * mm, 35 * mm])
    for i, r in enumerate(res["risks"], 1):
        t.setStyle(TableStyle([("TEXTCOLOR", (2, i), (2, i), lvc[r["level"]])]))
    s.append(t)
    for r in res["risks"]:
        if r["why"]:
            s.append(Paragraph(clean(f"<b>Why: {r['name']}</b>"), p))
            s.append(Paragraph(clean("; ".join(f"{w['factor']} {w['value']} ({'+' if w['impact'] > 0 else ''}{w['impact']} points)" for w in r["why"])), small))
    if res["diseases"]:
        s.append(Paragraph("Likely conditions from your symptoms", h2))
        data = [["Condition", "Stage", "Certainty", "Probability", "Symptom match"]] + [
            [x["name"], x["stage"], x["certainty"], f"{x['confidence']}%", f"{x['match']}%"] for x in res["diseases"]]
        t = table(data, [58 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm])
        for i, x in enumerate(res["diseases"], 1):
            t.setStyle(TableStyle([("TEXTCOLOR", (1, i), (1, i), lvc[x["stage"]])]))
        s.append(t)
    s.append(Paragraph("Precautions and diet", h2))
    for item in [*res["diseases"], *res["risks"]]:
        s.append(Paragraph(clean(f"<b>{item['name']}</b>"), p))
        s.append(Paragraph(clean("<b>Precautions:</b> " + "; ".join(item["precautions"])), p))
        s.append(Paragraph(clean("<b>Diet:</b> " + "; ".join(item["diet"])), p))
        s.append(Spacer(1, 4))
    s.append(Spacer(1, 8))
    s.append(Paragraph("This report is generated by an educational machine learning project. It is not a medical diagnosis. "
                       "Please see a doctor for any health concern. In an emergency call 112 (India).", small))
    doc.build(s)
    buf.seek(0)
    return buf


@app.route("/api/report", methods=["POST"])
def api_report():
    d = body()
    try:
        res = analyze(d, "en")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    user = current_user()
    return send_file(make_pdf(res, d, user["name"] if user else ""), mimetype="application/pdf", as_attachment=True,
                     download_name="HealthGuard_Report.pdf")


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", 5000)))
