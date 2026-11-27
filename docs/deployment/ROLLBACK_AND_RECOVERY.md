# Rollback and Recovery Procedures

**Project:** EduPro Predictive Analytics Platform  
**Version:** 1.3.0  
**Milestone:** R4.7 – Deployment Preparation & Infrastructure Handover  

---

## 1. Overview

This document covers rollback and recovery procedures for:
- Application code rollback
- Container image rollback
- Model registry rollback (active model)
- Model artifact recovery
- Data backup and restoration
- Configuration recovery
- Health-check failures

**Critical distinction:** Application code rollback ≠ Model rollback. They are independent operations.

---

## 2. Application Code Rollback

### 2.1 Container Image Rollback

```bash
# List available image tags
docker images <registry>/edupro-api --format "table {{.Tag}}\t{{.CreatedAt}}"

# Rollback Kubernetes deployment
kubectl rollout undo deployment/edupro-api

# Or rollback to specific revision
kubectl rollout history deployment/edupro-api
kubectl rollout undo deployment/edupro-api --to-revision=<N>

# Verify rollout
kubectl rollout status deployment/edupro-api
```

### 2.2 Git-Based Rollback (If Needed)
```bash
# Identify commit to rollback to
git log --oneline -10

# Create revert commit (preserves history)
git revert <commit-hash>

# Or reset (rewrites history - ONLY if not pushed)
# git reset --hard <commit-hash> && git push --force-with-lease

# Rebuild and deploy
docker build -t edupro-api:<new-tag> .
docker push <registry>/edupro-api:<new-tag>
kubectl set image deployment/edupro-api api=<registry>/edupro-api:<new-tag>
```

### 2.3 Verification After Rollback
```bash
# Wait for rollout
kubectl rollout status deployment/edupro-api

# Verify health
curl -f https://api.example.com/health/live
curl -f https://api.example.com/health/ready

# Verify version
curl -f https://api.example.com/health
# Check model_version matches expected
```

---

## 3. Model Registry Rollback

### 3.1 Difference: Application vs Model Rollback

| Aspect | Application Rollback | Model Rollback |
|--------|---------------------|----------------|
| What changes | Container image, code, config | Active model artifact + metadata |
| Triggered by | Code bug, config error, security issue | Model performance degradation, data drift |
| Tool | `kubectl rollout undo` / CI redeploy | `edup-retrain rollback` CLI |
| Downtime | Pod restart (seconds) | Instant (registry pointer swap) |
| Data impact | None | Changes predictions immediately |

### 3.2 Model Rollback via CLI

```bash
# Check current status
python -m edup.models.retrain status

# Rollback to previous active version (automatic)
python -m edup.models.retrain rollback

# Rollback to specific version
python -m edup.models.retrain rollback v20261120_100000_123456
```

### 3.3 Model Rollback via API (If Endpoint Added)
```bash
# Not currently implemented as API endpoint
# Use CLI inside container:
kubectl exec -it <pod> -- python -m edup.models.retrain rollback
```

### 3.4 What Model Rollback Does
1. Validates target version (checksum, metadata, feature contract)
2. Demotes current active → `legacy`
3. Promotes target → `active`
4. Updates `active_model.txt` atomically
5. Updates `registry_index.json`

### 3.5 Verification After Model Rollback
```bash
# Check new active model
python -m edup.models.retrain status

# Verify predictions use new model
curl -X POST -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"course_category":"Programming","course_level":"Beginner","course_price":99,"course_duration":20,"teacher_experience":5,"teacher_rating":4}' \
  https://api.example.com/predict/enrollment
# Check model_version in response matches rolled-back version
```

---

## 4. Model Artifact Recovery

