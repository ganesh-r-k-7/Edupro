# Infrastructure Handover Document

**Project:** EduPro Predictive Analytics Platform  
**Version:** 1.3.0  
**Milestone:** R4.7 – Deployment Preparation & Infrastructure Handover  
**Date:** 2026-11-27  
**Git Commit:** `6e628da` (feat: harden EduPro for production deployment)  

---

## 1. Project Overview

EduPro is a predictive analytics platform for an online education marketplace. It provides:
- Course enrollment prediction via REST API
- Multi-page Streamlit dashboard for business analytics
- Automated model retraining with registry-based lifecycle management
- Revenue forecasting (cached Prophet output, not validated)

**Key architectural principle:** The platform is a research prototype. The enrollment model does not beat a mean baseline on the available data. All predictions are reference estimates, not personalized forecasts.

---

## 2. Application Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Load Balancer / TLS                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  API Pod 1      │ │  API Pod 2      │ │  API Pod N      │
│  (edupro-api)   │ │  (edupro-api)   │ │  (edupro-api)   │
│  Port 8000      │ │  Port 8000      │ │  Port 8000      │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
    ┌─────────────────────┐       ┌─────────────────────┐
    │  Persistent Volume  │       │  Persistent Volume  │
    │  /app/models        │       │  /app/data          │
    │  (ReadWriteMany)    │       │  (ReadOnlyMany)     │
    │  - Registry         │       │  - processed_data.  │
    │  - Artifacts        │       │    parquet/csv      │
    └─────────────────────┘       └─────────────────────┘
```

### 2.1 Components

| Component | Technology | Port | Replicas |
|-----------|------------|------|----------|
| REST API | FastAPI + Uvicorn | 8000 | 2+ (stateless) |
| Dashboard | Streamlit | 8501 | 1 (stateful session) |
| Model Registry | File-based (JSON + artifacts) | N/A | Shared volume |
| Retraining | CLI (`edup-retrain`) | N/A | CronJob / Manual |

---

## 3. Container Details

### 3.1 Docker Image
| Attribute | Value |
|-----------|-------|
| Image name | `edupro-api` |
| Base image | `python:3.12-slim` |
| Build | Multi-stage (builder + runtime) |
| Runtime user | `edupro` (non-root, UID/GID assigned at build) |
| Exposed port | 8000 |
| Health check | `curl -f http://localhost:8000/health/live` |
| Entry point | `uvicorn edup.api.main:app --host 0.0.0.0 --port 8000` |

### 3.2 Image Layers (Runtime Stage)
1. `python:3.12-slim` base
2. `curl` for health checks
3. Non-root user `edupro`
4. Copied site-packages from builder
5. Copied application source (`/app/src`)
6. Copied models directory structure
7. Created `/app/data`, `/app/models/registry` with correct ownership

### 3.3 Required Volumes
| Mount Path | Purpose | Access Mode | Size |
|------------|---------|-------------|------|
| `/app/models` | Model artifacts + registry | ReadWriteMany | 10 GiB |
| `/app/data` | Processed data (Parquet/CSV) | ReadOnlyMany | 5 GiB |
| `/app/app` | Streamlit app files (dashboard) | ReadOnly | ConfigMap |

---

## 4. API Endpoints

| Endpoint | Method | Auth | Rate Limited | Purpose |
|----------|--------|------|--------------|---------|
| `/` | GET | Exempt | Exempt | API info |
| `/health` | GET | Exempt | Exempt | General health |
| `/health/live` | GET | Exempt | Exempt | Liveness probe |
| `/health/ready` | GET | Exempt | Exempt | Readiness probe |
| `/model-info` | GET | Required | Yes | Model metadata |
| `/predict/enrollment` | POST | Required | Yes | Enrollment prediction |
| `/model-registry` | GET | Required | Yes | List registry versions |
| `/model-registry/{v}` | GET | Required | Yes | Version details |
| `/docs` | GET | Exempt | Exempt | Swagger UI (dev only) |
| `/openapi.json` | GET | Exempt | Exempt | OpenAPI spec (dev only) |

### 4.1 Request/Response Examples

