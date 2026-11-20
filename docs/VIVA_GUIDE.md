# HealthGuard – Viva guide (final version)

Read this twice with the code open next to it. Every answer is something you can say in your own words.

---
## 1. The project in 30 seconds
> "HealthGuard is a web application for health risk screening. The user enters age, height, weight, vitals, lifestyle and symptoms, or uploads a report. Machine learning models trained on five datasets predict the likely disease from symptoms (41 diseases), the heart disease risk and the diabetes risk. Each result has a risk level (Low, Intermediate, High), a certainty label, an explanation of why, precautions, diet, and links to learn more. Users can use it in Hindi, speak their symptoms, download a PDF, and log in to keep a history. The backend is Flask in Python and the frontend is HTML, CSS and JavaScript."

## 2. Two-minute demo script (what to click in front of the teacher)
1. **Home** → point at the features. Click **Start check-up**.
2. **Upload report** (or type): age 55, male, height 170, weight 85, BP 150/95, tick "I don't know" for cholesterol, sugar 140. Show the **BMI** appearing by itself.
3. Search **"chest"**, tap chest pain; click the **mic** and say "I have vomiting and breathlessness" (Chrome).
4. Click **Check my risk** → show the **emergency alert**, **health score**, **gauges**, **certainty**.
5. Scroll to **Why this result?** → "blood sugar raised the risk by 38 points". Move the **what-if** sliders → risk drops.
6. Click **Learn more** links, **Download PDF**, then switch to **हिन्दी**.
7. **Sign up** → run another check → open **History** and show the trend chart.
8. Open **Models** → "we compared 13 algorithms and chose the best by cross-validation".
9. **Reset all** → the form is blank again.

## 3. Folder map
```
healthguard/
├── app.py                 Flask backend: models, API, login, history, PDF
├── train_models.py        cleans data, compares algorithms, saves best models (.pkl)
├── build_knowledge.py     writes data/knowledge.json (precautions, diet, doctor type)
├── build_hindi.py         writes data/hindi.json (Hindi names, precautions, diet)
├── requirements.txt       libraries to install
├── datasets/              the 5 CSV datasets
├── models/                trained models (.pkl), metrics.json, symptom_profiles.json
├── data/                  knowledge.json, hindi.json
├── templates/index.html   the website (7 pages in one HTML file)
├── static/css/style.css   design
├── static/js/i18n.js      all text in English and Hindi
├── static/js/app.js       pages, form, upload, voice, results, what-if, history
├── healthguard.db         created automatically: users and history (SQLite)
├── notebook/              Google Colab notebook for training
└── docs/                  this guide, DEPLOY.md
```

## 4. Flow chart (how data moves)
```
 USER fills form (or uploads a report, or speaks symptoms)
        |
        v
 app.js  collects values -> fetch("/api/predict", POST, JSON)
        |
        v
 FLASK  app.py  @app.route("/api/predict")
        |   1. parse(): validate numbers, estimate() the ones the user does not know
        |   2. build input rows for the models
        v
 ML MODELS (loaded from .pkl once, at start-up)
   +- Symptom model   Random Forest        -> top diseases + probability
   +- Heart model 1   Tuned Random Forest  -> probability  \  average
   +- Heart model 2   Random Forest        -> probability  /  = heart risk
   +- Diabetes model  Logistic Regression  -> probability
        |
        v
 level(), certainty(), health_score(), explain()  +  precautions and diet from knowledge.json / hindi.json
        |   if logged in: save the result in SQLite (history table)
        v
 FLASK returns JSON -> app.js draws gauges, bars, plan, what-if, links on the Results page
```

