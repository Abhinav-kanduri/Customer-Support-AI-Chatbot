# API Documentation

This document describes the HTTP endpoints available in the Customer Support AI Chatbot service.

---

## Base URL

| Environment | Base URL |
|---|---|
| Development | `https://<your-dev-domain>.up.railway.app` |
| Production | `https://<your-prod-domain>.up.railway.app` |

Replace `<your-dev-domain>` and `<your-prod-domain>` with the domains generated in Railway under **Settings → Networking → Generate Domain**.

---

## Endpoints

### GET /

Returns a confirmation that the service is running.

**Request**

```http
GET /
```

No headers or body required.

**Response**

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "message": "Customer Support AI Chatbot is running"
}
```

**When to use it:**
A quick sanity check to confirm the server is up and reachable.

---

### GET /health

Returns the current health status and how long the server has been running.

**Request**

```http
GET /health
```

No headers or body required.

**Response**

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "status": "ok",
  "uptime_seconds": 142.37
}
```

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `status` | string | Always `"ok"` when the server is healthy |
| `uptime_seconds` | float | Number of seconds since the server started |

**When to use it:**
Used by Railway, monitoring tools, and load balancers to check if the app is alive. If this endpoint returns a non-200 response, Railway will flag the deployment as unhealthy.

---

## Testing the API

### Using a browser

Open the base URL directly in your browser and append the endpoint path:

```
https://<your-domain>.up.railway.app/health
```

### Using curl (terminal)

```bash
# Test root endpoint
curl https://<your-domain>.up.railway.app/

# Test health endpoint
curl https://<your-domain>.up.railway.app/health
```

### Using the interactive docs

FastAPI automatically generates interactive API documentation. Open either of these in your browser:

| URL | Description |
|---|---|
| `/docs` | Swagger UI — interactive, lets you send requests from the browser |
| `/redoc` | ReDoc — clean read-only documentation |

Example:
```
https://<your-domain>.up.railway.app/docs
```

---

## HTTP Status Codes

| Code | Meaning |
|---|---|
| `200 OK` | Request succeeded |
| `404 Not Found` | The endpoint path does not exist |
| `422 Unprocessable Entity` | Request body or parameters are invalid |
| `500 Internal Server Error` | Something went wrong on the server — check Railway logs |

---

## Future Endpoints

As the chatbot is built out, the following endpoints will be added:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/chat/message` | POST | Send a customer message and receive an AI response |
| `/api/v1/documents/upload` | POST | Upload FAQ or policy documents for RAG ingestion |
| `/api/v1/search` | POST | Search indexed documents by query |
| `/api/v1/tickets` | POST | Create a support ticket for an unresolved issue |
| `/api/v1/feedback` | POST | Submit a CSAT rating for a conversation |

See [README.md](README.md) for the full API design including request and response examples.