**Prediction Request:**
```json
POST /predict/enrollment
{
  "course_category": "Programming",
  "course_level": "Beginner",
  "course_price": 99.0,
  "course_duration": 20.0,
  "teacher_experience": 5.0,
  "teacher_rating": 4.0,
  "course_type": "Paid",
  "course_rating": 4.0,
  "payment_method": "Credit Card"
}
```

**Prediction Response:**
```json
{
  "predicted_enrollment": 167.5,
  "model_name": "enrollment_model_candidate",
  "model_version": "enrollment_model_phase1.pkl",
  "features_used": ["CoursePrice", "CourseDuration", "CourseRating", "TeacherRating", "YearsOfExperience", "EncodedCourseLevel", "TeacherRatingScore", "CourseCategory", "CourseType", "PriceBand", "DurationBucket", "RatingTier", "ExperienceBucket"]
}
```

---

## 5. Storage Requirements

### 5.1 Model Registry (`/app/models/registry`)
```
registry/
├── registry_index.json          # Master index (atomic writes)
├── active_model.txt             # Path to active artifact (atomic)
├── .lock                        # File-based lock (runtime)
├── retraining_config.json       # Retraining configuration
├── logs/                        # Retraining job logs
└── versions/
    └── v<timestamp>/
        ├── <model>.pkl          # Model artifact (joblib)
        └── <model>_metadata.json # Metadata + checksum
```

**Size estimate:** ~500 MB per model version (XGBoost pipeline)

### 5.2 Processed Data (`/app/data`)
```
data/
├── processed_data.parquet       # Preferred (Parquet)
└── processed_data.csv           # Fallback (CSV)
```

**Size estimate:** ~50 MB

### 5.3 Volume Requirements
| Volume | Access Mode | Backup Frequency | Retention |
|--------|-------------|------------------|-----------|
| models | ReadWriteMany | Daily snapshot | 30 days |
| data | ReadOnlyMany | Weekly snapshot | 90 days |

---

## 6. Security Controls

### 6.1 Implemented (Application-Level)

| Control | Implementation | Configuration |
|---------|----------------|---------------|
| API Key Auth | Header-based (`X-API-Key`) | `AUTH_ENABLED=true`, `API_KEYS=key1,key2` |
| Rate Limiting | In-memory sliding window | `RATE_LIMIT_ENABLED=true`, `RATE_LIMIT_REQUESTS=100` |
| CORS | FastAPI CORSMiddleware | `CORS_ORIGINS=https://app.example.com` |
| Trusted Hosts | FastAPI TrustedHostMiddleware | `TRUSTED_HOSTS_ENABLED=true`, `TRUSTED_HOSTS=api.example.com` |
| Request Size Limit | Middleware (10 MB default) | `MAX_REQUEST_SIZE_MB=10` |
| Secure Errors | Generic responses, no stack traces | Always enabled |
| Structured Logs | JSON with correlation IDs | `LOG_FORMAT=json` |

### 6.2 Required Infrastructure-Level

| Control | Implementation | Responsibility |
|---------|----------------|----------------|
| TLS Termination | Load balancer / reverse proxy | Infrastructure |
| DDoS Protection | Cloud provider (AWS Shield, Cloudflare) | Infrastructure |
| Network Policies | Kubernetes NetworkPolicies / Security Groups | Infrastructure |
| Secret Management | Vault, AWS Secrets Manager, K8s Secrets | Infrastructure |
| Log Aggregation | Loki, ELK, CloudWatch, Datadog | Infrastructure |
| Metrics Collection | Prometheus + Grafana, DataDog | Infrastructure |
| Persistent Volumes | CSI driver (EBS, GCE PD, NFS) | Infrastructure |

---

## 7. Observability

### 7.1 Logging
- **Format:** JSON (production) / Text (development)
- **Fields:** `timestamp`, `level`, `logger`, `message`, `correlation_id`, extra
- **Correlation ID:** `X-Correlation-ID` header (generated or client-provided)
- **Request Timing:** `X-Process-Time` header (seconds)

### 7.2 Health Endpoints
| Endpoint | Purpose | Checks |
|----------|---------|--------|
| `/health/live` | Liveness | Process alive |
| `/health/ready` | Readiness | Model loaded, registry accessible, active model registered |
| `/health` | General | Model availability + status |