## 5. Every feature and how it works
| Feature | How it works (say this) |
|---|---|
| **Login / sign up** | Flask + SQLite. The password is never saved: `generate_password_hash` stores a salted hash and `check_password_hash` compares at login. After login Flask puts the user id in a signed cookie (`session`). |
| **Guest mode** | `/api/predict` works without login. Only if `current_user()` exists, the result is saved in the `history` table. |
| **History + trend** | `/api/history` returns the user's saved checks; JavaScript draws an SVG line chart of heart and diabetes risk over time. |
| **Certainty (not "confidence %")** | Probability is shared between diseases with common symptoms, so it can be low. We show a label: High, Medium or Low, plus the raw probability. Skipped (estimated) values and disagreeing models lower it one level. |
| **Why this result?** | Explainable AI by perturbation: for each factor we replace your value with a healthy value (for example sugar 88) and re-run the model. The drop in risk is the factor's impact. |
| **What-if simulator** | Sliders call `/api/whatif`, which only recomputes the two risks. It shows now → what-if. |
| **Upload a report** | The browser reads the photo with Tesseract.js (OCR) or the PDF text with PDF.js, then `parseReport()` finds BP, cholesterol, sugar, pulse, height, weight, age, sex with regular expressions and fills the form. Nothing is sent to the server. The user checks the values. |
| **Voice input** | The Web Speech API (`SpeechRecognition`) turns speech into text; `matchSymptoms()` matches words and synonyms to symptoms. Works in Chrome/Edge. |
| **Hindi** | `i18n.js` holds every text in two languages; the server returns Hindi disease names, symptoms, precautions and diet from `hindi.json`. |
| **PDF report** | `/api/report` recomputes the result in English and builds the PDF with ReportLab. |
| **Learn more links** | Wikipedia, YouTube, Google, NHS searches and a Google Maps link for the right specialist ("find a cardiologist near me"). They are search links, so they never break. |
| **Health score** | `100 − (0.45 × heart risk + 0.35 × diabetes risk + 0.20 × BMI distance from healthy)`. A simple summary, not a medical score. |
| **Reset** | `resetForm()` clears every input, the unknown ticks, the symptoms, the upload and the BMI box. |
| **Emergency alert** | If a serious disease (heart attack, paralysis, malaria, dengue and so on) is likely, or chest pain on exertion is reported, the page shows "Call 112" and a hospital search. |

## 6. The 5 datasets and the data cleaning
| Dataset | Used for | Cleaning |
|---|---|---|
| training_data.csv, test_data.csv | symptoms → 41 diseases | removed empty column, fixed 3 column names and 6 disease spellings, removed duplicates (4920 rows → 304 unique) |
| heart.csv | heart risk (clinical) | removed 723 duplicate rows, **fixed an inverted label** (in this file target=1 means healthy) |
| synthetic_heart_disease_dataset.csv | heart risk (lifestyle + vitals) | filled missing alcohol with "None" |
| diabetes.csv | diabetes risk | impossible zeros in glucose, blood pressure and BMI replaced with the median |
| disease_diagnosis.xlsx | not used | labels looked random, it would lower accuracy |

## 7. Algorithms compared
We tried many algorithms on every model: Decision Tree, Random Forest, Extra Trees, Naive Bayes, SVM, KNN, Logistic Regression, Gradient Boosting, AdaBoost, a Neural Network (MLP), a Voting Ensemble, and tuned versions (GridSearchCV) for the small datasets.

**Symptoms → disease (41 diseases)**
| Algorithm | Accuracy (5-fold cross-validation) | With 60% of symptoms |
|---|---|---|
| Decision Tree | 100.0% | 84.9% |
| Random Forest **(chosen)** | 100.0% | 93.4% |
| Naive Bayes | 100.0% | 94.1% |
| SVM | 100.0% | 92.1% |
| KNN | 100.0% | 89.5% |
| Logistic Regression | 100.0% | 93.4% |
| Gradient Boosting | 100.0% | 88.8% |
| Extra Trees | 100.0% | 91.1% |
| Neural Network (MLP) | 99.7% | 93.8% |
| AdaBoost | 56.2% | 26.0% |

**Heart (clinical data)**
| Algorithm | Accuracy (5-fold cross-validation) |
|---|---|
| Tuned Random Forest **(chosen)** | 80.5% |
| Logistic Regression | 78.4% |
| Tuned Logistic Regression | 78.4% |
| KNN | 78.4% |
| SVM | 78.0% |
| AdaBoost | 77.6% |
| Voting Ensemble | 76.3% |
| Extra Trees | 75.5% |
| Naive Bayes | 75.5% |
| Random Forest | 75.1% |
| Gradient Boosting | 73.0% |
| Neural Network (MLP) | 71.8% |
| Decision Tree | 66.8% |

**Heart (lifestyle + vitals)**
| Algorithm | Accuracy (5-fold cross-validation) |
|---|---|
| Gradient Boosting | 100.0% |
| AdaBoost | 100.0% |
| Voting Ensemble | 100.0% |
| Decision Tree | 100.0% |
| Random Forest **(chosen)** | 100.0% |
| Neural Network (MLP) | 97.2% |
| SVM | 93.6% |
| Extra Trees | 93.2% |
| Logistic Regression | 92.5% |
| KNN | 89.8% |
| Naive Bayes | 83.2% |

