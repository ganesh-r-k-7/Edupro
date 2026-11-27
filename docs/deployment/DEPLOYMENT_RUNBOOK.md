# Deployment Runbook

**Project:** EduPro Predictive Analytics Platform  
**Version:** 1.3.0  
**Milestone:** R4.7 – Deployment Preparation & Infrastructure Handover  

---

## 1. Pre-Deployment Checks

### 1.1 Repository Verification
```bash
# Verify clean working tree
git status

# Verify correct commit
git log --oneline -1
# Should show: 6e628da feat: harden EduPro for production deployment

# Verify origin sync
git fetch origin
git diff HEAD origin/main
# Should show no differences
```

### 1.2 Dependency Verification
```bash
# Verify lockfile exists
ls -la requirements.lock

# Verify Python version compatibility
python3 --version
# Should be 3.12.x
```

### 1.3 Infrastructure Readiness
- [ ] Kubernetes cluster / container platform accessible
- [ ] Persistent volumes provisioned (models, data)
- [ ] Load balancer configured with TLS
- [ ] Secret store configured with `API_KEYS`
- [ ] Log aggregation pipeline ready
- [ ] Monitoring/alerting configured for health endpoints
- [ ] Network policies applied

---

## 2. Environment Preparation

### 2.1 Create Production Environment File
```bash
# Create .env.production (DO NOT COMMIT)
cat > .env.production <<'EOF'
ENVIRONMENT=production
AUTH_ENABLED=true
API_KEYS=<INJECT_FROM_SECRET_STORE>
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
DATA_DIR=/app/data
MODELS_DIR=/app/models
REGISTRY_DIR=/app/models/registry
MAX_REQUEST_SIZE_MB=10
EOF
```

### 2.2 Kubernetes ConfigMap/Secret Example
```yaml
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
  DATA_DIR: "/app/data"
  MODELS_DIR: "/app/models"
  REGISTRY_DIR: "/app/models/registry"
  MAX_REQUEST_SIZE_MB: "10"
---
apiVersion: v1
kind: Secret
metadata:
  name: edupro-api-secrets
type: Opaque
stringData:
  API_KEYS: "<key1>,<key2>,<key3>"
```

---

## 3. Secret Configuration

### 3.1 Generate API Keys
```bash
# Run locally, never in CI/CD logs
for i in {1..3}; do openssl rand -hex 32; done
# Output: three 64-character hex strings
# Join with commas: key1,key2,key3
```

### 3.2 Inject into Platform
| Platform | Command |
|----------|---------|
| Kubernetes | `kubectl create secret generic edupro-api-secrets --from-literal=API_KEYS="key1,key2,key3"` |
| AWS Secrets Manager | `aws secretsmanager create-secret --name edupro/api-keys --secret-string "key1,key2,key3"` |
| Docker Compose | Add to `.env` file (dev only) |

### 3.3 Verify Injection
```bash
# In running container
kubectl exec -it <pod> -- env | grep API_KEYS
# Should show comma-separated keys
```

---

## 4. Container Image Build and Verification

### 4.1 Build Image
```bash
# Build with tag
docker build -t edupro-api:1.3.0 .

# Or with BuildKit for better caching
DOCKER_BUILDKIT=1 docker build -t edupro-api:1.3.0 .
```

### 4.2 Verify Image Locally
```bash
# Test import
docker run --rm --entrypoint python edupro-api:1.3.0 -c "import edup.api.main; print('Import OK')"

# Test startup (dev mode)
docker run -d --name edupro-verify \
  -e ENVIRONMENT=development \
  -e AUTH_ENABLED=false \
  -e RATE_LIMIT_ENABLED=false \
  -p 8000:8000 \
  edupro-api:1.3.0

sleep 10
curl -f http://localhost:8000/health/live
docker stop edupro-verify && docker rm edupro-verify
```

### 4.3 Push to Registry
```bash
# Tag for registry
docker tag edupro-api:1.3.0 <registry>/edupro-api:1.3.0

# Push
docker push <registry>/edupro-api:1.3.0
```

### 4.4 CI Verification
The GitHub Actions `docker-build` job in `.github/workflows/ci.yml` performs:
- Multi-stage build with cache
- Import verification
- Health check verification

---

## 5. Persistent Storage Configuration

### 5.1 Verify Volume Mounts
```bash
# Kubernetes: check PVC binding
kubectl get pvc -n <namespace>
# Should show: edupro-models-pvc Bound, edupro-data-pvc Bound

# Verify mount in pod
kubectl exec -it <pod> -- ls -la /app/models /app/data
```

