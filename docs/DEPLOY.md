# Sharing HealthGuard

**127.0.0.1:5000 is "localhost": it only works on your own PC.** Pick one of these.

## A. Friends on the same Wi-Fi (quick demo)
In the VS Code terminal (PowerShell), instead of `python app.py` type:
```
$env:HOST="0.0.0.0"; $env:FLASK_DEBUG="0"; python app.py
```
Find your PC's IP address (`ipconfig`, look for IPv4, for example 192.168.1.20). Friends open `http://192.168.1.20:5000`.
- Windows may ask to allow Python through the firewall: allow it on "Private networks".
- Always set `FLASK_DEBUG=0` when sharing (debug mode must never be open to others).
- Voice input will not work over http on another device; it needs https or localhost.
- It only works while your PC is on and the server is running.

## B. A public link anyone can open
GitHub stores your code but cannot run a Flask app (GitHub Pages is for static sites only). So: put the code on GitHub, then deploy it from GitHub to a host.

1. Create a GitHub repository and upload the project folder (the `.gitignore` already skips `venv`, the database and secret key).
2. **Render** (web service): New → Web Service → connect the repo. Build command `pip install -r requirements.txt`. Start command `gunicorn app:app`. Add an environment variable `SECRET_KEY` with any long random text and `FLASK_DEBUG=0`. You get an https link.
3. **Google Cloud Run** (uses the included Dockerfile): install the gcloud tool, then in the project folder run
   `gcloud run deploy healthguard --source . --region asia-south1 --allow-unauthenticated`
4. **PythonAnywhere** also works: upload the folder, create a Flask web app pointing to `app.py`.

Things to know:
- I could not test the deployment from my side, so follow each host's current instructions; free plans and limits change.
- Free hosts often reset the disk when the app restarts, so the login database (healthguard.db) can be wiped. For a long-lived site use a hosted database (for example PostgreSQL).
- The first start on a free host can be slow because the app loads the models.
- A public site with login stores health data. For a college demo that is fine; for real users you need privacy law compliance (for example India's DPDP Act).