**Diabetes**
| Algorithm | Accuracy (5-fold cross-validation) |
|---|---|
| Tuned Logistic Regression | 78.7% |
| Logistic Regression **(chosen)** | 78.2% |
| SVM | 76.7% |
| Tuned Random Forest | 76.7% |
| Extra Trees | 76.4% |
| KNN | 76.2% |
| Neural Network (MLP) | 76.2% |
| AdaBoost | 75.9% |
| Naive Bayes | 75.1% |
| Random Forest | 75.1% |
| Voting Ensemble | 74.9% |
| Gradient Boosting | 74.0% |
| Decision Tree | 71.8% |

### How the best one is chosen
Highest cross-validation score. If several are within 1%, we prefer the one with reliable probabilities (Random Forest, then ensembles and Logistic Regression), because certainty uses the probability. Naive Bayes and single Decision Trees give extreme 0% or 100% probabilities, so they would mislead.

## 8. Accuracy – say this honestly
- Symptom model: 100% cross-validated when all of a disease's symptoms are given, about 93% when the user gives only 60% of them (the realistic case). The dataset is synthetic, so almost every algorithm scores 100%.
- Heart (clinical): 81% cross-validated, 75% on the hold-out test. Diabetes: 78% cross-validated, 71% on the hold-out test. These are real-style datasets, where 75–85% is normal.
- Heart (lifestyle): about 100.0% because that dataset is synthetic and its labels follow simple rules (age, hypertension, cholesterol).
- **Real medical data cannot honestly reach 99–100%.** A real 100% usually means data leakage or a synthetic dataset. We report cross-validated numbers and explain them.
- test_data.csv: 41 of its 42 rows are also in training_data.csv, so a score on that file is not a fair test. That is why we use cross-validation.

**Cross-validation (5-fold):** split the data into 5 parts, train on 4, test on the 5th, repeat 5 times, average.

## 9. app.py explained
| Part | What it does |
|---|---|
| `app = Flask(__name__)` | creates the web application |
| `secret_key()` | key that signs the login cookie, created once and saved in `.secret_key` |
| `load_all()` | loads the .pkl models and JSON files once at start-up. If a model cannot load (different library version) the app retrains automatically |
| `connect()`, `rows()`, `run()` | SQLite helpers. They use `?` placeholders, which stops SQL injection |
| `label()`, `calc_bmi()`, `bmi_category()` | helpers. BMI = weight(kg) / height(m)² |
| `level(p)` | probability → Low (<30%), Intermediate (30–60%), High (60%+) |
| `num()` | reads a number from the request and checks the range; empty means "unknown" |
| `estimate()`, `parse()` | fill unknown values from age and BMI; validate the whole form |
| `predict_symptoms()` | 0/1 vector of symptoms, `predict_proba` for every disease, keep the top 3, add matched and missing symptoms |
| `heart_probs()`, `heart_p()`, `diabetes_p()` | probabilities from the models. Heart risk = average of two models |
| `explain()` | "Why this result?" by replacing each value with a healthy one |
| `finish()` | probability → level, certainty, precautions, diet |
| `health_score()` | the 0–100 summary |
| `analyze()` | puts everything together for one request |
| `/api/predict`, `/api/whatif`, `/api/report` | the main APIs |
| `/api/signup`, `/api/login`, `/api/logout`, `/api/me`, `/api/history` | accounts and history |
| `make_pdf()` | builds the PDF with ReportLab |

**What is `predict_proba`?** It returns the probability of each class instead of only the answer. For a Random Forest it is the share of trees voting for that class.
**What is an API route?** A URL that runs a Python function. `/api/predict` runs `api_predict()`.
**What is JSON?** A text format for data, like `{"age": 45, "sex": "Male"}`. Browser and Flask talk in JSON.

## 10. Formulas
- **BMI** = weight / (height in metres)²
- **Risk level (heart, diabetes):** under 30% Low, 30–60% Intermediate, 60%+ High
- **Risk for a disease from symptoms:** `score = 0.6 × probability + 0.4 × symptom match`; ≥55 High, ≥30 Intermediate, else Low
- **Certainty (heart, diabetes):** `decisive = max(p, 1−p)`; ≥85% High, ≥70% Medium, else Low; minus one level if two or more values were estimated; minus one level if the two heart models disagree by more than 40 points
- **Certainty (symptoms):** probability ≥60% High, ≥30% Medium, else Low
- **Why impact** = risk(now) − risk(with this value healthy), in percentage points
- **Health score** = 100 − (0.45 × heart% + 0.35 × diabetes% + 0.20 × BMI penalty)

