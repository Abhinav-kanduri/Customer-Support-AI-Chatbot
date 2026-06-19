# Railway Deployment Guide

This guide walks you through deploying the Customer Support AI Chatbot to Railway using GitHub Actions. Every step is explained so you understand not just what to do but why you are doing it.

---

## What is Railway?

Railway is a cloud hosting platform. You push your code to GitHub and Railway builds and runs it on a live server with a public URL. It is similar to Heroku but faster to set up. Each environment (Development, Production, Testing) gets its own isolated running copy of your app.

## What is GitHub Actions?

GitHub Actions is an automation tool built into GitHub. Every time you push code or merge a pull request, it can automatically run scripts — in our case, deploying your app to Railway. This removes the need to deploy manually.

## How They Work Together

```
You push code to GitHub
       ↓
GitHub Actions workflow runs automatically
       ↓
It installs the Railway CLI and runs "railway up"
       ↓
Railway pulls the latest code, builds it, and restarts the app
       ↓
Your live URL is updated with the new version
```

---

## Prerequisites

Before starting, make sure you have:

- A [Railway](https://railway.com) account (sign up free with GitHub)
- Your code pushed to a GitHub repository
- Admin access to the GitHub repository (needed to add secrets)

---

## Project Structure

Here is what each file does in this project:

```
Customer-Support-AI-Chatbot/
├── app/
│   └── main.py              # The FastAPI web server with /health endpoint
├── requirements.txt         # List of Python packages Railway needs to install
├── railway.toml             # Tells Railway how to build and start the app
└── .github/
    └── workflows/
        └── deployment.yml   # The GitHub Actions automation script
```

**Why does Railway need `railway.toml`?**
Railway needs to know what command starts your app. The file tells it to run:
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
`$PORT` is automatically provided by Railway — you must not hardcode a port number.

---

## Step 1 — Understand Your Railway Environments

Your Railway project already has three environments:

| Environment | Purpose | Deployed when |
|---|---|---|
| **Development** | Test new features safely | Code is merged into `develop` |
| **Production** | The live app users access | Code is merged into `main` |
| **Testing** | Manual or exploratory testing | Triggered manually |

**Why three environments?**
You never push untested code directly to Production. You test in Development first. If everything works, you promote it to Production. This protects real users from broken deployments.

Think of it like this:
```
Development  →  Testing  →  Production
(try it out)    (verify)     (go live)
```

> You do **not** need separate Railway projects. One project with multiple environments is the correct setup.

---

## Step 2 — Connect Your GitHub Repository to Railway

This step tells Railway where your code lives.

1. Log in to [railway.com](https://railway.com) and open your project
2. Click **+ Create** → **GitHub Repo**
3. If prompted, click **Configure GitHub App** and authorize Railway to access your GitHub account
4. Search for `Customer-Support-AI-Chatbot` and select it
5. Railway will automatically detect Python using **Nixpacks** (Railway's build system) and install your `requirements.txt`
6. You will see a service card appear on the project canvas named `Customer-Support-AI-Agent`

**What just happened?**
Railway cloned your repo, detected it was a Python project, installed packages, and started the app. It now has a running copy of your code.

### Disable Automatic Deploys

By default Railway redeploys every time you push to GitHub. We want GitHub Actions to control this instead.

1. Click the `Customer-Support-AI-Agent` service card
2. Go to **Settings** → **Source**
3. Turn off **Auto Deploy** (toggle it off)

**Why?**
If both Railway and GitHub Actions try to deploy at the same time you could get conflicting deployments. GitHub Actions is your single source of truth for deployments.

---

## Step 3 — Add the Service to Each Environment

When you connected the repo in Step 2, Railway added it to whichever environment was active. You need to make sure the service exists in all three environments.

Look at the **environment switcher** in the top-left corner of Railway.

1. Switch to **Development** — check the service card is visible. If not, click **+ Create** → **GitHub Repo** and connect the same repo again
2. Switch to **Production** — repeat the check
3. Switch to **Testing** — repeat if needed

**Why does each environment need the service?**
Each environment runs a completely separate copy of your app. Development changes do not affect Production. This is what makes it safe to experiment.

---

## Step 4 — Generate Railway API Tokens

A token is like a password that allows GitHub Actions to tell Railway "please deploy now." Without a token, GitHub Actions has no permission to trigger Railway.

**Where to find it:**
Railway project → **Project Settings** (left sidebar) → **Tokens**

You will see a form with two fields:
- **Token Name** — a label so you remember what the token is for
- **Environment** — which Railway environment the token has permission to deploy to

### 4.1 Create a Development Token

1. **Token Name** → type `github-actions-dev`
2. **Environment** → select `Development`
3. Click **Create**
4. A long string of characters appears — this is your token
5. **Copy it immediately** — Railway will never show it again

Save it somewhere safe (a notepad, password manager, etc.) — you will paste it into GitHub in the next step.

### 4.2 Create a Production Token

1. **Token Name** → type `github-actions-prod`
2. **Environment** → select `Production`
3. Click **Create**
4. Copy and save the token

### 4.3 Create a Testing Token (optional)

1. **Token Name** → type `github-actions-testing`
2. **Environment** → select `Testing`
3. Click **Create**
4. Copy and save the token

**Why separate tokens per environment?**
If your Development token is ever leaked, an attacker can only affect Development — not Production. Keeping tokens scoped by environment limits the blast radius of a security incident.

---

## Step 5 — Configure GitHub Environments

GitHub environments let you group secrets by deployment stage. This means your Production secrets are separate from your Development secrets.

1. Go to your GitHub repository
2. Click **Settings** → **Environments** (in the left sidebar)
3. Click **New environment** → type `development` → click **Configure environment**
4. Click **New environment** → type `production` → click **Configure environment**

### Add Protection to Production (Recommended)

Inside the `production` environment settings:

- Enable **Required reviewers**
- Add your GitHub username

**Why?**
This means someone must manually approve a production deployment before it runs. It is a safety gate that prevents accidental pushes from going live without a human check.

---

## Step 6 — Add Secrets and Variables to GitHub

GitHub Actions reads these values when it runs. Secrets are encrypted and hidden from logs. Variables are plain text and visible in logs.

### 6.1 Add Secrets

Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions** → **Secrets** tab

Click **New repository secret** and add each one:

| Secret Name | Value to paste | What it does |
|---|---|---|
| `RAILWAY_TOKEN_DEV` | Token from Step 4.1 | Lets GitHub Actions deploy to your Development environment |
| `RAILWAY_TOKEN_PROD` | Token from Step 4.2 | Lets GitHub Actions deploy to your Production environment |
| `RAILWAY_TOKEN_TESTING` | Token from Step 4.3 | Lets GitHub Actions deploy to your Testing environment (optional) |

**How to add each one:**
1. Click **New repository secret**
2. Name: paste the secret name exactly as shown (e.g. `RAILWAY_TOKEN_DEV`)
3. Secret: paste the token value you copied from Railway
4. Click **Add secret**

### 6.2 Add Variables

Go to the **Variables** tab (next to Secrets) and click **New repository variable** for each:

| Variable Name | Value | What it does |
|---|---|---|
| `RAILWAY_SERVICE_DEV` | `Customer-Support-AI-Agent` | Tells Railway which service to deploy in Development |
| `RAILWAY_SERVICE_PROD` | `Customer-Support-AI-Agent` | Tells Railway which service to deploy in Production |

**Why is the service name the same for both?**
It is the same service — just running in different environments. The token is what controls which environment gets deployed to, not the service name.

---

## Step 7 — Understand the GitHub Actions Workflow

The file [.github/workflows/deployment.yml](.github/workflows/deployment.yml) is already written and ready. Here is what it does:

| When this happens | This job runs | It does this |
|---|---|---|
| PR is opened targeting `develop` | `validate-pr-branch-policy` | Checks the source branch starts with `feature/` — fails if not |
| PR is opened targeting `main` | `validate-pr-branch-policy` | Checks the source branch is `develop` — fails if not |
| Code is merged into `develop` | `deploy-to-development` | Installs Railway CLI and runs `railway up` with your dev token |
| Code is merged into `main` | `deploy-to-production` | Installs Railway CLI and runs `railway up` with your prod token |

**You do not need to change anything in this file.** It is already configured to use the secrets and variables you added in Step 6.

**What does `railway up` do?**
It tells Railway: "take the latest code from this branch and deploy it." Railway then builds a new Docker image, runs health checks, and replaces the old running container with the new one.

---

## Step 8 — Make Your First Deployment

Follow the branch strategy from [DEPLOYMENT_RULES.md](DEPLOYMENT_RULES.md). Here is the complete flow from code to live:

### 8.1 Stage and commit your changes

```bash
git add .
git commit -m "feat: add health API with Railway deployment"
git push origin feature/newbranch
```

**What happened?** Your code is now on GitHub in the `feature/newbranch` branch. Nothing is deployed yet.

### 8.2 Open a Pull Request into develop

1. Go to your GitHub repository
2. Click **Compare & pull request** (GitHub shows this banner after a push)
3. Set **base** to `develop` and **compare** to `feature/newbranch`
4. Click **Create pull request**

**What happens automatically?**
GitHub Actions runs the `validate-pr-branch-policy` job. It checks that your branch starts with `feature/`. If it does, the check passes with a green tick. If not, the check fails and blocks the merge.

### 8.3 Get the PR approved and merge into develop

1. Ask the repository owner (or yourself if you are the owner) to review and approve
2. Once approved, click **Merge pull request**

**What happens automatically?**
GitHub Actions detects a push to `develop` and runs the `deploy-to-development` job:
- It installs the Railway CLI
- It runs `railway up --service Customer-Support-AI-Agent` using `RAILWAY_TOKEN_DEV`
- Railway builds your code and starts the app in the **Development** environment

**Where to watch it:**
Go to GitHub → **Actions** tab → click the running workflow → click the job to see live logs.

### 8.4 Verify the Development deployment

1. Go to Railway → switch to the **Development** environment
2. Click the service → **Deployments** → click the latest one → **View Logs**
3. You should see: `Uvicorn running on http://0.0.0.0:PORT`
4. Click **Settings** → **Networking** → **Generate Domain** to get a URL
5. Open the URL in your browser and add `/health` to the end

You should see:
```json
{ "status": "ok", "uptime_seconds": 4.21 }
```

### 8.5 Open a Pull Request into main

Once you are happy with Development, promote to Production:

1. Go to GitHub → **Pull requests** → **New pull request**
2. Set **base** to `main` and **compare** to `develop`
3. Click **Create pull request**
4. Get it reviewed and approved
5. Click **Merge pull request**

**What happens automatically?**
GitHub Actions runs `deploy-to-production` using `RAILWAY_TOKEN_PROD`. Railway deploys to the **Production** environment.

### 8.6 Verify the Production deployment

1. Railway → switch to **Production** environment
2. Click the service → **Settings** → **Networking** → **Generate Domain**
3. Test the live URL:

```bash
curl https://<your-production-domain>/health
```

Expected:
```json
{ "status": "ok", "uptime_seconds": 4.21 }
```

---

## Full Flow Summary

```
1. Write code on feature/newbranch
         ↓
2. git push origin feature/newbranch
         ↓
3. Open PR: feature/newbranch → develop
         ↓
4. GitHub Actions validates branch name (must start with feature/)
         ↓
5. PR approved → merge into develop
         ↓
6. GitHub Actions auto-deploys to Railway Development
         ↓
7. Test your app on the Development URL
         ↓
8. Open PR: develop → main
         ↓
9. PR approved → merge into main
         ↓
10. GitHub Actions auto-deploys to Railway Production
         ↓
11. Live app is updated at the Production URL
```

---

## Troubleshooting

### The GitHub Actions job fails with "token invalid" or "unauthorized"

- Double-check that `RAILWAY_TOKEN_DEV` and `RAILWAY_TOKEN_PROD` are added correctly in GitHub → Settings → Secrets
- Make sure you copied the full token from Railway without extra spaces
- Tokens are environment-scoped — ensure you picked the right environment when creating them

### Railway says "service not found"

- Check that `RAILWAY_SERVICE_DEV` and `RAILWAY_SERVICE_PROD` are set to `Customer-Support-AI-Agent` exactly
- Service names are case-sensitive — check for typos

### The app crashes immediately after deploy

- Go to Railway → the service → **Deployments** → click the latest deploy → **View Logs**
- Common causes:
  - A missing package in `requirements.txt`
  - Wrong start command in `railway.toml`
  - An environment variable the app needs but Railway does not have

### The branch policy check fails on my PR

- PRs into `develop` must come from a branch named `feature/something`
- PRs into `main` must come from `develop`
- If your branch is named differently (e.g. `fix/bug`), the check will fail
- Rename your branch: `git branch -m old-name feature/new-name`

### I cannot see the Actions tab in GitHub

- Make sure GitHub Actions is enabled for your repository
- Go to **Settings** → **Actions** → **General** → select **Allow all actions**

---

## Key Concepts Recap

| Term | What it means |
|---|---|
| **Railway environment** | An isolated copy of your running app (Dev, Prod, Testing) |
| **Railway service** | Your actual application inside a Railway project |
| **Railway token** | A password that allows external tools to deploy to a specific environment |
| **GitHub secret** | An encrypted value stored in GitHub, hidden from logs, used by Actions |
| **GitHub variable** | A plain text value stored in GitHub, visible in logs, used by Actions |
| **GitHub Actions workflow** | A YAML file that defines automation steps triggered by GitHub events |
| **`railway up`** | The CLI command that pushes your code and triggers a Railway deployment |
| **Nixpacks** | Railway's build system that auto-detects your language and installs dependencies |
