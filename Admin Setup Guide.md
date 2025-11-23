# IBRS Document Auto-Classifier - Admin Setup Guide

**Version:** 1.0
**Date:** January 2025

This guide provides step-by-step instructions for setting up and deploying the IBRS Document Auto-Classifier system on Google Cloud Platform.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [GCP Project Setup](#2-gcp-project-setup)
3. [Enable Required APIs](#3-enable-required-apis)
4. [Configure Service Accounts](#4-configure-service-accounts)
5. [Create Cloud Storage Buckets](#5-create-cloud-storage-buckets)
6. [Set Up Firestore](#6-set-up-firestore)
7. [Configure Secret Manager](#7-configure-secret-manager)
8. [Set Up Zoho CRM Integration](#8-set-up-zoho-crm-integration)
9. [Create Cloud Tasks Queue](#9-create-cloud-tasks-queue)
10. [Deploy Cloud Functions](#10-deploy-cloud-functions)
11. [Set Up Cloud Scheduler](#11-set-up-cloud-scheduler)
12. [Configure Monitoring & Alerts](#12-configure-monitoring--alerts)
13. [Initial Tag Sync](#13-initial-tag-sync)
14. [Testing & Validation](#14-testing--validation)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Prerequisites

### Required Tools

Install the following tools on your local machine:

- **Google Cloud SDK (gcloud)**: [Installation Guide](https://cloud.google.com/sdk/docs/install)
- **Python 3.11+**: [Download](https://www.python.org/downloads/)
- **Git**: [Download](https://git-scm.com/downloads)

### Required Access

You will need:

- **GCP Project Owner or Editor** role
- **Zoho CRM Administrator** access for creating OAuth app
- **Billing Account** linked to GCP project

### Verify gcloud Installation

```bash
gcloud --version
gcloud auth login
gcloud config list
```

---

## 2. GCP Project Setup

### 2.1 Create New GCP Project

```bash
# Set project name and ID
export PROJECT_ID="ibrs-classifier"
export PROJECT_NAME="IBRS Document Classifier"
export REGION="us-central1"

# Create project
gcloud projects create $PROJECT_ID --name="$PROJECT_NAME"

# Set as active project
gcloud config set project $PROJECT_ID

# Link billing account (replace with your billing account ID)
gcloud billing projects link $PROJECT_ID --billing-account=XXXXX-XXXXX-XXXXX
```

### 2.2 Verify Project Setup

```bash
gcloud config get-value project
gcloud projects describe $PROJECT_ID
```

---

## 3. Enable Required APIs

Enable all necessary Google Cloud APIs:

```bash
# Enable Cloud Functions
gcloud services enable cloudfunctions.googleapis.com

# Enable Cloud Build (required for Functions deployment)
gcloud services enable cloudbuild.googleapis.com

# Enable Vertex AI
gcloud services enable aiplatform.googleapis.com

# Enable Cloud Storage
gcloud services enable storage.googleapis.com

# Enable Firestore
gcloud services enable firestore.googleapis.com

# Enable Cloud Tasks
gcloud services enable cloudtasks.googleapis.com

# Enable Cloud Scheduler
gcloud services enable cloudscheduler.googleapis.com

# Enable Secret Manager
gcloud services enable secretmanager.googleapis.com

# Verify enabled APIs
gcloud services list --enabled
```

**Note**: API enablement may take 2-3 minutes to propagate.

---

## 4. Configure Service Accounts

### 4.1 Create Service Account for Cloud Functions

```bash
# Create service account
gcloud iam service-accounts create ibrs-classifier \
    --display-name="IBRS Classifier Service Account" \
    --description="Service account for IBRS Document Classifier functions"

# Get service account email
export SA_EMAIL="ibrs-classifier@${PROJECT_ID}.iam.gserviceaccount.com"
```

### 4.2 Grant Required Roles

```bash
# Vertex AI User (for Gemini API)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/aiplatform.user"

# Cloud Storage Admin (for tag cache and temp storage)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.admin"

# Firestore User (for job tracking)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/datastore.user"

# Secret Manager Accessor (for API keys and Zoho credentials)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"

# Cloud Tasks Enqueuer (for async job queue)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/cloudtasks.enqueuer"

# Cloud Functions Invoker (for worker function)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/cloudfunctions.invoker"
```

### 4.3 Verify Roles

```bash
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:${SA_EMAIL}"
```

---

## 5. Create Cloud Storage Buckets

### 5.1 Create Tag Cache Bucket

```bash
# Create bucket for tag cache
gcloud storage buckets create gs://${PROJECT_ID}-ibrs-tags \
    --location=$REGION \
    --uniform-bucket-level-access

# Create folder structure (optional, happens automatically on first use)
echo '{}' | gcloud storage cp - gs://${PROJECT_ID}-ibrs-tags/tags/.placeholder
```

### 5.2 Create Temporary Documents Bucket

```bash
# Create bucket for temporary document storage
gcloud storage buckets create gs://${PROJECT_ID}-ibrs-temp \
    --location=$REGION \
    --uniform-bucket-level-access

# Set lifecycle policy to auto-delete after 24 hours
cat > /tmp/lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 1}
      }
    ]
  }
}
EOF

gcloud storage buckets update gs://${PROJECT_ID}-ibrs-temp \
    --lifecycle-file=/tmp/lifecycle.json
```

### 5.3 Verify Buckets

```bash
gcloud storage buckets list
gcloud storage ls gs://${PROJECT_ID}-ibrs-tags
gcloud storage ls gs://${PROJECT_ID}-ibrs-temp
```

---

## 6. Set Up Firestore

### 6.1 Create Firestore Database

```bash
# Create Firestore database in Native mode
gcloud firestore databases create \
    --location=$REGION \
    --type=firestore-native
```

**Note**: Choose Native mode (not Datastore mode) for full Firestore features.

### 6.2 Create Firestore Indexes

Indexes are created automatically on first use, but you can pre-create them:

```bash
# Create index configuration file
cat > /tmp/firestore-indexes.json <<EOF
{
  "indexes": [
    {
      "collectionGroup": "classification_jobs",
      "queryScope": "COLLECTION",
      "fields": [
        {
          "fieldPath": "api_key_hash",
          "order": "ASCENDING"
        },
        {
          "fieldPath": "created_at",
          "order": "DESCENDING"
        }
      ]
    }
  ]
}
EOF

# Deploy indexes
gcloud firestore indexes composite create \
    --collection-group=classification_jobs \
    --query-scope=COLLECTION \
    --field-config field-path=api_key_hash,order=ascending \
    --field-config field-path=created_at,order=descending
```

### 6.3 Configure TTL Policy

Set up automatic deletion of expired jobs:

```bash
# TTL is configured at the application level
# Jobs with ttl_expires_at field will be auto-deleted
# Enable TTL in Firestore console or wait for automatic setup
```

**Manual Setup via Console**:
1. Go to [Firestore Console](https://console.cloud.google.com/firestore)
2. Select `classification_jobs` collection
3. Click "Enable TTL" → Set field to `ttl_expires_at`

---

## 7. Configure Secret Manager

### 7.1 Create API Keys Secret

```bash
# Create initial API keys structure
cat > /tmp/api-keys.json <<EOF
{
  "keys": [
    {
      "key_id": "key_001",
      "key_value": "ibrs_live_$(openssl rand -hex 16)",
      "key_hash": "",
      "name": "Production API Key",
      "description": "Primary production API key",
      "permissions": ["classify", "classify_async", "status"],
      "rate_limit": 60,
      "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "created_by": "setup-script",
      "active": true,
      "expires_at": null
    }
  ]
}
EOF

# Generate hash for the key (you'll need to calculate this properly)
# For now, just create the secret
gcloud secrets create ibrs-classifier-api-keys \
    --replication-policy="automatic" \
    --data-file=/tmp/api-keys.json

# Grant access to service account
gcloud secrets add-iam-policy-binding ibrs-classifier-api-keys \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"
```

**Important**: After creation, retrieve the API key value for use:

```bash
gcloud secrets versions access latest --secret=ibrs-classifier-api-keys | jq -r '.keys[0].key_value'
```

Save this key securely - you'll need it for API requests.

### 7.2 Create Admin Keys Secret

```bash
# Create admin API keys
cat > /tmp/admin-keys.json <<EOF
{
  "admin_keys": [
    {
      "key_id": "admin_001",
      "key_value": "ibrs_admin_$(openssl rand -hex 16)",
      "key_hash": "",
      "name": "Admin Key - Tag Sync",
      "description": "Admin key for tag synchronization",
      "permissions": ["classify", "classify_async", "status", "admin_sync_tags"],
      "rate_limit": 10,
      "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "created_by": "setup-script",
      "active": true,
      "expires_at": null
    }
  ]
}
EOF

gcloud secrets create ibrs-classifier-admin-keys \
    --replication-policy="automatic" \
    --data-file=/tmp/admin-keys.json

gcloud secrets add-iam-policy-binding ibrs-classifier-admin-keys \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"
```

### 7.3 Retrieve API Keys for Use

```bash
# Get standard API key
export API_KEY=$(gcloud secrets versions access latest --secret=ibrs-classifier-api-keys | jq -r '.keys[0].key_value')
echo "Standard API Key: $API_KEY"

# Get admin API key
export ADMIN_API_KEY=$(gcloud secrets versions access latest --secret=ibrs-classifier-admin-keys | jq -r '.admin_keys[0].key_value')
echo "Admin API Key: $ADMIN_API_KEY"
```

---

## 8. Set Up Zoho CRM Integration

### 8.1 Create Zoho OAuth Application

1. Go to [Zoho API Console](https://api-console.zoho.com/)
2. Click "Add Client" → "Server-based Applications"
3. Fill in details:
   - **Client Name**: IBRS Document Classifier
   - **Homepage URL**: https://ibrs.com
   - **Authorized Redirect URI**: https://www.google.com (placeholder)
4. Click "Create"
5. Note down **Client ID** and **Client Secret**

### 8.2 Generate Refresh Token

```bash
# Replace with your actual client ID
export ZOHO_CLIENT_ID="1000.XXXXXXXXXXXXXXXXXXXXX"
export ZOHO_CLIENT_SECRET="your-client-secret-here"

# Generate authorization URL (open in browser)
echo "https://accounts.zoho.com/oauth/v2/auth?scope=ZohoCRM.modules.READ,ZohoCRM.settings.READ&client_id=${ZOHO_CLIENT_ID}&response_type=code&access_type=offline&redirect_uri=https://www.google.com"
```

1. Open the URL in browser
2. Authorize the application
3. You'll be redirected to google.com with a **code** parameter in URL
4. Copy the code (everything after `code=` and before `&`)

```bash
# Exchange code for refresh token
export AUTH_CODE="paste-your-code-here"

curl -X POST "https://accounts.zoho.com/oauth/v2/token" \
  -d "code=${AUTH_CODE}" \
  -d "client_id=${ZOHO_CLIENT_ID}" \
  -d "client_secret=${ZOHO_CLIENT_SECRET}" \
  -d "redirect_uri=https://www.google.com" \
  -d "grant_type=authorization_code"
```

Response will contain `refresh_token`. Save it!

### 8.3 Store Zoho Credentials in Secret Manager

```bash
# Store client secret
echo -n "$ZOHO_CLIENT_SECRET" | gcloud secrets create zoho-client-secret \
    --replication-policy="automatic" \
    --data-file=-

# Store refresh token
echo -n "your-refresh-token-here" | gcloud secrets create zoho-refresh-token \
    --replication-policy="automatic" \
    --data-file=-

# Grant access to service account
gcloud secrets add-iam-policy-binding zoho-client-secret \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding zoho-refresh-token \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"
```

### 8.4 Set Zoho Client ID in Environment

```bash
# This will be set as environment variable when deploying functions
export ZOHO_CLIENT_ID="1000.XXXXXXXXXXXXXXXXXXXXX"
```

---

## 9. Create Cloud Tasks Queue

### 9.1 Create Queue for Async Processing

```bash
# Create Cloud Tasks queue
gcloud tasks queues create ibrs-classification-queue \
    --location=$REGION \
    --max-concurrent-dispatches=10 \
    --max-dispatches-per-second=5 \
    --max-attempts=3 \
    --min-backoff=30s \
    --max-backoff=300s

# Verify queue creation
gcloud tasks queues describe ibrs-classification-queue --location=$REGION
```

---

## 10. Deploy Cloud Functions

### 10.1 Prepare Environment Variables

Create a `.env.yaml` file for common environment variables:

```bash
cat > .env.yaml <<EOF
GCP_PROJECT_ID: $PROJECT_ID
GCP_REGION: $REGION
TAG_CACHE_BUCKET: ${PROJECT_ID}-ibrs-tags
API_KEYS_SECRET_NAME: ibrs-classifier-api-keys
ADMIN_KEYS_SECRET_NAME: ibrs-classifier-admin-keys
VERTEX_AI_LOCATION: $REGION
VERTEX_AI_MODEL: gemini-1.5-pro
ZOHO_CLIENT_ID: $ZOHO_CLIENT_ID
ZOHO_CLIENT_SECRET_NAME: zoho-client-secret
ZOHO_REFRESH_TOKEN_NAME: zoho-refresh-token
ASYNC_WORKER_QUEUE: ibrs-classification-queue
ASYNC_WORKER_LOCATION: $REGION
EOF
```

### 10.2 Deploy Classify Function (Synchronous)

```bash
gcloud functions deploy classify \
    --gen2 \
    --runtime=python311 \
    --region=$REGION \
    --source=./functions/classify \
    --entry-point=app \
    --trigger-http \
    --allow-unauthenticated \
    --service-account=$SA_EMAIL \
    --timeout=60s \
    --memory=512MB \
    --max-instances=10 \
    --env-vars-file=.env.yaml
```

### 10.3 Deploy Classify Async Function

```bash
gcloud functions deploy classify-async \
    --gen2 \
    --runtime=python311 \
    --region=$REGION \
    --source=./functions/classify_async \
    --entry-point=app \
    --trigger-http \
    --allow-unauthenticated \
    --service-account=$SA_EMAIL \
    --timeout=60s \
    --memory=512MB \
    --max-instances=10 \
    --env-vars-file=.env.yaml
```

### 10.4 Deploy Classify Worker Function

```bash
gcloud functions deploy classify-worker \
    --gen2 \
    --runtime=python311 \
    --region=$REGION \
    --source=./functions/classify_worker \
    --entry-point=app \
    --trigger-http \
    --service-account=$SA_EMAIL \
    --timeout=540s \
    --memory=1GB \
    --max-instances=10 \
    --env-vars-file=.env.yaml
```

**Note**: Worker needs longer timeout (540s = 9 minutes) for processing large documents.

### 10.5 Deploy Sync Tags Function

```bash
gcloud functions deploy sync-tags \
    --gen2 \
    --runtime=python311 \
    --region=$REGION \
    --source=./functions/sync_tags \
    --entry-point=app \
    --trigger-http \
    --allow-unauthenticated \
    --service-account=$SA_EMAIL \
    --timeout=60s \
    --memory=512MB \
    --max-instances=2 \
    --env-vars-file=.env.yaml
```

### 10.6 Deploy Health Check Function

```bash
gcloud functions deploy health \
    --gen2 \
    --runtime=python311 \
    --region=$REGION \
    --source=./functions/health \
    --entry-point=app \
    --trigger-http \
    --allow-unauthenticated \
    --service-account=$SA_EMAIL \
    --timeout=10s \
    --memory=256MB \
    --max-instances=5 \
    --env-vars-file=.env.yaml
```

### 10.7 Get Function URLs

```bash
# List all deployed functions
gcloud functions list --region=$REGION

# Get specific function URLs
gcloud functions describe classify --region=$REGION --format='value(serviceConfig.uri)'
gcloud functions describe classify-async --region=$REGION --format='value(serviceConfig.uri)'
gcloud functions describe sync-tags --region=$REGION --format='value(serviceConfig.uri)'
gcloud functions describe health --region=$REGION --format='value(serviceConfig.uri)'
```

Save these URLs - you'll need them for API calls!

---

## 11. Set Up Cloud Scheduler

### 11.1 Create Scheduler Job for Tag Sync

```bash
# Get sync-tags function URL
export SYNC_TAGS_URL=$(gcloud functions describe sync-tags --region=$REGION --format='value(serviceConfig.uri)')

# Create scheduler job to run every 6 hours
gcloud scheduler jobs create http sync-tags-scheduled \
    --location=$REGION \
    --schedule="0 */6 * * *" \
    --uri="${SYNC_TAGS_URL}/admin/sync-tags" \
    --http-method=POST \
    --headers="X-API-Key=${ADMIN_API_KEY}" \
    --time-zone="America/New_York"

# Verify scheduler job
gcloud scheduler jobs describe sync-tags-scheduled --location=$REGION
```

### 11.2 Test Scheduler Job (Optional)

```bash
# Manually trigger the job
gcloud scheduler jobs run sync-tags-scheduled --location=$REGION

# Check logs
gcloud scheduler jobs logs sync-tags-scheduled --location=$REGION --limit=10
```

---

## 12. Configure Monitoring & Alerts

### 12.1 Create Log-Based Metrics

```bash
# Create metric for classification errors
gcloud logging metrics create classification_errors \
    --description="Count of classification errors" \
    --log-filter='resource.type="cloud_function"
severity="ERROR"
jsonPayload.error_code="CLASSIFICATION_FAILED"'

# Create metric for slow requests
gcloud logging metrics create slow_classifications \
    --description="Classifications taking > 10 seconds" \
    --log-filter='resource.type="cloud_function"
jsonPayload.processing_time_ms>10000'
```

### 12.2 Create Alert Policies

**High Error Rate Alert**:

Go to [Cloud Monitoring Console](https://console.cloud.google.com/monitoring) and create alert:

- **Metric**: `logging.googleapis.com/user/classification_errors`
- **Condition**: Rate > 5 errors per 5 minutes
- **Notification**: Email/Slack

**Vertex AI Failures Alert**:

- **Metric**: Custom log filter for `VERTEX_AI_ERROR`
- **Condition**: Any occurrence
- **Notification**: Immediate alert

### 12.3 Create Dashboard

```bash
# Create monitoring dashboard (simplified)
cat > /tmp/dashboard.json <<EOF
{
  "displayName": "IBRS Classifier Dashboard",
  "mosaicLayout": {
    "columns": 12
  }
}
EOF

gcloud monitoring dashboards create --config-from-file=/tmp/dashboard.json
```

**Recommended Metrics to Monitor**:
- Function invocations per endpoint
- Average processing time
- Error rate by error code
- Vertex AI API usage
- Cloud Storage read/write operations
- Firestore read/write operations

---

## 13. Initial Tag Sync

### 13.1 Perform First Tag Sync

```bash
# Get sync-tags URL
export SYNC_TAGS_URL=$(gcloud functions describe sync-tags --region=$REGION --format='value(serviceConfig.uri)')

# Trigger initial sync
curl -X POST "${SYNC_TAGS_URL}/admin/sync-tags" \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -H "Content-Type: application/json"
```

Expected response:
```json
{
  "status": "success",
  "sync_timestamp": "2025-01-23T...",
  "tags_total": 247,
  "changes": {
    "added": 247,
    "updated": 0,
    "removed": 0,
    "unchanged": 0
  }
}
```

### 13.2 Verify Tag Cache

```bash
# Check tag cache file
gcloud storage cat gs://${PROJECT_ID}-ibrs-tags/tags/current.json | jq '.tags_count'
```

---

## 14. Testing & Validation

### 14.1 Test Health Endpoint

```bash
export HEALTH_URL=$(gcloud functions describe health --region=$REGION --format='value(serviceConfig.uri)')

curl "${HEALTH_URL}/health" | jq
```

Expected: `"status": "healthy"`

### 14.2 Test Synchronous Classification

```bash
export CLASSIFY_URL=$(gcloud functions describe classify --region=$REGION --format='value(serviceConfig.uri)')

# Create test document
echo "This is a test document about cybersecurity and zero trust architecture for CISOs." > /tmp/test.txt

# Classify document
curl -X POST "${CLASSIFY_URL}/classify" \
    -H "X-API-Key: ${API_KEY}" \
    -F "file=@/tmp/test.txt" | jq
```

Expected response with classification results.

### 14.3 Test Asynchronous Classification

```bash
export CLASSIFY_ASYNC_URL=$(gcloud functions describe classify-async --region=$REGION --format='value(serviceConfig.uri)')

# Submit async job
RESPONSE=$(curl -X POST "${CLASSIFY_ASYNC_URL}/classify/async" \
    -H "X-API-Key: ${API_KEY}" \
    -F "file=@/tmp/test.txt")

echo $RESPONSE | jq

# Extract job ID
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')

# Check status (wait a few seconds first)
sleep 10
curl -X GET "${CLASSIFY_ASYNC_URL}/classify/status/${JOB_ID}" \
    -H "X-API-Key: ${API_KEY}" | jq
```

---

## 15. Troubleshooting

### Common Issues

#### Issue: "Permission denied" errors

**Solution**: Verify service account has all required roles:
```bash
gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:serviceAccount:${SA_EMAIL}"
```

#### Issue: Tag sync fails with Zoho authentication error

**Solution**: Refresh Zoho tokens:
1. Regenerate refresh token (see section 8.2)
2. Update secret:
```bash
echo -n "new-refresh-token" | gcloud secrets versions add zoho-refresh-token --data-file=-
```

#### Issue: Cloud Function deployment fails

**Solution**: Check Cloud Build logs:
```bash
gcloud builds list --limit=5
gcloud builds log <BUILD_ID>
```

Common fixes:
- Ensure `requirements.txt` is in function directory
- Check Python version compatibility
- Verify all imports are available

#### Issue: Classification returns low-quality results

**Solution**:
1. Check tag cache freshness:
```bash
curl "${HEALTH_URL}/health" | jq '.services.tag_cache'
```
2. Trigger manual tag sync
3. Review Gemini prompt in `gemini_client.py`

#### Issue: High costs

**Solution**:
1. Review Vertex AI usage:
```bash
gcloud logging read "resource.type=aiplatform.googleapis.com" --limit=100
```
2. Consider:
   - Reducing max instances on functions
   - Using Gemini Flash for simple documents
   - Implementing response caching

### Checking Logs

```bash
# View function logs
gcloud functions logs read classify --region=$REGION --limit=50

# View all errors
gcloud logging read "severity=ERROR" --limit=50 --format=json

# Follow logs in real-time
gcloud functions logs read classify --region=$REGION --limit=10 --follow
```

### Useful Commands

```bash
# List all resources
gcloud functions list --region=$REGION
gcloud storage buckets list
gcloud secrets list
gcloud tasks queues list --location=$REGION

# Check quotas
gcloud compute project-info describe --project=$PROJECT_ID --format="value(quotas)"

# Monitor costs
gcloud billing projects describe $PROJECT_ID
```

---

## Appendix A: Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| GCP_PROJECT_ID | GCP Project ID | ibrs-classifier |
| GCP_REGION | Primary region | us-central1 |
| TAG_CACHE_BUCKET | Tag cache bucket name | ibrs-classifier-ibrs-tags |
| API_KEYS_SECRET_NAME | API keys secret | ibrs-classifier-api-keys |
| ADMIN_KEYS_SECRET_NAME | Admin keys secret | ibrs-classifier-admin-keys |
| VERTEX_AI_LOCATION | Vertex AI region | us-central1 |
| VERTEX_AI_MODEL | Gemini model | gemini-1.5-pro |
| ZOHO_CLIENT_ID | Zoho OAuth client ID | 1000.XXX |
| ZOHO_CLIENT_SECRET_NAME | Zoho secret name | zoho-client-secret |
| ZOHO_REFRESH_TOKEN_NAME | Zoho token secret | zoho-refresh-token |
| ASYNC_WORKER_QUEUE | Cloud Tasks queue | ibrs-classification-queue |

---

## Appendix B: Cost Estimates

**Monthly Cost Breakdown** (for 100 documents/day):

| Service | Usage | Cost |
|---------|-------|------|
| Cloud Functions | ~3000 invocations, 1.5M GB-sec | $0.50 |
| Vertex AI (Gemini) | ~3M tokens | $10.50 |
| Cloud Storage | 1GB storage, 5K ops | $0.05 |
| Firestore | 1K reads, 1K writes, 1K deletes | $0.10 |
| Cloud Tasks | 500 tasks | $0.01 |
| Cloud Scheduler | 4 jobs | $0.40 |
| Egress | 10GB | $1.20 |
| **Total** | | **~$12.76/month** |

**Notes**:
- Costs scale linearly with document volume
- Larger documents cost more (more tokens)
- Free tier covers most dev/test usage

---

## Appendix C: Production Checklist

Before going to production:

- [ ] All functions deployed successfully
- [ ] Service account has minimal required permissions
- [ ] API keys generated and stored securely
- [ ] Zoho CRM integration tested
- [ ] Initial tag sync completed (200+ tags)
- [ ] Health check returns "healthy"
- [ ] Test classification on sample documents
- [ ] Monitoring dashboard created
- [ ] Alert policies configured
- [ ] Cloud Scheduler running (check logs)
- [ ] Firestore TTL policy enabled
- [ ] Storage lifecycle policies active
- [ ] Cost alerts configured
- [ ] Documentation updated with URLs and keys
- [ ] Runbook created for common issues
- [ ] Backup/disaster recovery plan documented

---

**End of Admin Setup Guide**

For support, contact: support@ibrs.com