## 11. Security – be ready for "can it be hacked?"
- Passwords: salted hashes only (`werkzeug.security`). Nobody can read them, even from the database.
- Login cookie: signed with a secret key, `HttpOnly` and `SameSite=Lax`.
- SQL injection: all queries use `?` placeholders.
- XSS: the page escapes every text from the server (`esc()`).
- Brute force: after 8 wrong attempts in 10 minutes the login is blocked for that email and IP.
- CSRF: POST APIs accept only `application/json`, which a normal cross-site form cannot send.
- Privacy: report images are read in the browser and never uploaded; guests are not saved at all.
- Honest limits: it is a student project. A real hospital system would also need HTTPS everywhere, audit logs, email verification and legal compliance.

## 12. Likely teacher questions
1. **Why is the confidence so low sometimes?** It is the model's probability for one disease. Many diseases share symptoms, so the probability is shared. With 3–4 symptoms 35% for the top disease is honest. That is why we show a certainty label and advise adding more symptoms. Models that always show 95–100% are usually overconfident.
2. **Why Random Forest for symptoms?** It scored at the top, handles many 0/1 features, and its probabilities are reliable.
3. **Why did you compare so many algorithms?** No algorithm is best for every dataset. We measured them all with the same cross-validation and chose by score.
4. **What is overfitting and how did you avoid it?** When a model memorises the training data. We removed duplicates, used cross-validation, and tested on unseen rows.
5. **Why not 100% accuracy?** On real medical data it is not honest. We report true scores.
6. **What if the user selects only a few symptoms?** We trained with random symptom hiding (data augmentation), so it still works with partial symptoms (about 93%).
7. **What is "Why this result?"** It shows which input raised the risk the most, by re-running the model with a healthy value. This is explainable AI.
8. **How does the what-if simulator work?** Each slider move calls `/api/whatif`, which recomputes the risk with the new values.
9. **How does the report upload work?** OCR (Tesseract.js) reads the text from the photo, regular expressions find the numbers, and the form is filled. The user always checks the values. The file stays in the browser.
10. **How does voice input work?** The browser's Web Speech API converts speech to text and we match words to symptoms.
11. **How does login work?** Sign up stores a password hash in SQLite; login checks the hash and stores the user id in a signed cookie; history is saved per user id.
12. **Why can guests use it without logging in?** Login only adds saving. The prediction API does not need it.
13. **How is the heart risk calculated?** Two models (clinical data and lifestyle data); we average their probabilities.
14. **What do you do when the user doesn't know a value?** `estimate()` gives a typical value from age and BMI; the result says "estimated" and certainty can drop one level.
15. **How did you choose Low, Intermediate, High?** Thresholds of 30% and 60% on the probability. It is a design choice that can be adjusted.
16. **What is a .pkl file?** A saved trained model. We train once and load it in Flask.
17. **How does the page change without refreshing?** JavaScript shows one section based on the URL hash (`#/results`) and gets data with `fetch()`.
18. **What is Flask?** A lightweight Python framework that maps URLs to Python functions.
19. **Is this a medical diagnosis?** No. It is an educational screening tool with a disclaimer; for emergencies it tells the user to call 112.
20. **What are the limitations?** The symptom and lifestyle datasets are synthetic; only 41 diseases; OCR can misread photos; it does not replace a doctor. Future work: real hospital data, more diseases, email verification.
21. **What did you do about the inverted heart label?** In heart.csv `target=1` correlated with less disease, so we flipped it. Without that, healthy young people would get high heart risk.
22. **How did you handle both languages?** Static text in `i18n.js`; names, precautions and diet come from `hindi.json` through the same API.
23. **Why is the PDF only in English?** The PDF library needs a Hindi font file. The Print button saves a Hindi copy through the browser.
24. **How would you deploy it?** Push to GitHub and deploy on Render or Google Cloud Run with `gunicorn app:app` (see docs/DEPLOY.md).
25. **What is data augmentation here?** Extra training rows made by hiding random symptoms.
26. **Which metrics did you use?** Cross-validation accuracy, and accuracy and F1 on a hold-out test.
27. **What is an ensemble?** Several models voting together. We tested a Voting Ensemble of Logistic Regression, Random Forest and Gradient Boosting.
28. **What is hyper-parameter tuning?** Trying settings (like tree depth) with GridSearchCV and keeping the best. We did it on the two small datasets.
29. **What is SQLite?** A small database in one file, built into Python. Good for a project; for many users use PostgreSQL.
30. **How do the "Learn more" links work?** They are search URLs built from the disease name, so they always work.

## 13. If the teacher points at a line
Find the line in section 9, say what the function does in one sentence, then give one example: *"estimate() takes age and BMI; for age 45 and BMI 27 it returns about 191 mg/dL cholesterol."*
