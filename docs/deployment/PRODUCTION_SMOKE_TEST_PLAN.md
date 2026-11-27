# Production Smoke Test Plan

**Project:** EduPro Predictive Analytics Platform  
**Version:** 1.3.0  
**Milestone:** R4.7 – Deployment Preparation & Infrastructure Handover  

This document defines verification procedures for production deployment. Each test includes the command, expected result, and failure handling.

---

## Test Environment

| Variable | Value |
|----------|-------|
| API Base URL | `https://api.example.com` (replace with actual) |
| Dashboard URL | `https://dashboard.example.com` (replace with actual) |
| Valid API Key | Injected via secret store |
| Invalid API Key | `invalid-key-for-testing` |

---

## 1. Health Endpoints

### 1.1 GET /health/live (Liveness Probe)

**Purpose:** Verify the application process is running.

**Command:**
```bash
curl -f -s -w "\nHTTP %{http_code}\n" https://api.example.com/health/live
```

**Expected Result:**
- HTTP 200
- JSON response:
```json
{
  "status": "alive",
  "model_available": false,
  "model_name": null,
  "model_version": null
}
```

**Headers:** `X-Correlation-ID`, `X-Process-Time` present

**Failure Handling:**
- HTTP 5xx or timeout → Pod unhealthy, will be restarted by kubelet
- Check pod logs: `kubectl logs <pod> --previous`
- Verify container startup command

---

### 1.2 GET /health/ready (Readiness Probe)

**Purpose:** Verify the service can serve predictions.

**Command:**
```bash
curl -f -s -w "\nHTTP %{http_code}\n" https://api.example.com/health/ready
```

**Expected Result (Ready):**
- HTTP 200
- JSON response:
```json
{
  "status": "ready",
  "checks": {
    "model_loaded": true,
    "model_load_error": false,
    "registry_accessible": true,
    "active_model_registered": true
  },
  "model_name": "enrollment_model_candidate",
  "model_version": "enrollment_model_phase1.pkl"
}
```

**Expected Result (Not Ready):**
- HTTP 503
- JSON with `status: "not_ready"` and failed checks

**Failure Handling:**
| Failed Check | Action |
|--------------|--------|
| `model_loaded: false` | Check model artifact exists in `/app/models/registry/versions/` |
| `model_load_error: true` | Check logs for `ModelLoadError`, restore artifact |
| `registry_accessible: false` | Verify volume mount `/app/models/registry`, check permissions |
| `active_model_registered: false` | Run `edup-retrain promote <version>` |

---

### 1.3 GET /health (General Health)

**Purpose:** General status with model information.

**Command:**
```bash
curl -f -s https://api.example.com/health | jq .
```

**Expected Result (Healthy):**
- HTTP 200
```json
{
  "status": "healthy",
  "model_available": true,
  "model_name": "enrollment_model_candidate",
  "model_version": "enrollment_model_phase1.pkl"
}
```

**Expected Result (Degraded):**
- HTTP 200
```json
{
  "status": "degraded",
  "model_available": false,
  "model_name": null,
  "model_version": null
}
```

**Failure Handling:**
- `degraded` → Model not loaded, check `/health/ready` for details
- HTTP 5xx → Check liveness first

---

## 2. Model Information Endpoints

### 2.1 GET /model-info

**Purpose:** Retrieve model metadata (requires authentication).

**Command:**
```bash
curl -f -s -H "X-API-Key: <valid-key>" https://api.example.com/model-info | jq .
```

**Expected Result:**
- HTTP 200
- JSON with: `model_name`, `model_type`, `model_version`, `status`, `feature_names`, `target_variable`, `training_date_utc`, `metrics`, `notes`, `registry_version`, `active_since_utc`
- No filesystem paths, secrets, or sensitive data

**Failure Handling:**
- HTTP 401 → Invalid/missing API key
- HTTP 503 → Model not available (check `/health/ready`)

---

### 2.2 GET /model-registry

**Purpose:** List all registered model versions.

**Command:**
```bash
curl -f -s -H "X-API-Key: <valid-key>" https://api.example.com/model-registry | jq .
```

