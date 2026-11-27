# Production Environment Guide

**Project:** EduPro Predictive Analytics Platform  
**Version:** 1.3.0  
**Milestone:** R4.7 – Deployment Preparation & Infrastructure Handover  

This document describes every production-relevant environment variable based on the actual implementation in `src/edup/settings.py` and `.env.example`.

---

## Environment Variable Reference

### Core Environment

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | **Yes** | `development` | Runtime environment. Must be `production` for production deployments. Controls startup validation, default log format, and API docs availability. |

**Production value:** `production`

**Valid values:** `development`, `staging`, `production`

---

### API Server

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_HOST` | No | `0.0.0.0` | Bind address for Uvicorn server. |
| `API_PORT` | No | `8000` | Port for Uvicorn server. |
| `API_WORKERS` | No | `1` | Number of Uvicorn worker processes. Increase for CPU-bound workloads, but consider a dedicated model server for high-throughput inference. |

**Production guidance:** Keep defaults unless specific scaling needs. For multi-worker, ensure model loading is handled correctly (each worker loads its own copy).

---

### Authentication

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AUTH_ENABLED` | **Yes** | `false` | Enable API key authentication. **Must be `true` in production.** |
| `API_KEYS` | **Yes** (if `AUTH_ENABLED=true`) | `""` | Comma-separated list of valid API keys. Each key should be a secure random string (32+ hex chars). Example: `a1b2c3d4...,e5f6g7h8...,i9j0k1l2...` |
| `API_KEY_HEADER` | No | `X-API-Key` | HTTP header name for API key authentication. |

**Production requirements:**
- `AUTH_ENABLED=true`
- `API_KEYS` must contain at least one key
- Keys must be unique (validated at startup)
- Generate keys securely: `openssl rand -hex 32`

**Secret management:**
```yaml
# Kubernetes Secret
apiVersion: v1
kind: Secret
metadata:
  name: edupro-api-secrets
stringData:
  API_KEYS: "key1,key2,key3"

# AWS Secrets Manager
# Key: edupro/api-keys
# Value: "key1,key2,key3"

# Vault
# Path: secret/edupro/api-keys
# Field: API_KEYS = "key1,key2,key3"
```

---

### Rate Limiting

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | **Yes** | `false` | Enable rate limiting. **Must be `true` in production.** |
| `RATE_LIMIT_REQUESTS` | No | `100` | Maximum requests per window per client IP. |
| `RATE_LIMIT_WINDOW_SECONDS` | No | `60` | Rate limit window in seconds. |

**Production requirements:**
- `RATE_LIMIT_ENABLED=true`
- Tune `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS` based on expected traffic

**Exempt paths (always):** `/health`, `/health/live`, `/health/ready`, `/docs`, `/openapi.json`, `/redoc`, `/`

**Limitation:** Current implementation is in-memory (per-process). For horizontal scaling (multiple replicas), a Redis-backed rate limiter is required (not yet implemented).

---

### CORS (Cross-Origin Resource Sharing)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CORS_ENABLED` | No | `true` | Enable CORS middleware. |
| `CORS_ORIGINS` | **Yes** (production) | `*` | Comma-separated allowed origins. **Must be explicit list in production (not `*`).** |
| `CORS_ALLOW_CREDENTIALS` | No | `false` | Allow credentials (cookies, auth headers) in cross-origin requests. |
| `CORS_ALLOW_METHODS` | No | `GET,POST,OPTIONS` | Comma-separated allowed HTTP methods. |
| `CORS_ALLOW_HEADERS` | No | `*` | Comma-separated allowed request headers. |

**Production requirements:**
- `CORS_ORIGINS=https://app.example.com,https://admin.example.com` (explicit list)
- Never use `*` in production
- Each origin must start with `http://` or `https://` (validated at startup)

---

### Trusted Hosts

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TRUSTED_HOSTS_ENABLED` | **Yes** | `false` | Enable TrustedHostMiddleware. **Must be `true` in production.** |
| `TRUSTED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated allowed hostnames (Host header values). |

**Production requirements:**
- `TRUSTED_HOSTS_ENABLED=true`
- `TRUSTED_HOSTS=api.example.com,www.example.com` (your API domains)
- Requests with unknown Host header return `400 Bad Request`

---

### Request Limits

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MAX_REQUEST_SIZE_MB` | No | `10` | Maximum request body size in megabytes. Range: 1-100. |

**Production guidance:** Default 10 MB is sufficient for prediction requests. Increase only if larger payloads expected.

---

### Paths

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATA_DIR` | No | `data` | Path to processed data directory. In container: `/app/data`. |
| `MODELS_DIR` | No | `models` | Path to models directory. In container: `/app/models`. |
| `REGISTRY_DIR` | No | `models/registry` | Path to model registry directory. In container: `/app/models/registry`. |

**Production guidance:** Use absolute paths in container: `/app/data`, `/app/models`, `/app/models/registry`. Mount persistent volumes at these paths.

---

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | **Yes** | `INFO` | Logging level. **Must be `INFO` or `WARNING` in production (not `DEBUG`).** |
| `LOG_FORMAT` | **Yes** | `text` | Log output format. **Must be `json` in production.** |
| `LOG_REQUEST_TIMING` | No | `true` | Log request timing information (duration, method, path, status). |

