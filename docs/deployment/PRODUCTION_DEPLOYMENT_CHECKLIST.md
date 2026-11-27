# Production Deployment Checklist

**Project:** EduPro Predictive Analytics Platform  
**Version:** 1.3.0  
**Milestone:** R4.7 – Deployment Preparation & Infrastructure Handover  
**Date:** 2026-11-27  

---

## 1. Infrastructure Prerequisites

### 1.1 Compute Platform
| Requirement | Specification | Responsible |
|-------------|---------------|-------------|
| Container orchestration | Kubernetes (EKS/GKE/AKS), ECS, or Docker Swarm | Infrastructure |
| Minimum Kubernetes version | 1.28+ | Infrastructure |
| Node architecture | linux/amd64 | Infrastructure |
| CPU architecture | x86_64 | Infrastructure |

### 1.2 Networking
| Requirement | Specification | Responsible |
|-------------|---------------|-------------|
| Load balancer / reverse proxy | nginx, Traefik, ALB, or equivalent | Infrastructure |
| TLS termination | At load balancer (not in container) | Infrastructure |
| Internal DNS | Service discovery for inter-service communication | Infrastructure |
| Network policies | Restrict ingress/egress (see Section 7) | Infrastructure |

### 1.3 Storage
| Requirement | Specification | Responsible |
|-------------|---------------|-------------|
| Persistent volume for models | Minimum 10 GiB, ReadWriteOnce or ReadWriteMany | Infrastructure |
| Persistent volume for data | Minimum 5 GiB, ReadOnlyMany (read-only) | Infrastructure |
| Volume type | CSI-compatible (EBS, GCE PD, Azure Disk, NFS) | Infrastructure |
| Backup policy | Daily snapshots for model registry | Infrastructure |

### 1.4 Secrets Management
| Requirement | Specification | Responsible |
|-------------|---------------|-------------|
| Secret store | Vault, AWS Secrets Manager, GCP Secret Manager, or Kubernetes Secrets | Infrastructure |
| API keys injection | Environment variables at container startup | Infrastructure |
| Key rotation | Automated or manual process (external) | Infrastructure |

### 1.5 Observability
| Requirement | Specification | Responsible |
|-------------|---------------|-------------|
| Log aggregation | Loki, ELK, CloudWatch, or Datadog | Infrastructure |
| Metrics collection | Prometheus + Grafana, DataDog, CloudWatch | Infrastructure |
| Alerting | Alertmanager, PagerDuty, Opsgenie | Infrastructure |
| Distributed tracing | Optional (OpenTelemetry not yet integrated) | Infrastructure |

---

## 2. Supported Python / Runtime Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.12 (exact) | Required by `pyproject.toml` |
| Base image | python:3.12-slim | Used in Dockerfile |
| Uvicorn | 0.32.0 | ASGI server |
| FastAPI | 0.116.0 | API framework |

**Runtime constraints:**
- No GPU required
- Minimum 512 MiB RAM (1 GiB recommended for model loading)
- Single-threaded model inference (consider model server for high throughput)

---

## 3. Container Image Requirements

### 3.1 Build Specifications
| Attribute | Value |
|-----------|-------|
| Dockerfile | `Dockerfile` (multi-stage) |
| Build target | `runtime` (production) |
| Base image | `python:3.12-slim` |
| Non-root user | `edupro` (UID/GID assigned at build) |
| Health check | `curl -f http://localhost:8000/health/live` |
| Exposed port | 8000 |

### 3.2 Build Commands
```bash
# Local build (for verification)
docker build -t edupro-api:1.3.0 .

# CI build (GitHub Actions)
# See .github/workflows/ci.yml: docker-build job
```

### 3.3 Image Verification
```bash
# Verify image runs
docker run --rm --entrypoint python edupro-api:1.3.0 -c "import edup.api.main; print('Import OK')"

# Verify health check
docker run -d --name edupro-test -p 8000:8000 \
  -e ENVIRONMENT=development \
  -e AUTH_ENABLED=false \
  -e RATE_LIMIT_ENABLED=false \
  edupro-api:1.3.0
sleep 10
curl -f http://localhost:8000/health/live
docker stop edupro-test
```

---

## 4. TLS Termination

| Aspect | Requirement |
|--------|-------------|
| Termination point | Load balancer / reverse proxy (nginx, ALB, Traefik, Cloudflare) |
| Certificate source | ACM, Let's Encrypt, or internal CA |
| Protocol | TLS 1.2 minimum, TLS 1.3 preferred |
| Internal communication | HTTP (container port 8000) |
| HSTS | Enabled at load balancer |
| Certificate rotation | Automated via ACM or cert-manager |

**Application does NOT handle TLS.** The container receives plain HTTP on port 8000.

---

## 5. API Key Secret Management

### 5.1 Required Secrets
| Secret | Description | Format |
|--------|-------------|--------|
| `API_KEYS` | Comma-separated valid API keys | `key1,key2,key3` (each: 32+ hex chars) |