**Expected Result:**
- HTTP 200
- JSON with `versions` array (newest first)
- Each version: `version`, `model_name`, `model_type`, `artifact_filename`, `status`, `training_date_utc`, `target_variable`, `feature_names`, `metrics`, `artifact_sha256`, `promoted_at_utc`, `promoted_by`

**Failure Handling:**
- HTTP 401 → Auth issue
- Empty versions → Registry not populated

---

### 2.3 GET /model-registry/{version}

**Purpose:** Get specific version details.

**Command:**
```bash
VERSION=$(curl -s -H "X-API-Key: <valid-key>" https://api.example.com/model-registry | jq -r '.versions[0].version')
curl -f -s -H "X-API-Key: <valid-key>" "https://api.example.com/model-registry/$VERSION" | jq .
```

**Expected Result:**
- HTTP 200
- Full version metadata

**Failure Handling:**
- HTTP 404 → Version not found
- HTTP 401 → Auth issue

---

## 3. Prediction Endpoint

### 3.1 POST /predict/enrollment (Valid Request)

**Purpose:** Verify prediction functionality with valid input.

**Command:**
```bash
curl -f -s -X POST \
  -H "Content-Type: application/json" \
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
  https://api.example.com/predict/enrollment | jq .
```

**Expected Result:**
- HTTP 200
- JSON with:
```json
{
  "predicted_enrollment": 167.5,
  "model_name": "enrollment_model_candidate",
  "model_version": "enrollment_model_phase1.pkl",
  "features_used": ["CoursePrice", "CourseDuration", ...]
}
```
- `predicted_enrollment >= 0`

**Failure Handling:**
- HTTP 400/422 → Validation error (check request format)
- HTTP 401 → Auth issue
- HTTP 503 → Model not loaded
- HTTP 500 → Internal error (check logs)

---

### 3.2 POST /predict/enrollment (Free Course Normalization)

**Purpose:** Verify free course price normalization.

**Command:**
```bash
curl -f -s -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <valid-key>" \
  -d '{
    "course_category": "Programming",
    "course_level": "Beginner",
    "course_price": 99.0,
    "course_duration": 20.0,
    "teacher_experience": 5.0,
    "teacher_rating": 4.0,
    "course_type": "Free",
    "course_rating": 4.0,
    "payment_method": "Credit Card"
  }' \
  https://api.example.com/predict/enrollment | jq '.predicted_enrollment'
```

**Expected Result:**
- HTTP 200
- Prediction returned (price normalized to 0 internally)

---

## 4. Authentication

### 4.1 Missing API Key

**Purpose:** Verify authentication is enforced.

**Command:**
```bash
curl -s -w "\nHTTP %{http_code}\n" https://api.example.com/model-registry
```

**Expected Result:**
- HTTP 401
- JSON:
```json
{
  "error": "Unauthorized",
  "message": "Missing API key. Provide via 'X-API-Key' header.",
  "details": null
}
```
- Header: `WWW-Authenticate: ApiKey`

**Headers:** `X-Correlation-ID` present

---

### 4.2 Invalid API Key

**Purpose:** Verify invalid keys are rejected.

**Command:**
```bash
curl -s -w "\nHTTP %{http_code}\n" -H "X-API-Key: invalid-key" https://api.example.com/model-registry
```

**Expected Result:**
- HTTP 401
- JSON:
```json
{
  "error": "Unauthorized",
  "message": "Invalid API key.",
  "details": null
}
```

---

### 4.3 Valid API Key

**Purpose:** Verify valid key grants access.

**Command:**
```bash
curl -f -s -H "X-API-Key: <valid-key>" https://api.example.com/model-registry | jq '.versions | length'
```

**Expected Result:**
- HTTP 200
- Version count > 0

---

### 4.4 Health Endpoints Exempt

**Purpose:** Verify health endpoints don't require auth.

**Command:**
```bash
for endpoint in /health/live /health/ready /health /docs; do
  echo "Testing $endpoint..."
  curl -s -w "HTTP %{http_code}" "https://api.example.com$endpoint" | grep -q "HTTP 200" || { echo "FAIL: $endpoint"; exit 1; }
  echo "OK"
done
```

**Expected Result:** All HTTP 200 (or 503 for `/health/ready` if model not ready)

