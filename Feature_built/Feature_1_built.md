# Feature 1: Backend API and Support Operations

## Status

Built in the current project.

## What is implemented

The project has a FastAPI backend that assembles the customer-support services and
provides operational endpoints for application health, database connectivity,
login, and escalated support work.

- `GET /` confirms that the API is running.
- `GET /health` reports API status, database availability, and process uptime.
- `GET /database/test` tests the PostgreSQL/Supabase connection and returns the
  database name, database user, and server version.
- `POST /auth/login` validates a username and password stored in
  `public.app_users` and returns the matching user role.
- `GET /escalated` returns support orders from `public.escalated_table`, including
  approval, reviewer, email, and task status fields.
- Required environment variables are loaded and validated centrally at startup.
- Database and API failures are converted into structured HTTP error responses.

## Main source files

- `app/main.py`
- `app/config.py`
- `app/database.py`
- `app/routes/auth.py`
- `app/routes/escalated.py`

## Example login request

```http
POST /auth/login
Content-Type: application/json

{
  "username": "support_user",
  "password": "user_password"
}
```

Successful credential matches return:

```json
{
  "message": "YES",
  "user_role": "agent"
}
```

Invalid credentials return `message: "NO"` without exposing which value was
incorrect.

## How to run

```bash
uvicorn app.main:app --reload
```

FastAPI documentation is available at `http://127.0.0.1:8000/docs`.

## Current limitations

- Passwords are compared as stored values. Production use should replace this with
  salted password hashing and token-based sessions.
- Login does not currently issue a JWT or enforce authorization on other routes.
- The escalation endpoint reads records but does not yet update or assign them.