### 5.2 Generation Guidance
```bash
# Generate secure API keys (run locally, never in CI logs)
openssl rand -hex 32  # Repeat for each key
```

### 5.3 Injection Methods
| Platform | Method |
|----------|--------|
| Kubernetes | `envFrom: secretRef` or `env.valueFrom.secretKeyRef` |
| ECS | `secrets` in task definition |
| Docker Swarm | `secrets` in compose file |
| Docker Compose | `env_file` or `secrets` (dev only) |

### 5.4 Rotation
- No built-in rotation mechanism
- Rotate by updating secret store and rolling pods
- Support multiple active keys simultaneously (comma-separated)

---

## 6. Persistent Volumes

### 6.1 Volume Mounts
| Mount Path | Purpose | Access Mode | Source |
|------------|---------|-------------|--------|
| `/app/models` | Model artifacts + registry | ReadWriteOnce/ReadWriteMany | PVC |
| `/app/data` | Processed data (Parquet/CSV) | ReadOnlyMany | PVC |

### 6.2 Kubernetes Example
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: edupro-models-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: edupro-data-pvc
spec:
  accessModes:
    - ReadOnlyMany
  resources:
    requests:
      storage: 5Gi
```

### 6.3 Model Registry Preparation
- Registry directory: `/app/models/registry`
- Must contain: `registry_index.json`, `active_model.txt`, `versions/`
- Initialize by running `edup-retrain` pipeline or mounting pre-populated registry

---

## 7. Environment Variables and Configuration

### 7.1 Required Production Variables
| Variable | Required | Example |
|----------|----------|---------|
| `ENVIRONMENT` | Yes | `production` |
| `AUTH_ENABLED` | Yes | `true` |
| `API_KEYS` | Yes | `key1,key2,key3` |
| `RATE_LIMIT_ENABLED` | Yes | `true` |
| `TRUSTED_HOSTS_ENABLED` | Yes | `true` |
| `CORS_ORIGINS` | Yes | `https://app.example.com,https://admin.example.com` |
| `LOG_FORMAT` | Yes | `json` |
| `LOG_LEVEL` | Yes | `INFO` |

### 7.2 Optional / Tunable Variables
| Variable | Default | Production Guidance |
|----------|---------|---------------------|
| `API_HOST` | `0.0.0.0` | Keep as-is |
| `API_PORT` | `8000` | Keep as-is |
| `API_WORKERS` | `1` | Increase for CPU-bound workloads (consider model server instead) |
| `RATE_LIMIT_REQUESTS` | `100` | Adjust based on traffic |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Adjust based on traffic |
| `TRUSTED_HOSTS` | `localhost,127.0.0.1` | Set to API domain(s) |
| `MAX_REQUEST_SIZE_MB` | `10` | Keep unless large payloads expected |
| `HEALTH_CHECK_DETAILED` | `true` | Keep enabled |

### 7.3 Development Overrides (DO NOT USE IN PRODUCTION)
| Variable | Dev Value |
|----------|-----------|
| `AUTH_ENABLED` | `false` |
| `RATE_LIMIT_ENABLED` | `false` |
| `CORS_ORIGINS` | `*` |
| `TRUSTED_HOSTS_ENABLED` | `false` |
| `LOG_FORMAT` | `text` |
| `LOG_LEVEL` | `DEBUG` |

---

## 8. Network Ingress and Egress Restrictions

### 8.1 Ingress (Required)
| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 8000 | HTTP | Load balancer only | API traffic |

### 8.2 Egress (Required)
| Destination | Port | Protocol | Purpose |
|-------------|------|----------|---------|
| Internal data store | N/A | N/A | None required (read-only data mounted) |
| External APIs | N/A | N/A | None required |
| Log aggregation | As configured | TCP/UDP | Structured log shipping |
| Metrics endpoint | As configured | HTTP | Prometheus scrape |

### 8.3 Network Policies (Kubernetes Example)
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: edupro-api-ingress
spec:
  podSelector:
    matchLabels:
      app: edupro-api
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8000
```

---

## 9. Log Aggregation

### 9.1 Log Format
- **Production:** JSON (structured)
- **Fields:** timestamp, level, logger, message, correlation_id, extra fields
- **Exception logs:** Full stack trace in `exception` field

### 9.2 Correlation ID
- Header: `X-Correlation-ID`
- Generated per request (UUID v4 prefix) or client-provided
- Propagated through all log lines for request tracing

### 9.3 Required Log Fields for Alerting
| Field | Use Case |
|-------|----------|
| `level` | Filter ERROR/WARN |
| `logger` | Identify component |
| `correlation_id` | Trace request flow |
| `message` | Human-readable context |

---

## 10. Health and Readiness Monitoring

### 10.1 Endpoints
| Endpoint | Purpose | Expected Response | Auth/Rate Limit |
|----------|---------|-------------------|-----------------|
| `GET /health/live` | Liveness probe | `200 OK`, `{"status":"alive"}` | Exempt |
| `GET /health/ready` | Readiness probe | `200 OK` (ready) or `503` (not ready) | Exempt |
| `GET /health` | General status | `200 OK`, model info | Exempt |

### 10.2 Readiness Checks
The `/health/ready` endpoint verifies:
1. Model loaded (`model_loaded: true`)
2. No model load error (`model_load_error: false`)
3. Registry accessible (`registry_accessible: true`)
4. Active model registered (`active_model_registered: true`)

### 10.3 Alerting Rules (Example)
```yaml
# Prometheus alerting rules
- alert: EduProAPILivenessFailure
  expr: up{job="edupro-api"} == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "EduPro API liveness probe failed"