### 5.2 Required Directory Structure
```bash
# In /app/models (ReadWrite)
/app/models/
├── registry/
│   ├── registry_index.json
│   ├── active_model.txt
│   └── versions/
└── (legacy .pkl files if any)

# In /app/data (ReadOnly)
/app/data/
├── processed_data.parquet   # Preferred
└── processed_data.csv       # Fallback
```

### 5.3 Populate Model Registry
```bash
# Option 1: Run retraining in-cluster (requires data)
kubectl exec -it <pod> -- python -m edup.models.retrain retrain --auto-promote=false

# Option 2: Mount pre-populated registry volume
# Ensure registry_index.json, active_model.txt, versions/ exist
```

---

## 6. Application Startup

### 6.1 Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: edupro-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: edupro-api
  template:
    metadata:
      labels:
        app: edupro-api
    spec:
      containers:
        - name: api
          image: <registry>/edupro-api:1.3.0
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: edupro-api-config
            - secretRef:
                name: edupro-api-secrets
          volumeMounts:
            - name: models
              mountPath: /app/models
            - name: data
              mountPath: /app/data
              readOnly: true
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 3
      volumes:
        - name: models
          persistentVolumeClaim:
            claimName: edupro-models-pvc
        - name: data
          persistentVolumeClaim:
            claimName: edupro-data-pvc
```

### 6.2 Deploy
```bash
kubectl apply -f deployment.yaml
kubectl rollout status deployment/edupro-api
```

---

## 7. API Health Verification

### 7.1 Liveness Check
```bash
# Should return 200 immediately after container start
curl -f http://<api-url>/health/live
# Expected: {"status":"alive","model_available":false,"model_name":null,"model_version":null}
```

### 7.2 Readiness Check
```bash
# May return 503 until model is loaded
curl -f http://<api-url>/health/ready
# Expected when ready:
# {
#   "status": "ready",
#   "checks": {
#     "model_loaded": true,
#     "model_load_error": false,
#     "registry_accessible": true,
#     "active_model_registered": true
#   },
#   "model_name": "...",
#   "model_version": "..."
# }
```

### 7.3 General Health
```bash
curl -f http://<api-url>/health
# Expected: {"status":"healthy","model_available":true,"model_name":"...","model_version":"..."}
```

---

## 8. Readiness Verification

### 8.1 Model Availability
```bash
curl -H "X-API-Key: <valid-key>" http://<api-url>/model-info
# Should return 200 with model metadata
```

### 8.2 Registry Accessibility
```bash
curl -H "X-API-Key: <valid-key>" http://<api-url>/model-registry
# Should return 200 with version list
```

### 8.3 Prediction Endpoint
```bash
curl -X POST -H "Content-Type: application/json" \
  -H "X-API-Key: <valid-key>" \
  -d '{
    "course_category": "Programming",
    "course_level": "Beginner",
    "course_price": 99.0,
    "course_duration": 20.0,
    "teacher_experience": 5.0,
    "teacher_rating": 4.0,
    "course_type": "Paid",
    "course_rating": 4.0,
    "payment_method": "Credit Card"
  }' \
  http://<api-url>/predict/enrollment
# Should return 200 with prediction
```

---

## 9. Streamlit Dashboard Verification

### 9.1 Deploy Dashboard (Separate Deployment)
```yaml
# Separate deployment for Streamlit
apiVersion: apps/v1
kind: Deployment
metadata:
  name: edupro-dashboard
