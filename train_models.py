"""
train_models.py  -  HealthGuard training pipeline
Run in Google Colab or locally:   python train_models.py
Steps: 1) clean data  2) compare many algorithms  3) save the best model (.pkl) + metrics.json
"""
import json, os, time, warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (AdaBoostClassifier, ExtraTreesClassifier, GradientBoostingClassifier,
                              RandomForestClassifier, VotingClassifier)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score, train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.naive_bayes import BernoulliNB, GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")
DATA = os.environ.get("DATA_DIR", "datasets")   # folder that holds the datasets
OUT = "models"
os.makedirs(OUT, exist_ok=True)
RNG = np.random.RandomState(42)
metrics = {}


def r(x, n=4):
    return round(float(x), n)


PREFER = ["Random Forest", "Tuned Random Forest", "Voting Ensemble", "Logistic Regression", "Tuned Logistic Regression",
          "Extra Trees", "Gradient Boosting", "Neural Network (MLP)", "SVM", "KNN", "AdaBoost", "Naive Bayes", "Decision Tree"]


def choose(scores, margin=0.01):
    """Pick the best algorithm. If several are within 1% of the top score, prefer the one whose
    probabilities (our 'confidence') are most reliable: Random Forest, then ensembles and Logistic Regression ..."""
    top = max(scores.values())
    close = [k for k, v in scores.items() if v >= top - margin]
    return sorted(close, key=PREFER.index)[0]


# ---------------------------------------------------------------- 1. SYMPTOMS -> DISEASE
print("== 1. Symptom model ==")
tr = pd.read_csv(f"{DATA}/training_data.csv")
te = pd.read_csv(f"{DATA}/test_data.csv")
tr = tr.loc[:, ~tr.columns.str.startswith("Unnamed")]            # empty column
for d in (tr, te):
    d.columns = [c.strip().replace(" ", "") for c in d.columns]  # 'spotting_ urination' -> 'spotting_urination'

NAME_FIX = {
    "(vertigo) Paroymsal  Positional Vertigo": "Vertigo (Positional)",
    "Osteoarthristis": "Osteoarthritis",
    "Peptic ulcer diseae": "Peptic ulcer disease",
    "Dimorphic hemmorhoids(piles)": "Piles (Hemorrhoids)",
    "hepatitis A": "Hepatitis A",
    "Paralysis (brain hemorrhage)": "Paralysis (Brain hemorrhage)",
}
for d in (tr, te):
    d["prognosis"] = d["prognosis"].str.strip().replace(NAME_FIX)

rows_before = len(tr)
tr = tr.dropna().drop_duplicates().reset_index(drop=True)        # remove duplicate rows
symptoms = [c for c in tr.columns if c != "prognosis"]
X = tr[symptoms].values.astype(float)
y = tr["prognosis"].values
overlap = len(te.merge(tr, how="inner"))
print(f"rows {rows_before} -> {len(tr)} unique | diseases {len(set(y))} | test rows also in train: {overlap}/{len(te)}")


def augment(X, y, copies=12, low=0.5):
    """Randomly hide some symptoms so the model also works when a user selects only a few."""
    Xs, ys = [X], [y]
    for _ in range(copies):
        keep = RNG.rand(*X.shape) < RNG.uniform(low, 1.0, (X.shape[0], 1))
        Xs.append(X * keep)
        ys.append(y)
    return np.vstack(Xs), np.concatenate(ys)


def partial(X, frac=0.6):
    return X * (RNG.rand(*X.shape) < frac)


SYM_MODELS = {
    "Decision Tree": DecisionTreeClassifier(random_state=42),
    "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1),
    "Naive Bayes": BernoulliNB(),
    "SVM": SVC(kernel="linear", random_state=42),
    "KNN": KNeighborsClassifier(n_neighbors=5),
    "Logistic Regression": LogisticRegression(max_iter=1000),
    "Gradient Boosting": GradientBoostingClassifier(n_estimators=25, max_depth=3, random_state=42),
    "Extra Trees": ExtraTreesClassifier(n_estimators=150, random_state=42, n_jobs=-1),
    "Neural Network (MLP)": MLPClassifier(hidden_layer_sizes=(128,), max_iter=300, random_state=42),
    "AdaBoost": AdaBoostClassifier(n_estimators=100, random_state=42),
}
skf = StratifiedKFold(5, shuffle=True, random_state=42)
sym_res = {}
for name, m in SYM_MODELS.items():
    t0 = time.time()
    full, part = [], []
    for a, b in skf.split(X, y):
        Xa, ya = augment(X[a], y[a])
        clf = clone(m).fit(Xa, ya)
        full.append(accuracy_score(y[b], clf.predict(X[b])))
        part.append(accuracy_score(y[b], clf.predict(partial(X[b]))))
    sym_res[name] = {"cv_accuracy": r(np.mean(full)), "cv_std": r(np.std(full)),
                     "partial_symptom_accuracy": r(np.mean(part)), "train_time_s": r(time.time() - t0, 1)}
    print(name, sym_res[name])