### 4.1 From Registry Versions Directory
```bash
# List available versions
ls -la /app/models/registry/versions/

# Each version has:
# - <model>.pkl (artifact)
# - <model>_metadata.json (metadata with checksum)

# Verify artifact integrity
python -c "
from edup.models.metadata import compute_file_sha256
import json
with open('/app/models/registry/versions/v20261120_100000/enrollment_model_phase1_metadata.json') as f:
    meta = json.load(f)
actual = compute_file_sha256('/app/models/registry/versions/v20261120_100000/enrollment_model_phase1.pkl')
print('Match:', actual == meta['artifact_sha256'])
"
```

### 4.2 Re-register Lost Artifact
```bash
# If artifact deleted but metadata exists
python -c "
from edup.models import get_registry
registry = get_registry()
# Re-register from backup location
registry.register_model(
    model_name='enrollment_model_candidate',
    model_type='RandomForest',
    artifact_path='/backup/models/enrollment_model_phase1.pkl',
    status='candidate',
    training_date_utc='2026-11-20T10:00:00+00:00',
    target_variable='EnrollmentCount (course-level)',
    feature_names=<from metadata>,
    metrics=<from metadata>,
    training_data=None,
    notes='Recovered from backup'
)
"
```

### 4.3 From Backup Storage
```bash
# Restore from volume snapshot / object storage
# 1. Restore PVC from snapshot
# 2. Or extract tarball to /app/models/registry
tar -xzf edupro-registry-backup-20261127.tar.gz -C /app/models/registry

# Verify registry integrity
python -m edup.models.retrain status
```

---

## 5. Data Backup and Restoration

### 5.1 Processed Data Backup
```bash
# Backup processed data (Parquet + CSV)
tar -czf edupro-data-backup-$(date +%Y%m%d).tar.gz -C /app/data .

# Or use volume snapshot (preferred)
# AWS: aws ec2 create-snapshot --volume-id <vol-id>
# GCP: gcloud compute disks snapshot <disk-name>
```

### 5.2 Restore Processed Data
```bash
# From tarball
tar -xzf edupro-data-backup-20261127.tar.gz -C /app/data

# From volume snapshot
# 1. Create new volume from snapshot
# 2. Attach to pod / update PVC
```

### 5.3 Raw Data (Excel Source)
- Stored in repository: `data/EduPro_Online_Platform.xlsx`
- Not mounted in production container
- Rebuild processed data via pipeline if needed:
```bash
python notebooks/01_data_preprocessing.py
python notebooks/03_feature_engineering.py
```

---

## 6. Configuration Recovery

### 6.1 Environment Variables
```bash
# Kubernetes: stored in ConfigMap/Secret
kubectl get configmap edupro-api-config -o yaml
kubectl get secret edupro-api-secrets -o yaml

# Backup
kubectl get configmap edupro-api-config -o yaml > config-backup.yaml
kubectl get secret edupro-api-secrets -o yaml > secrets-backup.yaml
# (Secrets backup requires base64 decode for actual values)
```

### 6.2 Application Config Recovery
```bash
# Restore from backup
kubectl apply -f config-backup.yaml
kubectl apply -f secrets-backup.yaml

# Restart pods to pick up changes
kubectl rollout restart deployment/edupro-api
```

### 6.3 Retraining Configuration
```bash
# Stored in registry: /app/models/registry/retraining_config.json
cat /app/models/registry/retraining_config.json

# Backup
cp /app/models/registry/retraining_config.json /backup/retraining_config.json

# Restore
cp /backup/retraining_config.json /app/models/registry/retraining_config.json
```

---

## 7. Health-Check Failure Recovery

### 7.1 Liveness Failure (Pod Restart)

**Symptoms:** Pod `CrashLoopBackOff` or liveness probe failing

**Diagnosis:**
```bash
kubectl logs <pod> --previous
kubectl describe pod <pod>
```

**Common Causes & Fixes:**

| Cause | Symptom | Fix |
|-------|---------|-----|
| Invalid production config | `RuntimeError: Production configuration invalid` | Fix ConfigMap/Secret, restart |
| Missing model artifact | `No compatible enrollment model found` | Restore registry, restart |
| Port conflict | `Address already in use` | Check port 8000, fix conflicts |
| OOM kill | `OOMKilled` | Increase memory limit |