---

## 5. Rate Limiting

### 5.1 Rate Limit Enforcement

**Purpose:** Verify rate limiting blocks excess requests.

**Prerequisites:** `RATE_LIMIT_ENABLED=true`, `RATE_LIMIT_REQUESTS=3` (test value)

**Command:**
```bash
# Make 5 requests, first 3 should succeed, 4th and 5th should be 429
for i in {1..5}; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: <valid-key>" https://api.example.com/model-registry)
  echo "Request $i: $CODE"
done
```

**Expected Result:**
- Requests 1-3: HTTP 200
- Request 4: HTTP 429
- Request 5: HTTP 429
- Response includes `Retry-After` header (seconds)

**Response Format (429):**
```json
{
  "error": "RateLimitExceeded",
  "message": "Too many requests. Please try again later.",
  "details": {"retry_after_seconds": 60}
}
```

---

### 5.2 Rate Limit Exempt Paths

**Purpose:** Verify health endpoints bypass rate limiting.

**Command:**
```bash
# Make 10 requests to health endpoint (should all succeed)
for i in {1..10}; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" https://api.example.com/health/live)
  [ "$CODE" = "200" ] || { echo "FAIL: Request $i returned $CODE"; exit 1; }
done
echo "All health requests succeeded"
```

**Expected Result:** All HTTP 200

---

## 6. CORS

### 6.1 Allowed Origin

**Purpose:** Verify CORS allows configured origins.

**Command:**
```bash
curl -f -s -X OPTIONS \
  -H "Origin: https://app.example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -w "\nHTTP %{http_code}\n" \
  https://api.example.com/health/live
```

**Expected Result:**
- HTTP 200 or 204
- Header: `Access-Control-Allow-Origin: https://app.example.com`
- Header: `Access-Control-Allow-Methods: GET,POST,OPTIONS` (or configured)
- Header: `Access-Control-Allow-Headers: *` (or configured)

---

### 6.2 Blocked Origin

**Purpose:** Verify CORS blocks unconfigured origins.

**Command:**
```bash
curl -s -X OPTIONS \
  -H "Origin: https://evil.com" \
  -H "Access-Control-Request-Method: POST" \
  -w "\nHTTP %{http_code}\n" \
  https://api.example.com/health/live
```

**Expected Result:**
- No `Access-Control-Allow-Origin` header (or not `https://evil.com`)
- Browser would block; curl returns response but without CORS headers

---

## 7. Trusted Hosts

### 7.1 Allowed Host

**Purpose:** Verify trusted host middleware allows configured hosts.

**Command:**
```bash
curl -f -s -H "Host: api.example.com" https://api.example.com/health/live
```

**Expected Result:** HTTP 200

---

### 7.2 Blocked Host

**Purpose:** Verify trusted host middleware rejects unknown hosts.

**Command:**
```bash
curl -s -w "\nHTTP %{http_code}\n" -H "Host: evil.com" https://api.example.com/health/live
```

**Expected Result:** HTTP 400 (Bad Request)

---

## 8. Request Validation

### 8.1 Invalid Category

**Command:**
```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <valid-key>" \
  -d '{"course_category":"Invalid","course_level":"Beginner","course_price":99,"course_duration":20,"teacher_experience":5,"teacher_rating":4}' \
  https://api.example.com/predict/enrollment
```

**Expected Result:** HTTP 422 (validation error)

---

### 8.2 Price Out of Bounds

**Command:**
```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <valid-key>" \
  -d '{"course_category":"Programming","course_level":"Beginner","course_price":600,"course_duration":20,"teacher_experience":5,"teacher_rating":4}' \
  https://api.example.com/predict/enrollment
```

**Expected Result:** HTTP 422 with error message mentioning price bounds

---

### 8.3 Boolean Input Rejection

**Command:**
```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <valid-key>" \
  -d '{"course_category":"Programming","course_level":"Beginner","course_price":true,"course_duration":20,"teacher_experience":5,"teacher_rating":4}' \
  https://api.example.com/predict/enrollment
```

**Expected Result:** HTTP 422 with "must be a number, not boolean"

---

### 8.4 NaN/Inf Rejection