best = choose({k: 0.5 * v["cv_accuracy"] + 0.5 * v["partial_symptom_accuracy"] for k, v in sym_res.items()})
final = clone(SYM_MODELS[best])
if hasattr(final, "probability"):
    final.set_params(probability=True)
Xa, ya = augment(X, y, copies=15)
final.fit(Xa, ya)
test_acc = accuracy_score(te["prognosis"], final.predict(te[symptoms].values.astype(float)))
joblib.dump({"model": final, "features": symptoms}, f"{OUT}/symptom_model.pkl", compress=3)

profiles = {}
for dis in sorted(set(y)):
    freq = tr.loc[tr.prognosis == dis, symptoms].mean()
    profiles[dis] = [s for s in symptoms if freq[s] >= 0.4]
json.dump({"symptoms": symptoms, "profiles": profiles}, open(f"{OUT}/symptom_profiles.json", "w"), indent=1)
metrics["symptom"] = {"title": "Symptoms to disease (41 diseases)", "best": best, "algorithms": sym_res,
                      "final_test_file_accuracy": r(test_acc),
                      "note": "test_data.csv rows also appear in training data, so the honest numbers are the cross-validation scores.",
                      "rows_raw": rows_before, "rows_clean": len(tr), "n_diseases": len(set(y))}


# ---------------------------------------------------------------- generic tabular helper
def tab_models(scale=True, tuned=False):
    def pipe(clf):
        return Pipeline([("scale", StandardScaler()), ("clf", clf)]) if scale else clf
    m = {
        "Decision Tree": pipe(DecisionTreeClassifier(max_depth=6, random_state=42)),
        "Random Forest": pipe(RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)),
        "Extra Trees": pipe(ExtraTreesClassifier(n_estimators=200, random_state=42, n_jobs=-1)),
        "Naive Bayes": pipe(GaussianNB()),
        "SVM": pipe(SVC(kernel="rbf", random_state=42)),
        "KNN": pipe(KNeighborsClassifier(n_neighbors=7)),
        "Logistic Regression": pipe(LogisticRegression(max_iter=2000)),
        "Gradient Boosting": pipe(GradientBoostingClassifier(random_state=42)),
        "AdaBoost": pipe(AdaBoostClassifier(n_estimators=100, random_state=42)),
        "Neural Network (MLP)": pipe(MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=800, random_state=42)),
        "Voting Ensemble": VotingClassifier([
            ("lr", pipe(LogisticRegression(max_iter=2000))),
            ("rf", pipe(RandomForestClassifier(n_estimators=150, random_state=42, n_jobs=-1))),
            ("gb", pipe(GradientBoostingClassifier(random_state=42)))], voting="soft"),
    }
    if tuned:   # hyper-parameter tuning with GridSearchCV (small datasets only)
        m["Tuned Logistic Regression"] = GridSearchCV(pipe(LogisticRegression(max_iter=3000)),
                                                      {"clf__C": [0.01, 0.03, 0.1, 0.3, 1, 3, 10]}, cv=5)
        m["Tuned Random Forest"] = GridSearchCV(pipe(RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)),
                                                {"clf__max_depth": [3, 5, 8, None], "clf__min_samples_leaf": [1, 3, 5]}, cv=5)
    return m


def run_tabular(key, title, Xdf, yv, models, out_name, cv_sample=None, note=""):
    Xtr, Xte, ytr, yte = train_test_split(Xdf, yv, test_size=0.2, stratify=yv, random_state=42)
    Xc, yc = (Xtr, ytr) if cv_sample is None else (Xtr.sample(cv_sample, random_state=1), ytr.loc[Xtr.sample(cv_sample, random_state=1).index])
    res = {}
    for name, m in models.items():
        t0 = time.time()
        sc = cross_val_score(clone(m), Xc, yc, cv=5, scoring="accuracy", n_jobs=1)
        res[name] = {"cv_accuracy": r(sc.mean()), "cv_std": r(sc.std()), "train_time_s": r(time.time() - t0, 1)}
        print(key, name, res[name])
    best = choose({k: v["cv_accuracy"] for k, v in res.items()})
    model = clone(models[best])
    if best == "SVM":
        model.set_params(**({"clf__probability": True} if hasattr(model, "steps") else {"probability": True}))
    model.fit(Xtr, ytr)
    pred = model.predict(Xte)
    res[best]["test_accuracy"] = r(accuracy_score(yte, pred))
    res[best]["test_f1"] = r(f1_score(yte, pred))
    joblib.dump({"model": model, "features": list(Xdf.columns)}, f"{OUT}/{out_name}.pkl", compress=3)
    metrics[key] = {"title": title, "best": best, "algorithms": res, "test_accuracy": res[best]["test_accuracy"],
                    "test_f1": res[best]["test_f1"], "rows_clean": int(len(Xdf)), "note": note}


