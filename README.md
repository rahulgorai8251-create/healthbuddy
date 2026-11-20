# HealthGuard – how to run (VS Code, Windows)

## 1. One-time setup
1. Install **Python 3.10 or newer** from python.org. Tick **"Add Python to PATH"**.
2. Install **VS Code** from code.visualstudio.com and its **Python** extension.
3. Right-click the ZIP file → **Extract All**. (VS Code cannot open a ZIP directly.)

## 2. Open the project
**File → Open Folder** → choose the extracted folder that contains `app.py`. Open the terminal: **Terminal → New Terminal**.

## 3. Install and run (type these one by one)
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Mac / Linux: use `python3` and `source venv/bin/activate`.
Next time you only need `venv\Scripts\activate` and `python app.py`.

## 4. See the website
The terminal prints `Running on http://127.0.0.1:5000`. Ctrl+click it, or type `127.0.0.1:5000` in Chrome. Stop the server with **Ctrl + C**.

## 5. Features to try
Check-up (type, or upload a report photo/PDF), voice symptoms (mic button, Chrome/Edge), Hindi (button at the top right), Results with certainty and "Why this result?", What-if sliders, PDF report, Learn more links, Sign up / Login and History, Reset all.

- **Report upload and voice need internet the first time** (the reader library loads from the internet). Everything else works offline except Google Fonts.
- Photos work best when the numbers are sharp and well lit. Always check the values it fills in.

## 6. Problems
| Problem | Fix |
|---|---|
| `python` not found | reinstall Python and tick "Add to PATH", restart VS Code |
| `activate` blocked (red error) | run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then try again |
| `requirements.txt` not found | you are in the wrong folder: `cd` into the folder that contains `app.py` |
| "Re-training them now" message | normal. Your library versions differ from mine. Wait a few minutes |
| Port 5000 already in use | change `port=5000` to `5001` at the bottom of app.py, or set `PORT=5001` |
| Mic button does nothing | use Chrome or Edge and allow the microphone |
| Fonts look different offline | normal. Fonts load from Google when you are online |
| Forgot to log out / want a clean start | stop the server and delete `healthguard.db` (all accounts and history are removed) |

## 7. Share it
See `docs/DEPLOY.md` (same Wi-Fi, or a public link with GitHub + Render / Google Cloud Run).

## 8. Retrain (optional)
`python train_models.py` retrains all models on your PC (a few minutes), or use `notebook/HealthGuard_Colab_Training.ipynb` on Google Colab.

## 9. For your presentation
Read `docs/VIVA_GUIDE.md`.