**Command:**
```bash
# Test via direct validation (NaN not valid JSON)
python3 -c "
from edup.features import validate_course_inputs
try:
    validate_course_inputs(course_category='Programming', course_level='Beginner', course_price=float('nan'), course_duration=20, teacher_experience=5, teacher_rating=4)
except ValueError as e:
    print('Correctly rejected:', e)
"
```

**Expected Result:** ValueError with "must be finite"

---

## 9. Correlation IDs

### 9.1 Custom Correlation ID Propagation

**Command:**
```bash
curl -f -s -H "X-Correlation-ID: test-smoke-123" -D - https://api.example.com/health/live -o /dev/null | grep -i "x-correlation-id"
```

**Expected Result:**
- Header: `X-Correlation-ID: test-smoke-123`
- Same value echoed back

### 9.2 Generated Correlation ID

**Command:**
```bash
curl -f -s -D - https://api.example.com/health/live -o /dev/null | grep -i "x-correlation-id"
```

**Expected Result:**
- Header: `X-Correlation-ID: <8-char-uuid-prefix>`
- Present on all responses

---

## 10. Structured Logs

### 10.1 JSON Log Format Verification

**Command:**
```bash
# Check recent pod logs
kubectl logs <pod> --tail=5 | jq -e 'has("timestamp") and has("level") and has("logger") and has("message") and has("correlation_id")'
```

**Expected Result:** Exit code 0 (all fields present)

### 10.2 Correlation ID in Logs

**Command:**
```bash
# Make request with known correlation ID
curl -s -H "X-Correlation-ID: log-test-456" https://api.example.com/health/live > /dev/null

# Check logs
kubectl logs <pod> --tail=10 | grep log-test-456 | jq .
```

**Expected Result:** Log entries contain `correlation_id: "log-test-456"`

---

## 11. Streamlit Dashboard

### 11.1 Health Check

**Command:**
```bash
curl -f https://dashboard.example.com/_stcore/health
```

**Expected Result:** HTTP 200, response `ok`

---

### 11.2 Main Page Load

**Command:**
```bash
curl -f -s https://dashboard.example.com/ | grep -q "EduPro Analytics"
```

**Expected Result:** HTTP 200, HTML contains "EduPro Analytics"

---

### 11.3 All Pages Accessible

**Command:**
```bash
for page in \
  "" \
  "?page=Course%20Demand%20Prediction" \
  "?page=Revenue%20Forecasting" \
  "?page=Feature%20Importance%20Explorer" \
  "?page=Category%20Analytics"; do
  echo "Testing page: $page"
  curl -f -s "https://dashboard.example.com/$page" > /dev/null || { echo "FAIL: $page"; exit 1; }
done
```

**Expected Result:** All pages HTTP 200

---

## 12. Model Availability

### 12.1 Model Loaded and Active

**Command:**
```bash
# Via API
curl -f -s -H "X-API-Key: <valid-key>" https://api.example.com/model-info | jq -e '.model_available == true and .model_version != null'

# Via CLI
kubectl exec -it <pod> -- python -m edup.models.retrain status | grep -q "Active version:"
```

**Expected Result:** Both commands succeed

---

### 12.2 Registry Integrity

**Command:**
```bash
kubectl exec -it <pod> -- python -c "
from edup.models import get_registry
registry = get_registry()
active = registry.get_active_version()
print(f'Active: {active.version if active else None}')
print(f'Total versions: {len(registry.list_versions())}')
# Verify artifact checksum
if active:
    import hashlib
    path = registry.registry_dir / 'versions' / active.version / active.artifact_filename
    sha = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha.update(chunk)
    print(f'Artifact SHA256 matches: {sha.hexdigest() == active.artifact_sha256}')
"
```

**Expected Result:** Active version exists, artifact checksum matches

---

## 13. Complete Automated Smoke Test Script

