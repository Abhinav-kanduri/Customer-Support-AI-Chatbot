# Local Development Setup Guide

This guide walks you through running the Customer Support AI Chatbot on your own machine before pushing to GitHub or Railway.

---

## What You Need

| Tool | Minimum Version | Check your version |
|---|---|---|
| Python | 3.11+ | `python --version` |
| pip | Latest | `pip --version` |
| Git | Any recent | `git --version` |

If Python is not installed, download it from [python.org](https://www.python.org/downloads/). Make sure to check **"Add Python to PATH"** during installation on Windows.

---

## Step 1 — Clone the Repository

If you have not already cloned the project:

```bash
git clone https://github.com/<your-username>/Customer-Support-AI-Chatbot.git
cd Customer-Support-AI-Chatbot
```

If you already have it cloned, make sure you are up to date:

```bash
git checkout develop
git pull origin develop
```

---

## Step 2 — Create a Virtual Environment

A virtual environment keeps the project's Python packages isolated from the rest of your system. This prevents version conflicts between projects.

**On Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows (Command Prompt):**
```bash
python -m venv venv
venv\Scripts\activate
```

**On Windows (PowerShell):**
```bash
python -m venv venv
venv\Scripts\Activate.ps1
```

You will know it worked when you see `(venv)` at the start of your terminal prompt.

> Always activate the virtual environment before running the project. If you close the terminal, you need to activate it again next time.

---

## Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI and Uvicorn (the web server) listed in `requirements.txt`.

To verify the packages installed correctly:

```bash
pip list
```

You should see `fastapi` and `uvicorn` in the list.

---

## Step 4 — Run the App

```bash
uvicorn app.main:app --reload
```

**What this command means:**
- `app.main` — look inside the `app/` folder, open `main.py`
- `:app` — use the FastAPI object named `app` inside that file
- `--reload` — automatically restart the server when you save a file (useful during development)

You should see output like:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

---

## Step 5 — Test the Endpoints

Open your browser and visit:

| URL | What you should see |
|---|---|
| `http://127.0.0.1:8000/` | `{"message": "Customer Support AI Chatbot is running"}` |
| `http://127.0.0.1:8000/health` | `{"status": "ok", "uptime_seconds": 3.12}` |
| `http://127.0.0.1:8000/docs` | Interactive Swagger UI — test endpoints from the browser |

Or test using curl in a second terminal:

```bash
curl http://127.0.0.1:8000/health
```

---

## Step 6 — Stop the Server

Press `CTRL + C` in the terminal where the server is running.

---

## Project Structure

```
Customer-Support-AI-Chatbot/
├── app/
│   └── main.py          # FastAPI app — all endpoints live here
├── requirements.txt     # Python packages needed to run the app
├── railway.toml         # Railway deployment configuration
└── .github/
    └── workflows/
        └── deployment.yml  # GitHub Actions CI/CD pipeline
```

---

## Making Code Changes

1. Always work on a `feature/*` branch — never edit `develop` or `main` directly:

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-task-name
```

2. Open `app/main.py` in your editor and make your changes
3. The server will reload automatically (because of `--reload`)
4. Test your change in the browser or with curl
5. When happy, commit and push:

```bash
git add app/main.py
git commit -m "feat: describe what you changed"
git push origin feature/your-task-name
```

6. Open a Pull Request on GitHub following the steps in [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Common Errors and Fixes

### `ModuleNotFoundError: No module named 'fastapi'`

You forgot to activate the virtual environment or install dependencies.

```bash
# Activate venv first
source venv/bin/activate       # Mac/Linux
venv\Scripts\activate          # Windows

# Then install
pip install -r requirements.txt
```

### `Address already in use` on port 8000

Another process is already using port 8000. Either stop it or run on a different port:

```bash
uvicorn app.main:app --reload --port 8001
```

Then visit `http://127.0.0.1:8001/`.

### `ImportError` or app does not start

Make sure you are running the command from the **root of the project folder**, not from inside `app/`:

```bash
# Correct — run from the project root
cd Customer-Support-AI-Chatbot
uvicorn app.main:app --reload
```

### PowerShell says `cannot be loaded because running scripts is disabled`

Run this once to allow scripts:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate the virtual environment again.

---

## Difference Between Local and Railway

| | Local | Railway |
|---|---|---|
| Start command | `uvicorn app.main:app --reload` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Port | `8000` (fixed) | Assigned by Railway via `$PORT` |
| Reload | Yes (`--reload` flag) | No — Railway restarts on deploy |
| URL | `http://127.0.0.1:8000` | `https://<your-domain>.up.railway.app` |

The `--reload` flag is only for local development. Never use it in production — it adds overhead and is not needed when Railway handles restarts.