**Production requirements:**
- `LOG_FORMAT=json`
- `LOG_LEVEL=INFO` (or `WARNING`)
- Structured JSON logs include: `timestamp`, `level`, `logger`, `message`, `correlation_id`, extra fields

**Log format examples:**

Development (text):
```
2026-11-27 10:30:45 | INFO     | edup.api.middleware | abc123 | request_complete method=GET path=/health/live status=200 duration_ms=2.34 correlation_id=abc123
```

Production (JSON):
```json
{"timestamp": "2026-11-27T10:30:45", "level": "INFO", "logger": "edup.api.middleware", "message": "request_complete method=GET path=/health/live status=200 duration_ms=2.34", "correlation_id": "abc123", "method": "GET", "path": "/health/live", "status": 200, "duration_ms": 2.34}
```

---

### Health Checks

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HEALTH_CHECK_DETAILED` | No | `true` | Include detailed checks (registry accessibility, active model) in `/health/ready`. |

**Production guidance:** Keep `true` for comprehensive readiness checks.

---

## Complete Production Environment Example

```bash
# .env.production (DO NOT COMMIT - inject via secret store)
ENVIRONMENT=production
AUTH_ENABLED=true
API_KEYS=key1,key2,key3
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
TRUSTED_HOSTS_ENABLED=true
TRUSTED_HOSTS=api.example.com
CORS_ORIGINS=https://app.example.com,https://admin.example.com
LOG_FORMAT=json
LOG_LEVEL=INFO
HEALTH_CHECK_DETAILED=true
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1
MAX_REQUEST_SIZE_MB=10
DATA_DIR=/app/data
MODELS_DIR=/app/models
REGISTRY_DIR=/app/models/registry
LOG_REQUEST_TIMING=true
```

---

## Secret Management Integration

### Kubernetes
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: edupro-api-secrets
type: Opaque
stringData:
  API_KEYS: "key1,key2,key3"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: edupro-api-config
data:
  ENVIRONMENT: "production"
  AUTH_ENABLED: "true"
  RATE_LIMIT_ENABLED: "true"
  RATE_LIMIT_REQUESTS: "100"
  RATE_LIMIT_WINDOW_SECONDS: "60"
  TRUSTED_HOSTS_ENABLED: "true"
  TRUSTED_HOSTS: "api.example.com"
  CORS_ORIGINS: "https://app.example.com,https://admin.example.com"
  LOG_FORMAT: "json"
  LOG_LEVEL: "INFO"
  HEALTH_CHECK_DETAILED: "true"
  API_HOST: "0.0.0.0"
  API_PORT: "8000"
  API_WORKERS: "1"
  MAX_REQUEST_SIZE_MB: "10"
  DATA_DIR: "/app/data"
  MODELS_DIR: "/app/models"
  REGISTRY_DIR: "/app/models/registry"
  LOG_REQUEST_TIMING: "true"
```

### AWS Secrets Manager
```bash
# Create secret
aws secretsmanager create-secret \
  --name edupro/api-keys \
  --secret-string "key1,key2,key3"

# Reference in ECS task definition
"secrets": [
  {
    "name": "API_KEYS",
    "valueFrom": "arn:aws:secretsmanager:region:account:secret:edupro/api-keys"
  }
]
```

### HashiCorp Vault
```bash
# Write secret
vault kv put secret/edupro/api-keys API_KEYS="key1,key2,key3"

# Kubernetes auth + Vault Agent Injector
# Annotations on pod:
# vault.hashicorp.com/agent-inject: "true"
# vault.hashicorp.com/role: "edupro"
# vault.hashicorp.com/agent-inject-secret-api-keys: "secret/edupro/api-keys"
# vault.hashicorp.com/agent-inject-template-api-keys: |
#   {{- with secret "secret/edupro/api-keys" -}}
#   export API_KEYS="{{ .Data.data.API_KEYS }}"
#   {{- end }}
```

### Docker Compose (Development Only)
```yaml
services:
  api:
    env_file:
      - .env.production  # Never commit this file
```

---

## Validation Rules (Enforced at Startup)

When `ENVIRONMENT=production`, the application validates:

| Check | Error If |
|-------|----------|
| Auth enabled | `AUTH_ENABLED != true` |
| API keys present | `API_KEYS` empty |
| Rate limit enabled | `RATE_LIMIT_ENABLED != true` |
| Trusted hosts enabled | `TRUSTED_HOSTS_ENABLED != true` |
| CORS explicit origins | `CORS_ORIGINS == "*"` |
| JSON log format | `LOG_FORMAT != "json"` |
| Non-DEBUG log level | `LOG_LEVEL == "DEBUG"` |

**On validation failure:** Application exits with `RuntimeError` listing all issues.

---

## Development vs Production Defaults

| Variable | Development | Production |
|----------|-------------|------------|
| `ENVIRONMENT` | `development` | `production` |
| `AUTH_ENABLED` | `false` | `true` |
| `API_KEYS` | `""` | Required |
| `RATE_LIMIT_ENABLED` | `false` | `true` |
| `TRUSTED_HOSTS_ENABLED` | `false` | `true` |
| `CORS_ORIGINS` | `*` | Explicit list |
| `LOG_FORMAT` | `text` | `json` |
| `LOG_LEVEL` | `DEBUG` | `INFO` |
| `HEALTH_CHECK_DETAILED` | `true` | `true` |

---

*End of Production Environment Guide*