**Recovery:**
```bash
# Fix config
kubectl edit configmap edupro-api-config
# Or fix secret
kubectl edit secret edupro-api-secrets

# Restart
kubectl delete pod <pod>  # Let deployment recreate
# Or
kubectl rollout restart deployment/edupro-api
```

### 7.2 Readiness Failure (Traffic Not Routed)

**Symptoms:** Pod `Running` but not `Ready`, service returns 503

**Diagnosis:**
```bash
curl http://<pod-ip>:8000/health/ready
# Check checks object for which failed
```

**Common Causes & Fixes:**

| Check | Failure Meaning | Fix |
|-------|-----------------|-----|
| `model_loaded: false` | Model not loaded | Check logs for load error, restore model |
| `model_load_error: true` | Load exception | Fix model artifact, restart |
| `registry_accessible: false` | Registry I/O error | Check volume mount, permissions |
| `active_model_registered: false` | No active model | Promote a model via `edup-retrain promote` |

**Recovery:**
```bash
# Promote a model if none active
kubectl exec -it <pod> -- python -m edup.models.retrain promote <version>

# Or fix volume mount
kubectl describe pvc edupro-models-pvc

# Restart after fix
kubectl delete pod <pod>
```

### 7.3 Complete Health Check Failure Matrix

| Endpoint | Status | Action |
|----------|--------|--------|
| `/health/live` | 200 | OK - process alive |
| `/health/live` | 5xx/timeout | Pod unhealthy - will restart |
| `/health/ready` | 200 | OK - serving traffic |
| `/health/ready` | 503 | Not ready - check `checks` object |
| `/health` | 200, degraded | Model unavailable - check registry |
| `/health` | 503 | Critical - check liveness first |

---

## 8. Incident Escalation

### 8.1 Severity Levels

| Severity | Definition | Response Time | Escalation |
|----------|------------|---------------|------------|
| SEV-1 | Service down, no predictions | 15 min | Page on-call + team lead |
| SEV-2 | Degraded (model unavailable, high latency) | 1 hour | Notify team lead |
| SEV-3 | Minor (single endpoint slow, non-critical) | 4 hours | Ticket in backlog |

### 8.2 Escalation Contacts

| Role | Contact Method |
|------|----------------|
| Application On-Call | PagerDuty / Slack |
| Infrastructure On-Call | PagerDuty / Slack |
| Team Lead | Slack / Email |
| Data Science Lead | Slack / Email |

### 8.3 Runbook Links
- This document: `docs/deployment/ROLLBACK_AND_RECOVERY.md`
- Deployment runbook: `docs/deployment/DEPLOYMENT_RUNBOOK.md`
- Production checklist: `docs/deployment/PRODUCTION_DEPLOYMENT_CHECKLIST.md`

---

## 9. Recovery Time Objectives

| Component | RTO | RPO |
|-----------|-----|-----|
| Application (code) | 10 min | 0 (git) |
| Container image | 5 min | 0 (registry) |
| Active model | 2 min | 0 (registry) |
| Model registry | 30 min | 24 hours (daily snapshot) |
| Processed data | 1 hour | 24 hours (daily snapshot) |
| Configuration | 5 min | 0 (ConfigMap/Secret) |

---

## 10. Disaster Recovery Scenarios

### 10.1 Complete Cluster Loss
1. Provision new cluster
2. Deploy from GitOps manifests
3. Restore PVCs from snapshots
4. Inject secrets
5. Verify health endpoints
6. Run smoke tests

### 10.2 Region Outage
1. Failover to secondary region (if multi-region)
2. Update DNS / load balancer
3. Verify data consistency

### 10.3 Data Corruption
1. Stop application (scale to 0)
2. Restore `/app/models` and `/app/data` from last known good snapshot
3. Verify registry integrity
4. Restart application
4. Verify predictions

---

*End of Rollback and Recovery Procedures*