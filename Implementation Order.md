# IBRS Document Auto-Classifier - Implementation Order

**Version:** 1.0
**Date:** January 2025
**Purpose:** Guide for systematic implementation of the document classification system

---

## Table of Contents

1. [Overview](#overview)
2. [Implementation Phases](#implementation-phases)
3. [Detailed Build Order](#detailed-build-order)
4. [Dependencies and Prerequisites](#dependencies-and-prerequisites)
5. [Testing Strategy](#testing-strategy)
6. [Validation Checklist](#validation-checklist)

---

## Overview

This document outlines the recommended order for implementing the IBRS Document Auto-Classifier APIs and components. The order is designed to:

- Build foundational components first
- Enable incremental testing at each stage
- Minimize rework and refactoring
- Establish data flow before complex processing
- Allow early validation of integrations

### Total Implementation Time Estimate
**12-15 development days** (assuming 1 developer)

---

## Implementation Phases

```
Phase 1: Foundation (Days 1-3)
├── Infrastructure Setup
├── Shared Utilities
└── Configuration Management

Phase 2: Data Layer (Days 4-5)
├── Tag Management
├── Zoho CRM Integration
└── Tag Cache System

Phase 3: Core Processing (Days 6-8)
├── Document Parsing
├── AI Classification
└── Synchronous API

Phase 4: Async Processing (Days 9-11)
├── Job Management
├── Queue System
└── Worker Function

Phase 5: Operations (Days 12-13)
├── Health Monitoring
├── Admin Tools
└── Automation

Phase 6: Testing & Deploy (Days 14-15)
├── Integration Testing
├── Deployment
└── Production Validation
```

---

## Detailed Build Order

### Phase 1: Foundation (Days 1-3)

#### 1.1 Infrastructure Setup
**Priority:** Critical
**Dependencies:** None
**Estimated Time:** 1 day

**Tasks:**
1. Create GCP project
2. Enable required APIs
3. Configure service accounts and IAM roles
4. Create Cloud Storage buckets
5. Set up Firestore database
6. Configure Secret Manager

**Validation:**
- All APIs enabled
- Service account has required roles
- Buckets are accessible
- Firestore database created

**Reference:** Admin Setup Guide - Sections 2-7

---

#### 1.2 Shared Configuration Module
**File:** `functions/shared/config.py`
**Priority:** Critical
**Dependencies:** Infrastructure setup
**Estimated Time:** 2 hours

**Implementation Order:**
1. Define all environment variable constants
2. Set up GCP project configuration
3. Define service endpoints
4. Configure default values
5. Add supported MIME types mapping
6. Define tag type rules

**Testing:**
```python
from shared import config
assert config.GCP_PROJECT_ID != ''
assert config.MAX_SYNC_SIZE_BYTES == 5 * 1024 * 1024
assert 'application/pdf' in config.SUPPORTED_MIME_TYPES
```

**Why First:** All other modules depend on centralized configuration.

---

#### 1.3 Authentication Module
**File:** `functions/shared/auth.py`
**Priority:** Critical
**Dependencies:** config.py, Secret Manager
**Estimated Time:** 4 hours

**Implementation Order:**
1. Create API key storage structure in Secret Manager
2. Implement `_get_secret()` helper
3. Implement `_load_api_keys()` with caching
4. Implement `_check_rate_limit()` (in-memory version)
5. Implement `_hash_api_key()` utility
6. Create `require_api_key()` decorator
7. Add `get_api_key_hash()` for job ownership

**Testing:**
```python
# Create test API key in Secret Manager
# Test decorator with valid key
# Test decorator with invalid key
# Test rate limiting
# Test admin-only endpoints
```

**Why Second:** Authentication must be ready before any API endpoints.

---

#### 1.4 Python Dependencies
**File:** `requirements.txt`
**Priority:** Critical
**Dependencies:** None
**Estimated Time:** 1 hour

**Implementation Order:**
1. Add web framework (Flask, functions-framework)
2. Add GCP client libraries
3. Add document processing libraries
4. Add Zoho integration dependencies
5. Test local installation

**Testing:**
```bash
pip install -r requirements.txt
python -c "import PyPDF2, docx, pptx, google.cloud.storage"
```

**Why Third:** Dependencies must be defined before implementing dependent code.

---

### Phase 2: Data Layer (Days 4-5)

#### 2.1 Zoho CRM Client
**File:** `functions/shared/zoho_client.py`
**Priority:** High
**Dependencies:** config.py, Secret Manager
**Estimated Time:** 6 hours

**Implementation Order:**
1. Set up Zoho OAuth application (manual step)
2. Generate and store refresh token in Secret Manager
3. Implement `_get_secret()` for credentials
4. Implement `_refresh_access_token()`
5. Implement `_get_access_token()` with auto-refresh
6. Implement `_fetch_tags_page()` with pagination
7. Implement `fetch_all_tags()` with retry logic
8. Implement `_transform_tag()` for data mapping
9. Implement `validate_tag()` for quality checks

**Testing:**
```python
client = ZohoClient()
tags = client.fetch_all_tags()
assert len(tags) > 200
assert all(tag['name'] for tag in tags)
assert all(tag['type'] in TAG_TYPES for tag in tags)
```

**Why First in Phase 2:** Tags are the source of truth; must be accessible before classification.

---

#### 2.2 Tag Cache Management
**File:** `functions/shared/tag_cache.py`
**Priority:** High
**Dependencies:** config.py, Cloud Storage, zoho_client.py
**Estimated Time:** 4 hours

**Implementation Order:**
1. Implement `TagCache` class with indexes
2. Implement `_build_indexes()` for fast lookups
3. Implement `get_by_name()`, `get_by_alias()`, `get_by_type()`
4. Implement `get_formatted_for_prompt()` for AI
5. Implement `load_tag_cache()` with caching logic
6. Implement `save_tag_cache()` with backup
7. Implement `get_cache_age_hours()` utility

**Testing:**
```python
# Save test tag data to Cloud Storage
cache = load_tag_cache()
assert cache.get_tags_count() > 0
tag = cache.get_by_name('Cybersecurity')
assert tag is not None
assert cache.get_by_alias('InfoSec') == tag
```

**Why Second in Phase 2:** Cache system needed before any classification work.

---

#### 2.3 Tag Sync API
**File:** `functions/sync_tags/main.py`
**Priority:** High
**Dependencies:** auth.py, zoho_client.py, tag_cache.py
**Estimated Time:** 4 hours

**Implementation Order:**
1. Create Flask app structure
2. Implement `/admin/sync-tags` endpoint
3. Load current cache for comparison
4. Fetch tags from Zoho
5. Detect changes (added, updated, removed)
6. Save updated cache to Cloud Storage
7. Return detailed change summary
8. Add error handling for Zoho failures

**Testing:**
```bash
# Deploy function
gcloud functions deploy sync-tags ...

# Test sync
curl -X POST "https://.../admin/sync-tags" \
  -H "X-API-Key: admin-key"

# Verify tag cache updated in Cloud Storage
```

**Why Third in Phase 2:** Establishes data pipeline before building classification.

---

#### 2.4 Initial Tag Sync
**Priority:** Critical
**Dependencies:** Tag Sync API deployed
**Estimated Time:** 1 hour

**Implementation Order:**
1. Deploy sync-tags function to GCP
2. Manually trigger initial sync
3. Verify tag cache file in Cloud Storage
4. Inspect tag data structure
5. Validate tag counts and types

**Testing:**
```bash
# Trigger sync
curl -X POST ".../admin/sync-tags" -H "X-API-Key: ..."

# Verify cache
gcloud storage cat gs://bucket/tags/current.json | jq '.tags_count'
# Should return 200+
```

**Why Fourth in Phase 2:** Must have tag data before classification can work.

---

### Phase 3: Core Processing (Days 6-8)

#### 3.1 Document Parser
**File:** `functions/shared/document_parser.py`
**Priority:** High
**Dependencies:** config.py, document processing libraries
**Estimated Time:** 6 hours

**Implementation Order:**
1. Implement `detect_format()` based on MIME type
2. Implement `_extract_from_pdf()` with PyPDF2 and pdfplumber fallback
3. Implement `_extract_from_docx()` with paragraph and table support
4. Implement `_extract_from_pptx()` with slide and notes extraction
5. Implement `_extract_from_text()` with encoding detection
6. Implement `_extract_from_image()` with OCR
7. Implement `extract_text()` dispatcher
8. Implement `validate_extracted_text()` with quality checks

**Testing:**
```python
parser = DocumentParser()

# Test PDF
with open('test.pdf', 'rb') as f:
    text = parser.extract_text(f.read(), 'application/pdf')
assert len(text) > 100

# Test DOCX
# Test PPTX
# Test image with OCR
# Test validation
```

**Why First in Phase 3:** Text extraction is prerequisite for classification.

---

#### 3.2 Gemini AI Client
**File:** `functions/shared/gemini_client.py`
**Priority:** High
**Dependencies:** config.py, Vertex AI, tag_cache.py
**Estimated Time:** 8 hours

**Implementation Order:**
1. Initialize Vertex AI client
2. Configure Gemini model settings
3. Implement `_build_classification_prompt()` with:
   - System instructions
   - Classification rules
   - Tag list formatting
   - Document text inclusion
   - Output format specification
4. Implement `classify_document()` with retry logic
5. Implement `_validate_and_enrich_classification()` to:
   - Match tags by name and alias
   - Enforce cardinality rules (1 Horizon, 1 Practice)
   - Add default tags if missing
   - Enrich with full tag details
6. Implement `validate_classification_rules()`

**Testing:**
```python
classifier = GeminiClassifier()
tag_cache = load_tag_cache()

test_text = """
This document discusses zero trust security architecture
for Chief Information Security Officers implementing
cybersecurity solutions.
"""

result = classifier.classify_document(test_text, tag_cache)

assert result['horizon']['name'] in ['Solve', 'Plan', 'Explore']
assert result['practice'] is not None
assert len(result.get('topics', [])) > 0
```

**Why Second in Phase 3:** Classification engine is core functionality.

---

#### 3.3 Synchronous Classification API
**File:** `functions/classify/main.py`
**Priority:** Critical
**Dependencies:** All shared modules
**Estimated Time:** 6 hours

**Implementation Order:**
1. Create Flask app structure
2. Implement `_extract_document_from_request()`:
   - Handle multipart/form-data uploads
   - Handle JSON with base64 content
3. Implement `/classify` endpoint:
   - Apply `@require_api_key` decorator
   - Validate document size (< 5MB)
   - Validate MIME type
   - Extract text using DocumentParser
   - Validate extracted text quality
   - Load tag cache
   - Classify using GeminiClassifier
   - Validate classification rules
   - Return formatted response
4. Add comprehensive error handling
5. Include processing time metrics

**Testing:**
```bash
# Deploy function
gcloud functions deploy classify ...

# Test with PDF
curl -X POST "https://.../classify" \
  -H "X-API-Key: key" \
  -F "file=@test.pdf"

# Verify response structure
# Check classification quality
# Test error cases (too large, invalid format, etc.)
```

**Why Third in Phase 3:** First complete user-facing API endpoint.

---

### Phase 4: Async Processing (Days 9-11)

#### 4.1 Cloud Tasks Queue Setup
**Priority:** High
**Dependencies:** Infrastructure
**Estimated Time:** 1 hour

**Implementation Order:**
1. Create Cloud Tasks queue via gcloud
2. Configure retry settings
3. Configure rate limits
4. Verify queue created

**Testing:**
```bash
gcloud tasks queues create ibrs-classification-queue \
  --location=us-central1 \
  --max-concurrent-dispatches=10

gcloud tasks queues describe ibrs-classification-queue
```

**Why First in Phase 4:** Infrastructure needed before async APIs.

---

#### 4.2 Async Job Submission API
**File:** `functions/classify_async/main.py`
**Priority:** High
**Dependencies:** Firestore, Cloud Storage, Cloud Tasks
**Estimated Time:** 6 hours

**Implementation Order:**
1. Create Flask app structure
2. Implement `/classify/async` endpoint:
   - Apply `@require_api_key` decorator
   - Validate size (5MB - 50MB)
   - Generate UUID job_id
   - Upload document to Cloud Storage temp bucket
   - Create Firestore job document
   - Enqueue Cloud Task for worker
   - Return job_id and status_url immediately
3. Implement `/classify/status/{job_id}` endpoint:
   - Validate API key ownership
   - Query Firestore for job status
   - Return appropriate response based on status
   - Include progress for processing jobs
4. Implement `_create_worker_task()` helper

**Testing:**
```bash
# Deploy function
gcloud functions deploy classify-async ...

# Submit large document
RESPONSE=$(curl -X POST "https://.../classify/async" \
  -H "X-API-Key: key" \
  -F "file=@large.pdf")

JOB_ID=$(echo $RESPONSE | jq -r '.job_id')

# Check status
curl "https://.../classify/status/$JOB_ID" \
  -H "X-API-Key: key"
```

**Why Second in Phase 4:** API for job management before worker implementation.

---

#### 4.3 Async Worker Function
**File:** `functions/classify_worker/main.py`
**Priority:** High
**Dependencies:** All shared modules, Firestore, Cloud Storage
**Estimated Time:** 6 hours

**Implementation Order:**
1. Create Flask app structure (no auth - internal only)
2. Implement `/classify-worker` endpoint:
   - Extract job_id from request
   - Load job from Firestore
   - Update status to 'processing'
   - Download document from Cloud Storage
   - Update progress: text extraction
   - Extract text using DocumentParser
   - Update progress: classification
   - Load tag cache
   - Classify using GeminiClassifier
   - Validate classification
   - Update progress: completed
   - Store results in Firestore
   - Mark job as completed
   - Delete temporary document
3. Implement `_fail_job()` helper for error handling
4. Add comprehensive error handling for each stage

**Testing:**
```bash
# Deploy function
gcloud functions deploy classify-worker ...

# Submit async job (triggers worker)
curl -X POST "https://.../classify/async" \
  -H "X-API-Key: key" \
  -F "file=@large.pdf"

# Wait 30 seconds

# Check status - should be completed
curl "https://.../classify/status/$JOB_ID" \
  -H "X-API-Key: key"

# Verify Firestore job document
# Verify temp file deleted from Storage
```

**Why Third in Phase 4:** Completes async processing pipeline.

---

### Phase 5: Operations (Days 12-13)

#### 5.1 Health Check API
**File:** `functions/health/main.py`
**Priority:** Medium
**Dependencies:** All services
**Estimated Time:** 4 hours

**Implementation Order:**
1. Create Flask app structure (no auth required)
2. Implement `/health` endpoint:
   - Check Vertex AI connectivity
   - Check tag cache status and age
   - Check Firestore connectivity
   - Check Cloud Storage access
   - Count active async jobs
   - Return comprehensive status
3. Set overall status (healthy/degraded/unhealthy)
4. Add uptime tracking
5. Implement caching (30 seconds) to avoid overload

**Testing:**
```bash
# Deploy function
gcloud functions deploy health ...

# Test health check
curl "https://.../health"

# Verify all services show "operational"
# Check tag cache age is reasonable
```

**Why First in Phase 5:** Monitoring before automation.

---

#### 5.2 Cloud Scheduler Setup
**Priority:** Medium
**Dependencies:** sync-tags function deployed
**Estimated Time:** 1 hour

**Implementation Order:**
1. Get sync-tags function URL
2. Create Cloud Scheduler job
3. Configure schedule (every 6 hours)
4. Add admin API key header
5. Set timezone
6. Test manual trigger

**Testing:**
```bash
# Create scheduler job
gcloud scheduler jobs create http sync-tags-scheduled \
  --location=us-central1 \
  --schedule="0 */6 * * *" \
  --uri="https://.../admin/sync-tags" \
  --http-method=POST \
  --headers="X-API-Key=admin-key"

# Manually trigger
gcloud scheduler jobs run sync-tags-scheduled

# Verify tag cache updated
```

**Why Second in Phase 5:** Automates tag synchronization.

---

#### 5.3 Monitoring & Alerts
**Priority:** Medium
**Dependencies:** All functions deployed
**Estimated Time:** 4 hours

**Implementation Order:**
1. Create log-based metrics:
   - Classification errors
   - Slow requests
   - Vertex AI failures
2. Create alert policies:
   - High error rate (> 5%)
   - Stale tag cache (> 24 hours)
   - Vertex AI quota warnings
3. Create monitoring dashboard:
   - Request counts by endpoint
   - Processing time distribution
   - Error rate trends
   - Active async jobs
   - Vertex AI token usage
4. Set up notification channels (email/Slack)

**Testing:**
```bash
# Create test error to trigger alert
# Verify alerts received
# Check dashboard displays metrics
```

**Why Third in Phase 5:** Operational visibility after all APIs are working.

---

### Phase 6: Testing & Deployment (Days 14-15)

#### 6.1 Integration Testing
**Priority:** Critical
**Dependencies:** All components deployed
**Estimated Time:** 6 hours

**Test Scenarios:**

1. **End-to-End Sync Classification:**
```bash
# Upload small PDF
# Verify classification returned
# Check all mandatory tags present
# Verify response time < 10s
```

2. **End-to-End Async Classification:**
```bash
# Upload large PDF
# Verify job created
# Poll status until complete
# Verify classification quality
# Check processing time reasonable
```

3. **Tag Synchronization:**
```bash
# Trigger manual sync
# Verify tag count
# Check cache updated
# Validate tag structure
```

4. **Error Handling:**
```bash
# Invalid API key → 401
# Unsupported format → 400
# Document too large → 413
# Corrupted file → 500
```

5. **Rate Limiting:**
```bash
# Send 61 requests in 1 minute
# Verify 429 error on 61st request
```

6. **Load Testing:**
```bash
# Send 10 concurrent requests
# Verify all complete successfully
# Check processing times acceptable
```

**Why First in Phase 6:** Validate all integrations work together.

---

#### 6.2 Documentation Updates
**Priority:** Medium
**Dependencies:** Testing complete
**Estimated Time:** 2 hours

**Tasks:**
1. Update README with actual function URLs
2. Add example API calls with real responses
3. Document any configuration changes
4. Update troubleshooting guide with findings
5. Create API key management procedures

**Why Second in Phase 6:** Documentation reflects actual deployment.

---

#### 6.3 Production Validation
**Priority:** Critical
**Dependencies:** All testing passed
**Estimated Time:** 2 hours

**Validation Checklist:**
- [ ] Health check returns "healthy"
- [ ] Tag cache has 200+ tags
- [ ] Tag sync scheduler running (check logs)
- [ ] Synchronous classification working
- [ ] Asynchronous classification working
- [ ] All error codes tested
- [ ] Rate limiting enforced
- [ ] Monitoring dashboard showing data
- [ ] Alerts configured and tested
- [ ] Cost alerts set up
- [ ] API keys documented securely
- [ ] Backup procedures documented

**Why Third in Phase 6:** Final gate before production use.

---

## Dependencies and Prerequisites

### Before Starting Implementation

#### GCP Resources Required:
1. ✅ GCP Project created
2. ✅ Billing account linked
3. ✅ All APIs enabled
4. ✅ Service account configured
5. ✅ Cloud Storage buckets created
6. ✅ Firestore database created
7. ✅ Secret Manager secrets created
8. ✅ Cloud Tasks queue created

#### External Integrations Required:
1. ✅ Zoho CRM OAuth app created
2. ✅ Zoho refresh token obtained
3. ✅ API keys generated
4. ✅ IBRS_Tags module accessible in Zoho

#### Development Environment:
1. ✅ Python 3.11+ installed
2. ✅ gcloud CLI installed and authenticated
3. ✅ Git repository initialized
4. ✅ Code editor configured
5. ✅ Virtual environment created

### Component Dependency Graph

```
Infrastructure Setup (Day 1)
└── config.py (Day 1)
    ├── auth.py (Day 1)
    │   └── All API endpoints depend on this
    ├── zoho_client.py (Day 4)
    │   └── tag_cache.py (Day 4)
    │       └── sync_tags API (Day 5)
    │           └── Initial Tag Sync (Day 5)
    │               ├── document_parser.py (Day 6)
    │               └── gemini_client.py (Day 7)
    │                   └── classify API (Day 8)
    │                       └── classify_async API (Day 9)
    │                           └── classify_worker (Day 10)
    │                               └── health API (Day 12)
```

---

## Testing Strategy

### Unit Testing
**When:** After each component is built
**Scope:** Individual functions and classes
**Location:** `tests/` directory

Example:
```python
# tests/test_tag_cache.py
def test_tag_cache_loading():
    cache = load_tag_cache()
    assert cache.get_tags_count() > 0

def test_tag_lookup_by_name():
    cache = load_tag_cache()
    tag = cache.get_by_name('Cybersecurity')
    assert tag is not None
    assert tag['type'] == 'Practice'
```

### Integration Testing
**When:** After each phase is complete
**Scope:** API endpoints and service integrations
**Method:** cURL commands and API calls

Example:
```bash
# Test sync classification end-to-end
curl -X POST "$CLASSIFY_URL/classify" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@test.pdf" | jq
```

### System Testing
**When:** Phase 6 - Before production
**Scope:** Complete workflows and error scenarios
**Method:** Automated test scripts

---

## Validation Checklist

### After Each Component

- [ ] Code implements specification exactly
- [ ] All error cases handled
- [ ] Logging added for debugging
- [ ] Unit tests written and passing
- [ ] Manual testing completed
- [ ] Code committed to Git
- [ ] Documentation updated

### After Each Phase

- [ ] All components in phase completed
- [ ] Integration tests passing
- [ ] Phase dependencies met
- [ ] No breaking changes to previous phases
- [ ] Performance acceptable
- [ ] Ready for next phase

### Before Production

- [ ] All phases completed
- [ ] All tests passing (unit + integration + system)
- [ ] Documentation complete and accurate
- [ ] Monitoring and alerts configured
- [ ] Backup and recovery procedures documented
- [ ] Security review completed
- [ ] Cost projections validated
- [ ] Stakeholder sign-off obtained

---

## Critical Success Factors

### Must Have From Day 1:
1. **Stable Configuration** - No hard-coded values
2. **Proper Error Handling** - Never crash, always return JSON
3. **Comprehensive Logging** - Debug issues quickly
4. **Security First** - API keys, IAM roles, no secrets in code

### Don't Start Next Component Until:
1. Previous component fully tested
2. Integration points verified
3. Dependencies documented
4. No known critical bugs

### Red Flags to Stop and Reassess:
- Classification accuracy < 70%
- Response times consistently > 15 seconds
- Error rate > 5%
- Cost exceeding projections by 2x
- Unable to sync tags from Zoho
- Vertex AI quota issues

---

## Appendix: Quick Reference Commands

### Deploy All Functions (After Implementation)

```bash
#!/bin/bash
# Deploy script - run after all components built

export PROJECT_ID="ibrs-classifier"
export REGION="us-central1"

# Deploy in order
gcloud functions deploy sync-tags --gen2 --runtime=python311 ...
gcloud functions deploy classify --gen2 --runtime=python311 ...
gcloud functions deploy classify-async --gen2 --runtime=python311 ...
gcloud functions deploy classify-worker --gen2 --runtime=python311 ...
gcloud functions deploy health --gen2 --runtime=python311 ...

# Set up scheduler
gcloud scheduler jobs create http sync-tags-scheduled ...

echo "All functions deployed!"
```

### Test All Endpoints

```bash
#!/bin/bash
# Test script - run after deployment

# Get URLs
export CLASSIFY_URL=$(gcloud functions describe classify --format='value(serviceConfig.uri)')
export HEALTH_URL=$(gcloud functions describe health --format='value(serviceConfig.uri)')

# Test health
curl "$HEALTH_URL/health"

# Test classification
curl -X POST "$CLASSIFY_URL/classify" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@test.pdf"

echo "All tests complete!"
```

---

**End of Implementation Order Document**

This document should be used as the authoritative guide for building the IBRS Document Auto-Classifier system in the correct sequence.