### 7.3 Metrics (Not Yet Implemented)
- No `/metrics` endpoint currently
- Would require `prometheus-client` integration
- Key metrics to add: request latency, prediction latency, error rates, model load time

---

## 8. Known Limitations

### 8.1 Rate Limiting (In-Memory)
- **Current:** Per-process in-memory token bucket
- **Impact:** Not shared across replicas; each pod has independent limit
- **Workaround:** Sticky sessions or single replica until Redis integration
- **Fix Required:** Redis-backed rate limiter for horizontal scaling

### 8.2 API Key Rotation
- **Current:** No built-in rotation mechanism
- **Impact:** Long-lived keys; rotation requires secret update + pod rollout
- **Fix Required:** External key management with rotation policy

### 8.3 Audit Logging
- **Current:** No dedicated audit trail
- **Impact:** Limited forensic capability for security events
- **Fix Required:** Add audit middleware for compliance requirements

### 8.4 Docker Build Verification
- **Status:** Not locally verified during R4.6 audit (Docker unavailable in environment)
- **Mitigation:** CI workflow includes `docker-build` job for GitHub Actions validation
- **Action Required:** Verify Docker build passes in CI before deployment

### 8.5 Public Deployment Requirements
- **TLS:** Required at load balancer (not in container)
- **Network Policies:** Required to restrict ingress/egress
- **DDoS Protection:** Required at infrastructure level
- **No IPv6:** Container only listens on IPv4 (0.0.0.0)

### 8.6 Model Performance
- **Status:** Enrollment model does not beat mean baseline
- **Impact:** Predictions are reference estimates, not personalized forecasts
- **Documentation:** Clearly communicated in API responses and dashboard

---

## 9. Infrastructure Dependencies

| Dependency | Purpose | Version/Requirement |
|------------|---------|---------------------|
| Kubernetes | Orchestration | 1.28+ |
| CSI Driver | Persistent volumes | Cloud-provider specific |
| Load Balancer | TLS termination, routing | nginx, ALB, Traefik, Cloudflare |
| Secret Store | API key management | Vault, AWS Secrets Manager, K8s Secrets |
| Log Aggregation | Structured log collection | Loki, ELK, CloudWatch, Datadog |
| Monitoring | Health/readiness alerts | Prometheus + Grafana, DataDog |
| Container Registry | Image storage | ECR, GCR, Docker Hub, Harbor |

---

## 10. Responsibility Matrix

| Area | Application Team | Infrastructure Team | Joint |
|------|------------------|---------------------|-------|
| Container image build | ✅ | | |
| Container image scan | | ✅ | |
| Kubernetes manifests | ✅ | ✅ | |
| TLS certificates | | ✅ | |
| Secret injection | ✅ (names) | ✅ (implementation) | |
| Persistent volumes | | ✅ | |
| Network policies | | ✅ | |
| Log aggregation | ✅ (format) | ✅ (pipeline) | |
| Metrics/alerting | ✅ (endpoints) | ✅ (collection) | |
| Model training | ✅ | | |
| Model promotion | ✅ | | |
| Backup scheduling | | ✅ | |
| Incident response | ✅ (app) | ✅ (infra) | ✅ |

---

## 11. Outstanding Decisions Requiring Infrastructure Team Approval

| Decision | Options | Recommendation |
|----------|---------|----------------|
| Rate limiting at scale | Redis-backed limiter vs. single replica | Redis-backed (requires development) |
| Secret management platform | Vault vs. AWS Secrets Manager vs. K8s Secrets | Align with org standard |
| Log aggregation platform | Loki vs. ELK vs. CloudWatch vs. Datadog | Align with org standard |
| Multi-region deployment | Active-passive vs. active-active | Active-passive for R4.7 |
| Model serving optimization | Dedicated model server (TorchServe, Triton) vs. current | Evaluate for high throughput |
| Automated model promotion | Threshold-based vs. manual approval | Manual approval for R4.7 |

---

## 12. Contact Information

| Role | Contact |
|------|---------|
| Application Development | [Team Slack/Email] |
| Data Science / Model Training | [Team Slack/Email] |
| Infrastructure On-Call | [PagerDuty/Slack] |
| Security Team | [Slack/Email] |

---

*End of Infrastructure Handover Document*