# ---------------------------------------------------------------- 2. HEART (clinical, heart.csv)
print("== 2. Heart (clinical) ==")
h = pd.read_csv(f"{DATA}/heart.csv")
n_raw = len(h)
h = h.drop_duplicates().reset_index(drop=True)
# In this version of heart.csv the column 'target' is inverted (target=1 = HEALTHY: exang, age and ca all
# correlate negatively with it). We flip it so that 1 = heart disease present.
h["target"] = 1 - h["target"]
hf = ["age", "sex", "cp", "trestbps", "chol", "fbs", "thalach", "exang"]
run_tabular("heart_clinical", "Heart disease (clinical data)", h[hf], h["target"], tab_models(tuned=True),
            "heart_clinical", note=f"{n_raw} rows -> {len(h)} after removing duplicates")

# ---------------------------------------------------------------- 3. HEART (lifestyle + vitals, synthetic)
print("== 3. Heart (lifestyle + vitals) ==")
s = pd.read_csv(f"{DATA}/synthetic_heart_disease_dataset.csv")
s["Alcohol_Intake"] = s["Alcohol_Intake"].fillna("None")
sf = ["Age", "Gender", "BMI", "Smoking", "Alcohol_Intake", "Physical_Activity", "Diet", "Stress_Level",
      "Hypertension", "Diabetes", "Hyperlipidemia", "Family_History", "Previous_Heart_Attack",
      "Systolic_BP", "Diastolic_BP", "Heart_Rate", "Blood_Sugar_Fasting", "Cholesterol_Total"]
cats = ["Gender", "Smoking", "Alcohol_Intake", "Physical_Activity", "Diet", "Stress_Level"]
nums = [c for c in sf if c not in cats]


def life_models():
    pre = lambda: ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore"), cats), ("n", StandardScaler(), nums)])
    mk = lambda clf: Pipeline([("pre", pre()), ("clf", clf)])
    return {
        "Decision Tree": mk(DecisionTreeClassifier(max_depth=8, random_state=42)),
        "Random Forest": mk(RandomForestClassifier(n_estimators=100, min_samples_leaf=5, random_state=42, n_jobs=-1)),
        "Naive Bayes": Pipeline([("pre", ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cats), ("n", StandardScaler(), nums)])), ("clf", GaussianNB())]),
        "SVM": mk(SVC(kernel="rbf", random_state=42)),
        "KNN": mk(KNeighborsClassifier(n_neighbors=7)),
        "Logistic Regression": mk(LogisticRegression(max_iter=2000)),
        "Gradient Boosting": mk(GradientBoostingClassifier(random_state=42)),
        "Extra Trees": mk(ExtraTreesClassifier(n_estimators=100, min_samples_leaf=5, random_state=42, n_jobs=-1)),
        "AdaBoost": mk(AdaBoostClassifier(n_estimators=100, random_state=42)),
        "Neural Network (MLP)": mk(MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=500, random_state=42)),
        "Voting Ensemble": VotingClassifier([
            ("lr", mk(LogisticRegression(max_iter=2000))),
            ("rf", mk(RandomForestClassifier(n_estimators=80, min_samples_leaf=5, random_state=42, n_jobs=-1))),
            ("gb", mk(GradientBoostingClassifier(random_state=42)))], voting="soft"),
    }


run_tabular("heart_lifestyle", "Heart disease (lifestyle + vitals)", s[sf], s["Heart_Disease"], life_models(),
            "heart_lifestyle", cv_sample=6000,
            note="Synthetic dataset: labels follow simple rules, so scores are very high. Real-world accuracy would be lower.")

# ---------------------------------------------------------------- 4. DIABETES
print("== 4. Diabetes ==")
dd = pd.read_csv(f"{DATA}/diabetes.csv")
for c in ["Glucose", "BloodPressure", "BMI"]:
    dd[c] = dd[c].replace(0, np.nan)               # zero is impossible -> missing value
df_ = ["Pregnancies", "Glucose", "BloodPressure", "BMI", "Age"]
dm = {k: Pipeline([("imp", SimpleImputer(strategy="median")), ("s", StandardScaler()), ("clf", v.named_steps["clf"] if hasattr(v, "named_steps") else v)])
      for k, v in tab_models(tuned=True).items()}
run_tabular("diabetes", "Diabetes risk", dd[df_], dd["Outcome"], dm, "diabetes",
            note="Impossible zero values in Glucose, BloodPressure and BMI were replaced by the median.")

json.dump(metrics, open(f"{OUT}/metrics.json", "w"), indent=1)
print("DONE. best models:", {k: v["best"] for k, v in metrics.items()})