```bash
#!/bin/bash
# smoke_tests.sh - Run all production smoke tests
# Usage: API_KEY=<key> API_URL=https://api.example.com DASHBOARD_URL=https://dashboard.example.com ./smoke_tests.sh

set -euo pipefail

API_KEY="${API_KEY:-}"
API_URL="${API_URL:-https://api.example.com}"
DASHBOARD_URL="${DASHBOARD_URL:-https://dashboard.example.com}"

if [ -z "$API_KEY" ]; then
  echo "ERROR: API_KEY environment variable required"
  exit 1
fi

pass=0
fail=0

test_pass() { echo "✅ $1"; ((pass++)); }
test_fail() { echo "❌ $1"; ((fail++)); }

echo "=== EduPro Production Smoke Tests ==="
echo "API: $API_URL"
echo "Dashboard: $DASHBOARD_URL"
echo ""

# 1. Liveness
echo "1. Liveness Probe"
curl -sf "$API_URL/health/live" | jq -e '.status == "alive"' > /dev/null && test_pass "/health/live" || test_fail "/health/live"

# 2. Readiness
echo "2. Readiness Probe"
curl -sf "$API_URL/health/ready" | jq -e '.status == "ready"' > /dev/null && test_pass "/health/ready" || test_fail "/health/ready"

# 3. Model Info (auth)
echo "3. Model Info (Authenticated)"
curl -sf -H "X-API-Key: $API_KEY" "$API_URL/model-info" | jq -e '.model_name' > /dev/null && test_pass "/model-info" || test_fail "/model-info"

# 4. Model Registry
echo "4. Model Registry"
curl -sf -H "X-API-Key: $API_KEY" "$API_URL/model-registry" | jq -e '.versions | length > 0' > /dev/null && test_pass "/model-registry" || test_fail "/model-registry"

# 5. Prediction
echo "5. Prediction Endpoint"
curl -sf -X POST -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"course_category":"Programming","course_level":"Beginner","course_price":99,"course_duration":20,"teacher_experience":5,"teacher_rating":4}' \
  "$API_URL/predict/enrollment" | jq -e '.predicted_enrollment >= 0' > /dev/null && test_pass "/predict/enrollment" || test_fail "/predict/enrollment"

# 6. Auth Enforcement
echo "6. Auth Enforcement (401 without key)"
curl -s -o /dev/null -w "%{http_code}" "$API_URL/model-registry" | grep -q "401" && test_pass "Auth required" || test_fail "Auth required"

# 7. Invalid Key Rejection
echo "7. Invalid Key Rejection"
curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: invalid" "$API_URL/model-registry" | grep -q "401" && test_pass "Invalid key rejected" || test_fail "Invalid key rejected"

# 8. Correlation ID
echo "8. Correlation ID Propagation"
CORR=$(curl -sf -H "X-Correlation-ID: smoke-test-123" -D - "$API_URL/health/live" -o /dev/null | grep -i "x-correlation-id" | cut -d' ' -f2 | tr -d '\r')
[ "$CORR" = "smoke-test-123" ] && test_pass "Correlation ID preserved" || test_fail "Correlation ID preserved"

# 9. Rate Limiting (if enabled with low limit)
# Skipped - requires specific config

# 10. Dashboard
echo "10. Dashboard Health"
curl -sf "$DASHBOARD_URL/_stcore/health" | grep -q "ok" && test_pass "Dashboard health" || test_fail "Dashboard health"

echo "11. Dashboard Main Page"
curl -sf "$DASHBOARD_URL/" | grep -q "EduPro Analytics" && test_pass "Dashboard main page" || test_fail "Dashboard main page"

echo ""
echo "=== Results: $pass passed, $fail failed ==="
[ $fail -eq 0 ] || exit 1
```

---

## Failure Handling Summary

| Test | Failure Action |
|------|----------------|
| `/health/live` | Check pod logs, restart pod, verify container command |
| `/health/ready` | Check `checks` object, fix specific failure (model, registry) |
| Auth tests | Verify secret injection, `AUTH_ENABLED=true` |
| Rate limiting | Verify `RATE_LIMIT_ENABLED=true`, check exempt paths |
| CORS/Trusted hosts | Verify `CORS_ORIGINS`, `TRUSTED_HOSTS` config |
| Prediction | Check `/health/ready`, model artifact, logs |
| Dashboard | Check Streamlit pod, volume mounts, port 8501 |
| Logs | Verify `LOG_FORMAT=json`, correlation ID middleware |

---

*End of Production Smoke Test Plan*