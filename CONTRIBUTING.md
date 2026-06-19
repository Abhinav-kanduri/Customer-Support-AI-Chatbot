# Contributing Guide

Thank you for contributing to the Customer Support AI Chatbot. This document explains how to set up your environment, follow the branch strategy, and submit your work correctly.

---

## Table of Contents

- [Branch Strategy](#branch-strategy)
- [Branch Naming Rules](#branch-naming-rules)
- [Step-by-Step Contribution Flow](#step-by-step-contribution-flow)
- [Commit Message Format](#commit-message-format)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Code Standards](#code-standards)
- [What Happens After You Submit a PR](#what-happens-after-you-submit-a-pr)

---

## Branch Strategy

This project uses a three-branch model:

```
feature/*  →  develop  →  main
```

| Branch | Purpose | Who pushes here |
|---|---|---|
| `feature/*` | Your working branch for a task or fix | You |
| `develop` | Integration branch — all approved features land here | Via PR only |
| `main` | Production-ready code — what is live on Railway | Via PR from develop only |

> Direct pushes to `develop` and `main` are blocked. All changes must come through a pull request.

---

## Branch Naming Rules

Always create your branch from `develop`, not from `main`.

| Type of work | Branch name pattern | Example |
|---|---|---|
| New feature | `feature/<short-description>` | `feature/add-chat-endpoint` |
| Bug fix | `feature/fix-<short-description>` | `feature/fix-health-timeout` |
| Documentation | `feature/docs-<short-description>` | `feature/docs-update-readme` |
| Refactor | `feature/refactor-<short-description>` | `feature/refactor-intent-router` |

Use lowercase letters and hyphens only. No spaces or special characters.

---

## Step-by-Step Contribution Flow

### 1. Get the latest develop branch

```bash
git checkout develop
git pull origin develop
```

### 2. Create your feature branch

```bash
git checkout -b feature/your-task-name
```

### 3. Make your changes

Write your code, tests, or documentation changes.

### 4. Stage and commit your changes

```bash
git add <specific-files>
git commit -m "feat: short description of what you did"
```

See [Commit Message Format](#commit-message-format) below.

### 5. Push your branch to GitHub

```bash
git push origin feature/your-task-name
```

### 6. Open a Pull Request into develop

1. Go to the GitHub repository
2. Click **Compare & pull request**
3. Set **base** to `develop` and **compare** to your `feature/*` branch
4. Fill in the PR title and description
5. Click **Create pull request**

GitHub Actions will automatically check your branch name. The check must pass before the PR can be merged.

### 7. Wait for review and approval

The repository owner will review your PR. You may be asked to make changes before it is approved.

### 8. Merge

Once approved, the PR is merged into `develop`. GitHub Actions will automatically deploy to the Railway **Development** environment.

### 9. Promote to production

A separate PR from `develop` into `main` is opened by the repository owner or release manager. On merge, GitHub Actions deploys to the Railway **Production** environment.

---

## Commit Message Format

Use the following format for every commit:

```
<type>: <short description>
```

| Type | When to use |
|---|---|
| `feat` | Adding a new feature |
| `fix` | Fixing a bug |
| `docs` | Documentation changes only |
| `refactor` | Code restructuring with no behaviour change |
| `test` | Adding or updating tests |
| `chore` | Config, tooling, dependency updates |

**Examples:**

```bash
git commit -m "feat: add /chat endpoint with intent classification"
git commit -m "fix: handle empty message body in health check"
git commit -m "docs: update RAILWAY_DEPLOYMENT with token steps"
git commit -m "refactor: split router logic into separate module"
```

Keep the description short (under 72 characters) and written in the present tense.

---

## Pull Request Guidelines

When opening a PR, include the following in the description:

- **What does this PR do?** — one or two sentences
- **How to test it?** — steps a reviewer can follow to verify the change
- **Any known issues or limitations?** — be honest about what is not finished

**Good PR title examples:**
```
feat: add /chat endpoint with intent classification
fix: correct uvicorn startup port binding
docs: add CONTRIBUTING guide
```

**Bad PR title examples:**
```
update stuff
WIP
my changes
```

---

## Code Standards

- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Formatting:** Follow PEP 8. Use 4 spaces for indentation, not tabs.
- **File names:** Use lowercase with underscores (e.g. `intent_router.py`)
- **Function names:** Use lowercase with underscores (e.g. `get_order_status`)
- **No secrets in code:** Never hardcode API keys, tokens, or passwords. Use environment variables.
- **No commented-out code:** Delete unused code rather than commenting it out.

---

## What Happens After You Submit a PR

```
You open PR (feature/* → develop)
        ↓
GitHub Actions runs branch policy check
        ↓
Check passes? → Repository owner reviews
        ↓
Approved? → Merged into develop
        ↓
GitHub Actions deploys to Railway Development automatically
        ↓
Development URL is tested
        ↓
develop → main PR opened and approved
        ↓
GitHub Actions deploys to Railway Production automatically
```

---

## Questions

If you are unsure about anything, open a GitHub issue or ask the repository owner before starting work. It is better to ask upfront than to build the wrong thing.
