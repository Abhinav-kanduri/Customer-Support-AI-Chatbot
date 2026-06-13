# Deployment and Branch Rules

This repository uses a controlled pull request and deployment flow.

## Branches and the stratergies

| Branch | Purpose | Merge Source |
| --- | --- | --- |
| `feature/*` | Individual feature, fix, documentation, or experiment work | Created from `develop` |
| `develop` | Integration branch for approved feature work | Pull requests from `feature/*` only |
| `main` | Production-ready branch | Pull requests from `develop` only |

## Required Pull Request Flow

1. Create all work branches from `develop`.
2. Use the `feature/<short-description>` naming pattern.
3. Open a pull request from `feature/*` into `develop`.
4. The repository owner must review and approve the pull request.
5. After approval and passing checks, merge the pull request into `develop`.
6. Open a release pull request from `develop` into `main`.
7. The repository owner must review and approve the release pull request.
8. After approval and passing checks, merge `develop` into `main`.

## Branch Policy

Pull requests must follow these rules:

| Target Branch | Allowed Source Branch |
| --- | --- |
| `develop` | `feature/*` |
| `main` | `develop` |

Direct pushes to `develop` and `main` should be disabled for everyone except emergency repository administrators. Normal contributors must raise pull requests.

## GitHub Repository Settings

Configure branch protection rules in GitHub:

### `develop`

- Require a pull request before merging.
- Require approvals.
- Require review from Code Owners.
- Require status checks to pass before merging.
- Select the `Validate PR branch policy` check.
- Require branches to be up to date before merging.
- Restrict who can push to matching branches.
- Do not allow force pushes.
- Do not allow deletions.

### `main`

- Require a pull request before merging.
- Require approvals.
- Require review from Code Owners.
- Require status checks to pass before merging.
- Select the `Validate PR branch policy` check.
- Require branches to be up to date before merging.
- Restrict who can push to matching branches.
- Do not allow force pushes.
- Do not allow deletions.

## Owner Approval

The `.github/CODEOWNERS` file marks the repository owner as the required reviewer for all files:

```text
* @Abhinav-kanduri
```

Then enable this setting for both `develop` and `main`:

```text
Require review from Code Owners
```

## Deployment Workflow

The workflow file is located at:

```text
.github/workflows/deployment.yml
```

It performs two jobs:

| Event | Behavior |
| --- | --- |
| Pull request to `develop` | Verifies the source branch starts with `feature/` |
| Pull request to `main` | Verifies the source branch is `develop` |
| Push to `develop` | Runs the development deployment placeholder |
| Push to `main` | Runs the production deployment placeholder |

The deployment jobs currently contain placeholders because this repository only contains project documentation. Add build, test, packaging, and deployment commands when application code and infrastructure are added.

## Recommended Commands

Create a feature branch:

```bash
git checkout develop
git pull origin develop
git checkout -b feature/add-chat-orchestrator
```

Open a pull request:

```text
feature/add-chat-orchestrator -> develop
```

Promote to production:

```text
develop -> main
```