- alert: EduProAPIReadinessFailure
  expr: http_status{endpoint="/health/ready"} != 200
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "EduPro API not ready - model or registry unavailable"
```

---

## 11. Rate-Limiting Requirements

### 11.1 Current Implementation
- **Algorithm:** In-memory sliding window (token bucket)
- **Scope:** Per client IP (respects `X-Forwarded-For`)
- **Exempt paths:** `/health`, `/health/live`, `/health/ready`, `/docs`, `/openapi.json`, `/redoc`, `/`

### 11.2 Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_REQUESTS` | 100 | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | 60 | Window duration |

### 11.3 Horizontal Scaling Limitation
- **Current:** In-memory only, not shared across replicas
- **Required for scaling:** Redis-backed rate limiter (not implemented in application)
- **Workaround:** Sticky sessions or single replica until Redis integration

---

## 12. Backup and Recovery Requirements

### 12.1 Model Registry Backup
| Asset | Frequency | Method |
|-------|-----------|--------|
| `/app/models/registry` | Daily | Volume snapshot or `tar` + object storage |
| Active model artifact | On promotion | Copied to registry versions/ |

### 12.2 Data Backup
| Asset | Frequency | Method |
|-------|-----------|--------|
| `/app/data` (processed data) | Weekly | Volume snapshot |
| Raw data (`EduPro_Online_Platform.xlsx`) | As needed | Source control / object storage |

### 12.3 Configuration Backup
| Asset | Frequency | Method |
|-------|-----------|--------|
| Environment variables / secrets | On change | Secret store versioning |
| Kubernetes manifests | On change | GitOps repository |

---

## 13. Model Registry Preparation

### 13.1 Pre-Deployment Steps
1. Ensure processed data exists at `/app/data/processed_data.parquet`
2. Run retraining pipeline: `python -m edup.models.retrain retrain --auto-promote=false`
3. Validate candidate: `python -m edup.models.retrain validate`
4. Promote to active: `python -m edup.models.retrain promote <version>`
5. Verify `/health/ready` returns `200 OK` with all checks passing

### 13.2 Registry Structure (Post-Deployment)
```
/app/models/registry/
├── registry_index.json      # JSON index of all versions
├── active_model.txt         # Path to active model artifact
├── .lock                    # File-based lock (runtime)
├── retraining_config.json   # Retraining configuration
├── logs/                    # Retraining job logs
└── versions/
    └── v<timestamp>/
        ├── <model>.pkl      # Model artifact
        └── <model>_metadata.json  # Model metadata
```

---

## 14. Production Acceptance Criteria

| Criterion | Verification Method | Pass Condition |
|-----------|---------------------|----------------|
| Container starts | `docker run` / pod `Running` | No crash, health check passes |
| Liveness probe | `GET /health/live` | `200 OK`, `status: alive` |
| Readiness probe | `GET /health/ready` | `200 OK`, all checks true |
| Model loaded | `GET /model-info` | `200 OK`, model metadata returned |
| Prediction works | `POST /predict/enrollment` | `200 OK`, valid prediction |
| Auth enforced | Request without key | `401 Unauthorized` |
| Rate limit enforced | Exceed limit | `429 Too Many Requests` |
| CORS correct | Request from allowed origin | `Access-Control-Allow-Origin` matches |
| Trusted hosts enforced | Request with invalid Host | `400 Bad Request` |
| Structured logs | Check log output | JSON with correlation_id |
| Dashboard loads | `GET /` (Streamlit) | `200 OK`, page renders |

---

## 15. Responsibility Matrix

| Area | Application Team | Infrastructure Team | Joint |
|------|------------------|---------------------|-------|
| Container image build | ✅ | | |
| Container image scan | | ✅ | |
| Kubernetes manifests | ✅ | ✅ | |
| TLS certificates | | ✅ | |
| Secret injection | ✅ (provide names) | ✅ (implement) | |
| Persistent volumes | | ✅ | |
| Network policies | | ✅ | |
| Log aggregation | ✅ (format) | ✅ (pipeline) | |
| Metrics/alerting | ✅ (endpoints) | ✅ (collection) | |
| Model training | ✅ | | |
| Model promotion | ✅ | | |
| Backup scheduling | | ✅ | |
| Incident response | ✅ (app) | ✅ (infra) | ✅ |

---

*End of Production Deployment Checklist*