spec:
  replicas: 1
  selector:
    matchLabels:
      app: edupro-dashboard
  template:
    metadata:
      labels:
        app: edupro-dashboard
    spec:
      containers:
        - name: dashboard
          image: <registry>/edupro-api:1.3.0
          command: ["streamlit", "run", "app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
          ports:
            - containerPort: 8501
          envFrom:
            - configMapRef:
                name: edupro-api-config
          volumeMounts:
            - name: models
              mountPath: /app/models
            - name: data
              mountPath: /app/data
              readOnly: true
            - name: app
              mountPath: /app/app
              readOnly: true
      volumes:
        - name: models
          persistentVolumeClaim:
            claimName: edupro-models-pvc
        - name: data
          persistentVolumeClaim:
            claimName: edupro-data-pvc
        - name: app
          configMap:
            name: edupro-app-files
```

### 9.2 Verify Dashboard
```bash
# Health endpoint
curl -f http://<dashboard-url>/_stcore/health

# Main page
curl -f http://<dashboard-url>/
# Should return HTML with "EduPro Analytics"
```

---

## 10. Model Registry Verification

### 10.1 Check Active Model
```bash
# Via API
curl -H "X-API-Key: <valid-key>" http://<api-url>/model-info

# Via CLI (in container)
kubectl exec -it <pod> -- python -m edup.models.retrain status
```

### 10.2 Expected Output
```
=== EduPro Model Registry Status ===
Registry directory: /app/models/registry
Active version: v20261127_120000_123456
  Model: enrollment_model_candidate
  Artifact: enrollment_model_phase1.pkl
  Training date: 2026-11-27T12:00:00+00:00
  Promoted at: 2026-11-27T12:05:00+00:00
  Promoted by: manual
  Status: active
  Test RMSE: 14.07, MAE: 11.46, R2: -0.09
```

---

## 11. Post-Deployment Smoke Tests

### 11.1 Automated Smoke Test Script
```bash
#!/bin/bash
set -e

API_URL="https://api.example.com"
DASHBOARD_URL="https://dashboard.example.com"
API_KEY="<valid-key>"

echo "=== EduPro Post-Deployment Smoke Tests ==="

# 1. Liveness
echo "Testing /health/live..."
curl -sf "$API_URL/health/live" | jq -e '.status == "alive"'
echo "✅ Liveness OK"

# 2. Readiness
echo "Testing /health/ready..."
curl -sf "$API_URL/health/ready" | jq -e '.status == "ready"'
echo "✅ Readiness OK"

# 3. Model info (authenticated)
echo "Testing /model-info..."
curl -sf -H "X-API-Key: $API_KEY" "$API_URL/model-info" | jq -e '.model_name'
echo "✅ Model info OK"

# 4. Prediction
echo "Testing /predict/enrollment..."
curl -sf -X POST -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"course_category":"Programming","course_level":"Beginner","course_price":99,"course_duration":20,"teacher_experience":5,"teacher_rating":4}' \
  "$API_URL/predict/enrollment" | jq -e '.predicted_enrollment >= 0'
echo "✅ Prediction OK"

# 5. Auth enforcement
echo "Testing auth enforcement..."
curl -s -o /dev/null -w "%{http_code}" "$API_URL/model-registry" | grep -q "401"
echo "✅ Auth enforced (401 without key)"

# 6. Rate limiting
echo "Testing rate limiting (3 requests)..."
for i in {1..4}; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" "$API_URL/model-registry")
  if [ "$i" -le 3 ]; then
    [ "$CODE" = "200" ] || { echo "❌ Request $i failed: $CODE"; exit 1; }
  else
    [ "$CODE" = "429" ] || { echo "❌ Request $i should be 429: $CODE"; exit 1; }
  fi
done
echo "✅ Rate limiting enforced"

# 7. Correlation ID
echo "Testing correlation ID..."
CORR_ID=$(curl -sf -H "X-Correlation-ID: test-smoke-123" "$API_URL/health/live" -o /dev/null -D - | grep -i "x-correlation-id" | cut -d' ' -f2 | tr -d '\r')
[ "$CORR_ID" = "test-smoke-123" ] || { echo "❌ Correlation ID not preserved"; exit 1; }
echo "✅ Correlation ID propagated"

# 8. Dashboard
echo "Testing dashboard..."
curl -sf "$DASHBOARD_URL/_stcore/health" | grep -q "ok"
echo "✅ Dashboard healthy"

echo "=== All Smoke Tests Passed ==="
```

### 11.2 Run Smoke Tests
```bash
chmod +x smoke_tests.sh
./smoke_tests.sh
```

---

## 12. Monitoring and Log Verification

### 12.1 Verify Structured Logs
```bash
# Check pod logs for JSON format
kubectl logs <pod> --tail=20 | jq .
# Should show JSON objects with timestamp, level, logger, correlation_id
```

### 12.2 Verify Correlation ID Propagation
```bash
# Make request with correlation ID
curl -H "X-Correlation-ID: verify-123" https://api.example.com/health/live

# Check logs for correlation ID
kubectl logs <pod> | grep verify-123 | jq .
# Should appear in log entries
```

### 12.3 Verify Metrics Collection
```bash
# If Prometheus configured
curl http://<pod>:8000/metrics  # Not implemented - would need prometheus-client
# Instead verify scrape targets in Prometheus UI
```

### 12.4 Verify Alerting
```bash
# Simulate readiness failure (scale down to 0 or stop model)
# Verify alert fires in Alertmanager/PagerDuty
```

---

*End of Deployment Runbook*