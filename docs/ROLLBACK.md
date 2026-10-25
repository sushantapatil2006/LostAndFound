# Production Rollback & Disaster Recovery Procedures

This document provides instructions for rolling back application versions in production, handling failed releases, and recovering data from backups.

---

## 1. Automated Rollback Behavior

During an automated deployment via `./scripts/deploy.sh <COMMIT_SHA>`:
1. The currently running release version is recorded in `/opt/lostandfound/.previous_release`.
2. The new Docker images are pulled and launched.
3. Health checks verify `http://127.0.0.1:8080/healthz` and `http://127.0.0.1:8080/api/health`.
4. If health checks fail after 15 consecutive attempts (45 seconds):
   * Diagnostic logs are printed to standard error.
   * `deploy.sh` automatically reads `.previous_release` and rolls back containers to the prior working commit SHA.
   * Named persistent Docker volumes (`mysql-data`) are **strictly preserved** throughout the entire process.
   * The script exits with status `1`, causing the GitHub Actions deployment workflow to fail visibly.

---

## 2. Manual Rollback Procedure

If a bug is discovered after deployment has succeeded, an operator can roll back to any prior release version using the steps below.

### Step 1: Connect to the Production VM
```bash
gcloud compute ssh <VM_NAME> --zone=<ZONE> --tunnel-through-iap
cd /opt/lostandfound
```

### Step 2: Determine Previous Image Tag
Inspect the recorded previous release or check the Git history:
```bash
cat .previous_release
# Example output: e3b89fa2d948123...
```
Or view the list of pulled Docker images on the host:
```bash
docker images --filter=reference='ghcr.io/sushantapatil2006/lostandfound-backend'
```

### Step 3: Execute Rollback
Execute `deploy.sh` specifying the known good Git commit SHA:
```bash
./scripts/deploy.sh <KNOWN_GOOD_COMMIT_SHA>
```

Alternatively, manually restart services with the desired tag:
```bash
export IMAGE_TAG=<KNOWN_GOOD_COMMIT_SHA>
docker compose -f docker-compose.prod.yml pull frontend api
docker compose -f docker-compose.prod.yml up -d --remove-orphans
```

### Step 4: Verify Service Health
Confirm all containers are healthy:
```bash
docker compose -f docker-compose.prod.yml ps
curl -i http://127.0.0.1:8080/api/health
```

---

## 3. Database Disaster Recovery

If database data is corrupted or accidentally deleted, restore from the latest daily compressed backup:

### Step 1: Locate the Backup File
```bash
ls -la /opt/backups/
```
Example: `/opt/backups/lostandfound_db_2026-10-25_020000.sql.gz`

### Step 2: Restore the MySQL Dump
Stream the uncompressed SQL directly into the running MySQL container:
```bash
cd /opt/lostandfound

# Source environment variables to obtain database credentials
set -a && source .env && set +a

gunzip < /opt/backups/lostandfound_db_2026-10-25_020000.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T \
    -e MYSQL_PWD="$MYSQL_PASSWORD" \
    mysql mysql -u "$MYSQL_USER" "$MYSQL_DATABASE"
```

### Step 3: Verify Application State
```bash
# Verify API queries items successfully
curl -s http://127.0.0.1:8080/api/items | jq .
```
The database is restored, and the application resumes normal operation without downtime on the frontend.
