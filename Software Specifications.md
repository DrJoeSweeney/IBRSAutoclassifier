# IBRS Document Auto-Classifier - Software Specifications

**Version:** 1.0
**Date:** January 2025
**Author:** IBRS Development Team

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Functional Requirements](#2-functional-requirements)
3. [API Specifications](#3-api-specifications)
4. [Data Models](#4-data-models)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Integration Requirements](#6-integration-requirements)
7. [Error Handling](#7-error-handling)
8. [Constraints & Assumptions](#8-constraints--assumptions)

---

## 1. System Overview

### 1.1 Purpose

The IBRS Document Auto-Classifier is a stateless, serverless API system that automatically classifies documents against a taxonomy of 240+ tags using artificial intelligence. The system is designed to analyze various document formats (text, Word, PowerPoint, PDF, images) and assign relevant tags based on content, helping IBRS categorize and organize their knowledge base and research materials.

### 1.2 Architecture

The system is deployed on Google Cloud Platform (GCP) using the following components:

- **Cloud Functions (2nd Gen)**: Stateless API endpoints and processing functions
- **Vertex AI**: Google Gemini 1.5 Pro for AI-powered classification
- **Cloud Storage**: Tag cache storage
- **Firestore**: Async job tracking
- **Cloud Tasks**: Asynchronous job queue
- **Cloud Scheduler**: Periodic tag synchronization
- **Secret Manager**: API key storage
- **Zoho CRM Integration**: Source of truth for tag taxonomy

### 1.3 Key Features

- Multi-format document support (PDF, Word, PowerPoint, images, text)
- AI-powered classification using Google Gemini
- Flexible sync/async processing based on document size
- Periodic tag synchronization from Zoho CRM
- Stateless design for scalability
- API key authentication
- Structured JSON responses
- Rule-based validation (mandatory Horizon and Practice tags)

---

## 2. Functional Requirements

### 2.1 Document Processing

#### 2.1.1 Supported Formats

| Format | Extension | Processing Method | Notes |
|--------|-----------|-------------------|-------|
| Plain Text | .txt | Direct read | UTF-8 encoding |
| PDF | .pdf | PyPDF2/pdfplumber | Text extraction, tables supported |
| Word | .docx | python-docx | Modern Office format only |
| PowerPoint | .pptx | python-pptx | Extracts text from slides and notes |
| JPEG Image | .jpg, .jpeg | Tesseract OCR | Requires clear, high-resolution text |
| PNG Image | .png | Tesseract OCR | Best for screenshots |
| GIF Image | .gif | Tesseract OCR | First frame only |

#### 2.1.2 Input Methods

1. **Binary Upload**: Multipart form data with file attachment
2. **Base64 Encoding**: JSON payload with base64-encoded content

#### 2.1.3 Size-Based Routing

- **Documents < 5MB**: Synchronous processing via `/classify`
- **Documents ≥ 5MB**: Asynchronous processing via `/classify/async`
- **Maximum Size**: 50MB hard limit

### 2.2 Tag Management

#### 2.2.1 Tag Structure

Each tag in the IBRS_Tags module contains:

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| id | String | Unique identifier from Zoho | Yes |
| name | String | Primary tag name | Yes |
| aliases | Array[String] | Up to 4 alternative names | No |
| short_form | String | Abbreviated version (2-10 chars) | Yes |
| public_description | String | User-facing description | Yes |
| internal_commentary | String | Internal usage notes | No |
| type | Enum | Tag category (see below) | Yes |

#### 2.2.2 Tag Types

| Type | Description | Cardinality | Values |
|------|-------------|-------------|--------|
| Horizon | Strategic timeframe | Exactly 1 | Solve, Plan, Explore |
| Practice | Business practice area | Exactly 1 | Various (e.g., Cybersecurity, Cloud Computing) |
| Stream | Content stream/category | 0 to Many | Various (e.g., Risk Management, Architecture) |
| Role | Target audience role | 0 to Many | Various (e.g., CIO, CISO, Developer) |
| Vendor | Company/vendor mentioned | 0 to Many | Various (e.g., Microsoft, AWS, Google) |
| Product | Specific product/service | 0 to Many | Various (e.g., Azure, AWS Lambda, Kubernetes) |
| Topic | Subject matter | 0 to Many | Various (e.g., Zero Trust, DevOps, AI/ML) |

#### 2.2.3 Tag Synchronization

- **Frequency**: Every 6 hours via Cloud Scheduler
- **Source**: Zoho CRM IBRS_Tags module via API
- **Cache Location**: Cloud Storage bucket (JSON file)
- **Manual Trigger**: Available via `/admin/sync-tags` endpoint
- **Change Detection**: Track added, updated, and removed tags
- **Failure Handling**: Retry up to 3 times, alert on persistent failure

### 2.3 Classification Engine

#### 2.3.1 AI Model

- **Provider**: Google Vertex AI
- **Model**: gemini-1.5-pro
- **Context Window**: ~1M tokens (supports large documents)
- **Output Format**: Structured JSON with tag assignments and confidence scores

#### 2.3.2 Classification Process

1. **Text Extraction**: Extract text from uploaded document
2. **Prompt Construction**: Build structured prompt with:
   - Document text
   - Complete tag list with descriptions
   - Classification rules
   - Output format specification
3. **AI Analysis**: Send to Gemini for classification
4. **Response Parsing**: Extract structured JSON response
5. **Validation**: Ensure exactly 1 Horizon and 1 Practice tag
6. **Confidence Scoring**: Include AI confidence for each tag
7. **Result Formatting**: Return standardized JSON response

#### 2.3.3 Validation Rules

The system MUST enforce:
- Exactly 1 Horizon tag (Solve, Plan, or Explore)
- Exactly 1 Practice tag
- 0 or more tags of all other types
- All returned tags must exist in the tag cache
- Confidence scores must be between 0.0 and 1.0

---

## 3. API Specifications

### 3.1 Base Configuration

- **Protocol**: HTTPS only (TLS 1.2+)
- **Base URL**: `https://[region]-[project-id].cloudfunctions.net`
- **Content Type**: `application/json` (except multipart uploads)
- **Authentication**: API Key via header
- **Rate Limiting**: 60 requests per minute per API key

---

### 3.2 API Endpoint: Classify Document (Synchronous)

#### Name
`POST /classify`

#### Purpose
Synchronously classify documents under 5MB and return immediate results with assigned tags.

#### Behavior
1. Validates API key
2. Accepts document upload (multipart or base64)
3. Validates document size (< 5MB)
4. Extracts text from document
5. Loads current tag cache
6. Sends text and tags to Gemini for classification
7. Validates classification results against rules
8. Returns structured JSON response with tags and confidence scores

#### Specification

**HTTP Method**: POST

**Endpoint**: `/classify`

**Request Headers**:
```
X-API-Key: <api_key>
Content-Type: multipart/form-data OR application/json
```

**Request Body (Multipart)**:
```
POST /classify HTTP/1.1
Host: us-central1-ibrs-classifier.cloudfunctions.net
X-API-Key: abc123xyz789
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="report.pdf"
Content-Type: application/pdf

[binary file data]
------WebKitFormBoundary--
```

**Request Body (JSON)**:
```json
{
  "content": "base64-encoded-document-content",
  "filename": "report.pdf",
  "mime_type": "application/pdf"
}
```

**Response (200 OK)**:
```json
{
  "status": "success",
  "document": {
    "filename": "report.pdf",
    "size_bytes": 245678,
    "mime_type": "application/pdf",
    "text_length": 15234
  },
  "classification": {
    "horizon": {
      "name": "Solve",
      "short_form": "SLV",
      "confidence": 0.92,
      "matched_via": "primary"
    },
    "practice": {
      "name": "Cybersecurity",
      "short_form": "CYB",
      "confidence": 0.88,
      "matched_via": "primary"
    },
    "streams": [
      {
        "name": "Risk Management",
        "short_form": "RISK",
        "confidence": 0.85,
        "matched_via": "alias"
      }
    ],
    "roles": [
      {
        "name": "CISO",
        "short_form": "CISO",
        "confidence": 0.81,
        "matched_via": "primary"
      }
    ],
    "vendors": [
      {
        "name": "Microsoft",
        "short_form": "MSFT",
        "confidence": 0.79,
        "matched_via": "primary"
      },
      {
        "name": "Palo Alto Networks",
        "short_form": "PANW",
        "confidence": 0.72,
        "matched_via": "primary"
      }
    ],
    "products": [
      {
        "name": "Microsoft Defender",
        "short_form": "MSDEF",
        "confidence": 0.81,
        "matched_via": "alias"
      }
    ],
    "topics": [
      {
        "name": "Zero Trust",
        "short_form": "ZT",
        "confidence": 0.76,
        "matched_via": "primary"
      },
      {
        "name": "Endpoint Security",
        "short_form": "EPSEC",
        "confidence": 0.73,
        "matched_via": "primary"
      }
    ]
  },
  "processing_time_ms": 3421,
  "model_used": "gemini-1.5-pro"
}
```

**Error Response (400 Bad Request)**:
```json
{
  "status": "error",
  "error_code": "DOCUMENT_TOO_LARGE",
  "message": "Document exceeds 5MB limit for synchronous processing. Use /classify/async endpoint.",
  "details": {
    "max_size_bytes": 5242880,
    "received_size_bytes": 6291456,
    "recommendation": "Use POST /classify/async for this document"
  },
  "timestamp": "2025-01-23T10:30:00Z"
}
```

**Error Response (401 Unauthorized)**:
```json
{
  "status": "error",
  "error_code": "INVALID_API_KEY",
  "message": "API key is missing or invalid",
  "timestamp": "2025-01-23T10:30:00Z"
}
```

**Error Response (500 Internal Server Error)**:
```json
{
  "status": "error",
  "error_code": "CLASSIFICATION_FAILED",
  "message": "Failed to classify document after 3 attempts",
  "details": {
    "last_error": "Vertex AI rate limit exceeded",
    "retry_count": 3
  },
  "timestamp": "2025-01-23T10:30:00Z"
}
```

#### Implementation Notes for Developers

1. **Document Size Check**: Immediately check `Content-Length` header or file size before processing
2. **Text Extraction**: Use appropriate library based on MIME type:
   - PDF: Try PyPDF2 first, fallback to pdfplumber for complex PDFs
   - DOCX: Use python-docx, extract from paragraphs and tables
   - PPTX: Use python-pptx, extract from all slides and notes
   - Images: Use pytesseract with preprocessing (grayscale, contrast enhancement)
3. **Tag Cache Loading**: Load from Cloud Storage at function startup (cache in global scope for warm instances)
4. **Prompt Engineering**:
   - Include system instructions about tag types and rules
   - Provide all tag names, aliases, and descriptions
   - Request JSON output with specific schema
   - Include few-shot examples for better accuracy
5. **Timeout Handling**: Set 55-second timeout to allow response before Cloud Function timeout
6. **Validation**: After receiving Gemini response:
   - Parse JSON safely
   - Check for exactly 1 Horizon and 1 Practice
   - Verify all tags exist in cache
   - Add missing mandatory tags if needed (use highest confidence from Gemini)
7. **Logging**: Log document metadata, processing time, and classification results for analytics
8. **Error Recovery**: Retry Vertex AI calls up to 3 times with exponential backoff

#### Input Requirements

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| file (multipart) | Binary | Yes (if not using JSON) | Max 5MB, supported MIME type |
| content (JSON) | String (base64) | Yes (if not using multipart) | Valid base64, decodes to max 5MB |
| filename (JSON) | String | Yes (if using JSON) | Valid filename with extension |
| mime_type (JSON) | String | Yes (if using JSON) | One of: application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, application/vnd.openxmlformats-officedocument.presentationml.presentation, text/plain, image/jpeg, image/png, image/gif |

#### Output Specification

| Field | Type | Description |
|-------|------|-------------|
| status | String | "success" or "error" |
| document | Object | Metadata about processed document |
| document.filename | String | Original filename |
| document.size_bytes | Integer | File size in bytes |
| document.mime_type | String | MIME type |
| document.text_length | Integer | Characters extracted |
| classification | Object | Classification results |
| classification.horizon | Object | Exactly 1 Horizon tag |
| classification.practice | Object | Exactly 1 Practice tag |
| classification.streams | Array[Object] | 0+ Stream tags |
| classification.roles | Array[Object] | 0+ Role tags |
| classification.vendors | Array[Object] | 0+ Vendor tags |
| classification.products | Array[Object] | 0+ Product tags |
| classification.topics | Array[Object] | 0+ Topic tags |
| [tag].name | String | Tag name |
| [tag].short_form | String | Tag abbreviation |
| [tag].confidence | Float | Confidence score (0.0-1.0) |
| [tag].matched_via | String | "primary" or "alias" |
| processing_time_ms | Integer | Total processing time |
| model_used | String | AI model identifier |

#### Authentication Requirements

- **Required**: Yes
- **Method**: API Key
- **Header**: `X-API-Key`
- **Validation**: Key must exist in Secret Manager and be active
- **Rate Limit**: 60 requests/minute per key
- **Scope**: Standard user access

---

### 3.3 API Endpoint: Classify Document (Asynchronous)

#### Name
`POST /classify/async`

#### Purpose
Accept large documents (5MB - 50MB) for asynchronous classification, returning a job ID for later status polling.

#### Behavior
1. Validates API key
2. Accepts document upload (multipart or base64)
3. Validates document size (5MB - 50MB)
4. Creates job record in Firestore
5. Enqueues processing task in Cloud Tasks
6. Returns job ID and status URL immediately
7. Background worker processes document and updates job status

#### Specification

**HTTP Method**: POST

**Endpoint**: `/classify/async`

**Request Headers**:
```
X-API-Key: <api_key>
Content-Type: multipart/form-data OR application/json
```

**Request Body**: Same format as `/classify` endpoint

**Response (202 Accepted)**:
```json
{
  "status": "accepted",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status_url": "/classify/status/550e8400-e29b-41d4-a716-446655440000",
  "estimated_completion_seconds": 45,
  "created_at": "2025-01-23T10:30:00Z"
}
```

**Error Response (413 Payload Too Large)**:
```json
{
  "status": "error",
  "error_code": "DOCUMENT_TOO_LARGE",
  "message": "Document exceeds maximum size of 50MB",
  "details": {
    "max_size_bytes": 52428800,
    "received_size_bytes": 65536000
  },
  "timestamp": "2025-01-23T10:30:00Z"
}
```

#### Implementation Notes for Developers

1. **Job ID Generation**: Use UUID v4 for unique job identifiers
2. **Document Storage**: Store uploaded document temporarily in Cloud Storage (with 24hr TTL) for worker processing
3. **Firestore Document**:
   ```json
   {
     "job_id": "uuid",
     "status": "pending",
     "created_at": timestamp,
     "updated_at": timestamp,
     "document_ref": "gs://bucket/temp/uuid.pdf",
     "api_key_hash": "sha256_hash",
     "result": null,
     "ttl_expires_at": timestamp + 24hrs
   }
   ```
4. **Cloud Tasks**: Create task with:
   - Target: async worker function URL
   - Payload: job_id
   - Delay: 0 seconds (immediate)
   - Max retries: 3
5. **Estimation**: Calculate based on document size (rough: 1MB = 5 seconds)
6. **Response Time**: Entire endpoint should complete in < 1 second

#### Input Requirements
Same as `/classify` endpoint, but size validation is 5MB - 50MB range.

#### Output Specification

| Field | Type | Description |
|-------|------|-------------|
| status | String | Always "accepted" for successful submission |
| job_id | String | UUID v4 job identifier |
| status_url | String | Relative URL for status polling |
| estimated_completion_seconds | Integer | Estimated processing time |
| created_at | String | ISO 8601 timestamp |

#### Authentication Requirements
Same as `/classify` endpoint.

---

### 3.4 API Endpoint: Check Classification Status

#### Name
`GET /classify/status/{job_id}`

#### Purpose
Retrieve the status and results of an asynchronous classification job.

#### Behavior
1. Validates API key
2. Extracts job_id from URL path
3. Queries Firestore for job record
4. Returns current status and results if completed
5. Returns 404 if job not found or expired

#### Specification

**HTTP Method**: GET

**Endpoint**: `/classify/status/{job_id}`

**Request Headers**:
```
X-API-Key: <api_key>
```

**Response (200 OK) - Pending**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2025-01-23T10:30:00Z",
  "updated_at": "2025-01-23T10:30:00Z",
  "message": "Job is queued for processing"
}
```

**Response (200 OK) - Processing**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "created_at": "2025-01-23T10:30:00Z",
  "updated_at": "2025-01-23T10:30:15Z",
  "progress": {
    "stage": "text_extraction",
    "percent_complete": 30
  }
}
```

**Response (200 OK) - Completed**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2025-01-23T10:30:00Z",
  "completed_at": "2025-01-23T10:30:45Z",
  "processing_time_ms": 45123,
  "result": {
    "status": "success",
    "document": {
      "filename": "large_report.pdf",
      "size_bytes": 8388608,
      "mime_type": "application/pdf",
      "text_length": 45234
    },
    "classification": {
      /* Same structure as /classify response */
    }
  }
}
```

**Response (200 OK) - Failed**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "created_at": "2025-01-23T10:30:00Z",
  "failed_at": "2025-01-23T10:30:20Z",
  "error": {
    "error_code": "EXTRACTION_FAILED",
    "message": "Unable to extract text from corrupted PDF",
    "details": {
      "error_type": "PDFSyntaxError",
      "error_message": "Invalid PDF structure"
    }
  }
}
```

**Response (404 Not Found)**:
```json
{
  "status": "error",
  "error_code": "JOB_NOT_FOUND",
  "message": "Job not found or has expired",
  "details": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "note": "Jobs expire 24 hours after creation"
  },
  "timestamp": "2025-01-23T10:30:00Z"
}
```

#### Implementation Notes for Developers

1. **Path Parameter**: Extract job_id from URL path using routing framework
2. **Firestore Query**: Query by job_id field (ensure indexed)
3. **API Key Validation**: Verify requester's API key matches the key that created the job (compare hash)
4. **Caching**: Consider caching completed results for 5 minutes to reduce Firestore reads
5. **Polling Guidance**: Include `Retry-After` header when status is pending/processing:
   ```
   Retry-After: 5
   ```
6. **Cleanup**: Firestore TTL policy automatically deletes expired jobs

#### Input Requirements

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| job_id (path) | String | Yes | Valid UUID v4 format |

#### Output Specification

| Field | Type | Description |
|-------|------|-------------|
| job_id | String | Job identifier |
| status | String | "pending", "processing", "completed", or "failed" |
| created_at | String | ISO 8601 timestamp |
| updated_at | String | ISO 8601 timestamp |
| completed_at | String | ISO 8601 timestamp (only when completed) |
| failed_at | String | ISO 8601 timestamp (only when failed) |
| processing_time_ms | Integer | Total processing time (only when completed) |
| progress | Object | Current progress (only when processing) |
| progress.stage | String | Current processing stage |
| progress.percent_complete | Integer | 0-100 |
| result | Object | Classification results (only when completed) |
| error | Object | Error details (only when failed) |

#### Authentication Requirements
Same as `/classify` endpoint, with additional validation that API key matches job creator.

---

### 3.5 API Endpoint: Sync Tags from Zoho

#### Name
`POST /admin/sync-tags`

#### Purpose
Manually trigger synchronization of tags from Zoho CRM IBRS_Tags module to the local cache.

#### Behavior
1. Validates admin API key (special elevated permission)
2. Connects to Zoho CRM API using OAuth credentials
3. Fetches all records from IBRS_Tags module
4. Compares with current cache to detect changes
5. Updates Cloud Storage cache file
6. Returns summary of changes

#### Specification

**HTTP Method**: POST

**Endpoint**: `/admin/sync-tags`

**Request Headers**:
```
X-API-Key: <admin_api_key>
```

**Request Body**: None

**Response (200 OK)**:
```json
{
  "status": "success",
  "sync_timestamp": "2025-01-23T10:35:00Z",
  "tags_total": 247,
  "changes": {
    "added": 2,
    "updated": 5,
    "removed": 1,
    "unchanged": 239
  },
  "added_tags": [
    {
      "name": "Quantum Computing",
      "short_form": "QCOMP",
      "type": "Topic"
    },
    {
      "name": "Sustainability",
      "short_form": "SUST",
      "type": "Practice"
    }
  ],
  "updated_tags": [
    {
      "name": "Cloud Computing",
      "short_form": "CLOUD",
      "type": "Practice",
      "changes": ["public_description updated"]
    }
  ],
  "removed_tags": [
    {
      "name": "Legacy System",
      "short_form": "LEGACY",
      "type": "Topic",
      "reason": "Deprecated in Zoho"
    }
  ],
  "processing_time_ms": 2341
}
```

**Error Response (401 Unauthorized)**:
```json
{
  "status": "error",
  "error_code": "INVALID_ADMIN_KEY",
  "message": "Admin API key required for this endpoint",
  "timestamp": "2025-01-23T10:35:00Z"
}
```

**Error Response (500 Internal Server Error)**:
```json
{
  "status": "error",
  "error_code": "ZOHO_SYNC_FAILED",
  "message": "Failed to sync tags from Zoho CRM",
  "details": {
    "error_type": "ZohoAPIError",
    "error_message": "Rate limit exceeded",
    "retry_after_seconds": 60
  },
  "timestamp": "2025-01-23T10:35:00Z"
}
```

#### Implementation Notes for Developers

1. **Admin Key Validation**: Check API key against admin key list in Secret Manager
2. **Zoho Authentication**:
   - Use OAuth 2.0 refresh token stored in Secret Manager
   - Refresh access token if expired
   - Handle token refresh failures gracefully
3. **Pagination**: Zoho API returns max 200 records per page, implement pagination loop
4. **Change Detection**:
   - Load current cache from Cloud Storage
   - Compare each tag by ID
   - Detect: new tags (in Zoho, not in cache), updated tags (different fields), removed tags (in cache, not in Zoho)
5. **Atomic Update**: Write new cache to temporary file, then move to production path
6. **Rollback**: Keep previous cache version for 7 days as backup
7. **Notification**: Consider sending alert to Slack/email when tags are modified
8. **Logging**: Log all changes with before/after values for audit trail

#### Input Requirements
None (empty request body)

#### Output Specification

| Field | Type | Description |
|-------|------|-------------|
| status | String | "success" or "error" |
| sync_timestamp | String | ISO 8601 timestamp of sync completion |
| tags_total | Integer | Total tags after sync |
| changes | Object | Summary of changes |
| changes.added | Integer | Number of new tags |
| changes.updated | Integer | Number of modified tags |
| changes.removed | Integer | Number of deleted tags |
| changes.unchanged | Integer | Number of unchanged tags |
| added_tags | Array[Object] | Details of newly added tags |
| updated_tags | Array[Object] | Details of modified tags |
| removed_tags | Array[Object] | Details of removed tags |
| processing_time_ms | Integer | Total sync duration |

#### Authentication Requirements

- **Required**: Yes
- **Method**: API Key
- **Header**: `X-API-Key`
- **Scope**: **Admin access** (elevated permission)
- **Validation**: Key must be in admin key list in Secret Manager
- **Rate Limit**: 10 requests/hour (prevents excessive syncing)

---

### 3.6 API Endpoint: Health Check

#### Name
`GET /health`

#### Purpose
Verify system health and operational status of all dependencies.

#### Behavior
1. No authentication required
2. Checks connectivity to:
   - Vertex AI (Gemini)
   - Cloud Storage (tag cache)
   - Firestore (if job tracking enabled)
3. Verifies tag cache exists and is recent
4. Returns health status and last sync time

#### Specification

**HTTP Method**: GET

**Endpoint**: `/health`

**Request Headers**: None required

**Response (200 OK) - Healthy**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-01-23T10:40:00Z",
  "services": {
    "vertex_ai": {
      "status": "operational",
      "model": "gemini-1.5-pro",
      "region": "us-central1"
    },
    "tag_cache": {
      "status": "operational",
      "tags_count": 247,
      "last_sync": "2025-01-23T08:00:00Z",
      "age_hours": 2.67
    },
    "firestore": {
      "status": "operational",
      "active_jobs": 3
    },
    "cloud_storage": {
      "status": "operational"
    }
  },
  "uptime_seconds": 86400
}
```

**Response (503 Service Unavailable) - Degraded**:
```json
{
  "status": "degraded",
  "version": "1.0.0",
  "timestamp": "2025-01-23T10:40:00Z",
  "services": {
    "vertex_ai": {
      "status": "error",
      "error": "Connection timeout"
    },
    "tag_cache": {
      "status": "warning",
      "tags_count": 247,
      "last_sync": "2025-01-22T08:00:00Z",
      "age_hours": 26.67,
      "warning": "Cache is stale (>24 hours old)"
    },
    "firestore": {
      "status": "operational",
      "active_jobs": 12
    },
    "cloud_storage": {
      "status": "operational"
    }
  },
  "uptime_seconds": 86400
}
```

#### Implementation Notes for Developers

1. **Lightweight Checks**: Health check should complete in < 2 seconds
2. **Vertex AI Check**: Simple API connectivity test (don't send actual classification)
3. **Cache Age Warning**: Warn if cache is > 24 hours old
4. **Firestore Check**: Query count of active jobs (optional, can skip if adds latency)
5. **Version**: Include from environment variable or deployment metadata
6. **Uptime**: Track function start time (in global scope for warm instances)
7. **Caching**: Cache health check results for 30 seconds to avoid overload
8. **Use Case**: Load balancers and monitoring systems will poll this frequently

#### Input Requirements
None

#### Output Specification

| Field | Type | Description |
|-------|------|-------------|
| status | String | "healthy", "degraded", or "unhealthy" |
| version | String | API version |
| timestamp | String | ISO 8601 timestamp |
| services | Object | Status of each dependency |
| services.[service].status | String | "operational", "warning", or "error" |
| uptime_seconds | Integer | Time since function started |

#### Authentication Requirements
None - public endpoint for monitoring

---

## 4. Data Models

### 4.1 Tag Cache Structure

**Storage Location**: Cloud Storage
**Path**: `gs://[bucket-name]/tags/current.json`
**Format**: JSON
**Update Frequency**: Every 6 hours + on-demand

```json
{
  "version": "1.0",
  "sync_timestamp": "2025-01-23T08:00:00Z",
  "sync_source": "zoho_crm",
  "tags_count": 247,
  "tags": [
    {
      "id": "zoho_record_id_001",
      "name": "Solve",
      "aliases": ["Solution", "Resolution", "Fix", "Remediation"],
      "short_form": "SLV",
      "public_description": "Content focused on solving current, immediate problems and challenges",
      "internal_commentary": "Use for tactical, actionable content with immediate ROI",
      "type": "Horizon",
      "created_at": "2023-01-15T00:00:00Z",
      "updated_at": "2024-06-20T00:00:00Z"
    },
    {
      "id": "zoho_record_id_002",
      "name": "Plan",
      "aliases": ["Planning", "Strategy", "Strategic", "Roadmap"],
      "short_form": "PLN",
      "public_description": "Content focused on planning and mid-term strategy (6-18 months)",
      "internal_commentary": "Use for strategic planning content, roadmaps, future state",
      "type": "Horizon",
      "created_at": "2023-01-15T00:00:00Z",
      "updated_at": "2024-06-20T00:00:00Z"
    },
    {
      "id": "zoho_record_id_003",
      "name": "Explore",
      "aliases": ["Exploration", "Research", "Innovation", "Emerging"],
      "short_form": "EXP",
      "public_description": "Content exploring emerging technologies and long-term trends",
      "internal_commentary": "Use for forward-looking, innovation, R&D content",
      "type": "Horizon",
      "created_at": "2023-01-15T00:00:00Z",
      "updated_at": "2024-06-20T00:00:00Z"
    },
    {
      "id": "zoho_record_id_010",
      "name": "Cybersecurity",
      "aliases": ["InfoSec", "Security", "Cyber", "Information Security"],
      "short_form": "CYB",
      "public_description": "Information security, cybersecurity, and security risk management",
      "internal_commentary": "Core IBRS practice area covering all security topics",
      "type": "Practice",
      "created_at": "2023-01-15T00:00:00Z",
      "updated_at": "2024-08-10T00:00:00Z"
    },
    {
      "id": "zoho_record_id_050",
      "name": "Zero Trust",
      "aliases": ["Zero-Trust", "ZTA", "Zero Trust Architecture", "ZT"],
      "short_form": "ZT",
      "public_description": "Zero Trust security architecture and implementation",
      "internal_commentary": "Hot topic, high engagement",
      "type": "Topic",
      "created_at": "2023-03-20T00:00:00Z",
      "updated_at": "2024-11-15T00:00:00Z"
    },
    {
      "id": "zoho_record_id_120",
      "name": "CISO",
      "aliases": ["Chief Information Security Officer", "CSO", "Security Leader"],
      "short_form": "CISO",
      "public_description": "Chief Information Security Officer role and responsibilities",
      "internal_commentary": "Key executive audience",
      "type": "Role",
      "created_at": "2023-01-15T00:00:00Z",
      "updated_at": "2024-02-28T00:00:00Z"
    },
    {
      "id": "zoho_record_id_180",
      "name": "Microsoft",
      "aliases": ["MS", "MSFT", "Microsoft Corporation"],
      "short_form": "MSFT",
      "public_description": "Microsoft Corporation and its products/services",
      "internal_commentary": "Major vendor, track carefully",
      "type": "Vendor",
      "created_at": "2023-01-15T00:00:00Z",
      "updated_at": "2024-09-05T00:00:00Z"
    },
    {
      "id": "zoho_record_id_200",
      "name": "Microsoft Azure",
      "aliases": ["Azure", "MS Azure", "Azure Cloud"],
      "short_form": "AZR",
      "public_description": "Microsoft's cloud computing platform",
      "internal_commentary": "Link to Microsoft vendor tag",
      "type": "Product",
      "created_at": "2023-01-15T00:00:00Z",
      "updated_at": "2024-09-05T00:00:00Z"
    }
  ]
}
```

**Developer Notes**:
- Load entire cache into memory at function startup (global scope)
- Reload if cache file modified timestamp changes
- Build lookup indexes: by name, by alias, by type
- Validate all required fields present during load
- Cache size: ~1MB for 240+ tags (negligible memory footprint)

---

### 4.2 Async Job Document Structure

**Storage Location**: Firestore
**Collection**: `classification_jobs`
**Document ID**: Job UUID
**TTL**: 24 hours (auto-delete via Firestore TTL policy)

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": {
    "_seconds": 1706004600,
    "_nanoseconds": 0
  },
  "updated_at": {
    "_seconds": 1706004645,
    "_nanoseconds": 0
  },
  "completed_at": {
    "_seconds": 1706004645,
    "_nanoseconds": 0
  },
  "document": {
    "filename": "large_report.pdf",
    "size_bytes": 8388608,
    "mime_type": "application/pdf",
    "storage_ref": "gs://ibrs-classifier-temp/550e8400-e29b-41d4-a716-446655440000.pdf"
  },
  "api_key_hash": "sha256:abc123...",
  "progress": {
    "stage": "completed",
    "percent_complete": 100
  },
  "result": {
    "status": "success",
    "document": {
      "filename": "large_report.pdf",
      "size_bytes": 8388608,
      "mime_type": "application/pdf",
      "text_length": 45234
    },
    "classification": {
      "horizon": {
        "name": "Solve",
        "short_form": "SLV",
        "confidence": 0.89
      },
      "practice": {
        "name": "Cloud Computing",
        "short_form": "CLOUD",
        "confidence": 0.91
      },
      "streams": [],
      "roles": ["CIO"],
      "vendors": ["AWS", "Microsoft"],
      "products": ["AWS Lambda", "Azure Functions"],
      "topics": ["Serverless", "Cloud Architecture"]
    },
    "processing_time_ms": 45123,
    "model_used": "gemini-1.5-pro"
  },
  "ttl_expires_at": {
    "_seconds": 1706091000,
    "_nanoseconds": 0
  }
}
```

**Firestore Indexes Required**:
- Single field index on `job_id` (ascending)
- Single field index on `ttl_expires_at` (ascending) for TTL policy
- Composite index on `api_key_hash` (ascending) + `created_at` (descending) for user job listing (future feature)

**Status Values**:
- `pending`: Job created, waiting in queue
- `processing`: Worker is actively processing
- `completed`: Successfully classified
- `failed`: Processing failed with error

**Progress Stages**:
- `queued`: In Cloud Tasks queue
- `downloading`: Downloading document from storage
- `text_extraction`: Extracting text from document
- `classification`: Sending to Gemini for classification
- `validation`: Validating and formatting results
- `completed`: Done

**Developer Notes**:
- Use Firestore transactions when updating status to prevent race conditions
- Set TTL policy on collection to auto-delete after 24 hours
- Document storage reference should also have 24hr TTL
- Store API key hash (SHA-256) for ownership verification, never plain key

---

### 4.3 API Key Structure

**Storage Location**: Secret Manager
**Secret Names**:
- `ibrs-classifier-api-keys` (standard keys)
- `ibrs-classifier-admin-keys` (admin keys)

**Format**: JSON array of key objects

```json
{
  "keys": [
    {
      "key_id": "key_001",
      "key_value": "ibrs_live_abc123xyz789def456ghi789",
      "key_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "name": "Production API - Main",
      "description": "Primary production API key for IBRS website",
      "permissions": ["classify", "classify_async", "status"],
      "rate_limit": 60,
      "created_at": "2025-01-15T00:00:00Z",
      "created_by": "admin@ibrs.com",
      "active": true,
      "expires_at": null
    },
    {
      "key_id": "key_002",
      "key_value": "ibrs_test_test123test456test789test",
      "key_hash": "sha256:a2c3e44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b999",
      "name": "Testing Environment",
      "description": "API key for development and testing",
      "permissions": ["classify", "classify_async", "status"],
      "rate_limit": 30,
      "created_at": "2025-01-10T00:00:00Z",
      "created_by": "dev@ibrs.com",
      "active": true,
      "expires_at": "2025-12-31T23:59:59Z"
    }
  ],
  "admin_keys": [
    {
      "key_id": "admin_001",
      "key_value": "ibrs_admin_secure789admin456admin123",
      "key_hash": "sha256:b4d5e66398fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b777",
      "name": "Admin - Tag Management",
      "description": "Admin key for tag sync operations",
      "permissions": ["classify", "classify_async", "status", "admin_sync_tags"],
      "rate_limit": 10,
      "created_at": "2025-01-15T00:00:00Z",
      "created_by": "admin@ibrs.com",
      "active": true,
      "expires_at": null
    }
  ]
}
```

**Key Format Convention**:
- Prefix: `ibrs_`
- Environment: `live_`, `test_`, `admin_`
- Random string: 24-32 alphanumeric characters
- Example: `ibrs_live_abc123xyz789def456`

**Developer Notes**:
- Load keys from Secret Manager at function startup
- Cache in memory (global scope) and refresh every 5 minutes
- Always compare using key_hash for security
- Check `active` flag and `expires_at` timestamp
- Enforce rate limits using Cloud Firestore or Memorystore
- Never log full API keys, only key_id

---

## 5. Non-Functional Requirements

### 5.1 Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Sync API Response Time (p95) | < 10 seconds | Time from request to response |
| Sync API Response Time (p50) | < 5 seconds | Median response time |
| Async API Accept Time | < 1 second | Time to return job ID |
| Async Job Processing Time | < 60 seconds | Time from queue to completion |
| Status Check Response Time | < 500ms | Time to return job status |
| Tag Sync Duration | < 30 seconds | Time to sync all tags from Zoho |
| Health Check Response Time | < 2 seconds | Time to check all services |
| Cold Start Time | < 5 seconds | Function initialization time |
| Text Extraction (1MB PDF) | < 3 seconds | Time to extract text |
| Gemini Classification | < 5 seconds | Time for AI analysis |

### 5.2 Scalability

| Aspect | Requirement | Implementation |
|--------|-------------|----------------|
| Daily Volume | 100 documents/day (initial) | Cloud Functions auto-scale |
| Peak Concurrency | 10 simultaneous requests | Cloud Functions max instances: 10 |
| Future Scalability | Up to 1000 documents/day | Increase max instances, add queuing |
| Maximum Document Size | 50MB | Hard limit, enforced at API gateway |
| Tag Cache Size | 500+ tags supported | In-memory cache, < 2MB |
| Job Retention | 24 hours | Firestore TTL cleanup |

### 5.3 Reliability

| Aspect | Target | Implementation |
|--------|--------|----------------|
| API Availability | 99.9% uptime | Cloud Functions SLA + retry logic |
| Error Rate | < 1% of requests | Comprehensive error handling |
| Data Loss | Zero tolerance | No persistent data (stateless) |
| Retry Logic | 3 attempts for transient failures | Exponential backoff |
| Timeout Handling | Graceful degradation | Return partial results if possible |
| Tag Sync Failures | Alert after 3 consecutive failures | Cloud Monitoring alerts |

### 5.4 Security

| Aspect | Requirement | Implementation |
|--------|-------------|----------------|
| Transport Security | TLS 1.2+ only | GCP enforced HTTPS |
| Authentication | API Key required | Custom middleware |
| Key Storage | Encrypted at rest | Secret Manager |
| Key Rotation | Quarterly recommended | Manual process, documented |
| Input Validation | Strict validation | Schema validation, size limits |
| Output Sanitization | Remove sensitive data | No PII in logs |
| Rate Limiting | 60 req/min per key | Firestore-based tracking |
| Audit Logging | All requests logged | Cloud Logging |
| CORS | Configurable allowed origins | Environment-based config |

### 5.5 Monitoring & Observability

#### Key Metrics to Track

1. **Request Metrics**
   - Total requests per endpoint
   - Success vs. error rate
   - Response time distribution (p50, p95, p99)
   - Requests by API key

2. **Processing Metrics**
   - Documents processed by format
   - Text extraction time by format
   - Classification time
   - Tags assigned distribution

3. **Queue Metrics**
   - Async jobs pending
   - Async jobs processing
   - Async job completion time
   - Job failure rate

4. **Dependency Metrics**
   - Vertex AI API latency
   - Vertex AI error rate
   - Zoho CRM API latency
   - Tag cache age

5. **Resource Metrics**
   - Function invocations
   - Function execution time
   - Memory usage
   - Cold start frequency

#### Alert Conditions

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High Error Rate | Error rate > 5% for 5 minutes | Critical | Page on-call engineer |
| Slow Responses | p95 latency > 15s for 10 minutes | Warning | Investigate performance |
| Vertex AI Failures | 10+ failures in 5 minutes | Critical | Check Vertex AI status, quotas |
| Tag Sync Failed | 3 consecutive sync failures | Warning | Verify Zoho connectivity |
| Stale Tag Cache | Cache age > 24 hours | Warning | Trigger manual sync |
| High Queue Depth | > 20 jobs pending for 15 minutes | Warning | Check worker function |
| Quota Warning | Approaching Vertex AI quota (80%) | Warning | Review usage, request increase |

### 5.6 Cost Management

**Estimated Monthly Costs (100 docs/day)**:

| Service | Usage | Estimated Cost |
|---------|-------|----------------|
| Cloud Functions | ~3000 invocations | $0.10 |
| Vertex AI (Gemini) | ~3M tokens | $10.50 |
| Cloud Storage | < 1GB | $0.02 |
| Firestore | ~1000 reads/writes | $0.10 |
| Cloud Tasks | ~500 tasks | $0.01 |
| Cloud Scheduler | 4 jobs | $0.40 |
| Egress | ~10GB | $1.20 |
| **Total** | | **~$12.33/month** |

**Cost Optimization Strategies**:
1. Cache tag data in Cloud Functions memory (reduce storage reads)
2. Use Gemini Flash model for simple documents (lower token cost)
3. Implement response caching for identical documents
4. Set appropriate function timeout (don't pay for idle time)
5. Clean up temp storage immediately (don't pay for retention)

---

## 6. Integration Requirements

### 6.1 Zoho CRM Integration

#### Overview
Synchronize tag taxonomy from custom IBRS_Tags module in Zoho CRM.

#### Authentication
- **Method**: OAuth 2.0
- **Grant Type**: Authorization Code (one-time) + Refresh Token
- **Scopes**: `ZohoCRM.modules.READ`, `ZohoCRM.settings.READ`
- **Token Storage**: GCP Secret Manager
- **Token Refresh**: Automatic when expired (expires every 60 minutes)

#### API Endpoints Used

**1. Fetch Tags**
```
GET https://www.zohoapis.com/crm/v2/IBRS_Tags
```

**Query Parameters**:
- `fields`: name,Alias_1,Alias_2,Alias_3,Alias_4,Short_Form,Public_Description,Internal_Commentary,Type
- `per_page`: 200
- `page`: [page_number]

**Response Structure**:
```json
{
  "data": [
    {
      "id": "5428652000001234567",
      "name": "Cybersecurity",
      "Alias_1": "InfoSec",
      "Alias_2": "Security",
      "Alias_3": "Cyber",
      "Alias_4": "Information Security",
      "Short_Form": "CYB",
      "Public_Description": "Information security and cybersecurity topics",
      "Internal_Commentary": "Core practice area",
      "Type": "Practice"
    }
  ],
  "info": {
    "per_page": 200,
    "count": 200,
    "page": 1,
    "more_records": true
  }
}
```

#### Error Handling

| Error Code | Description | Action |
|------------|-------------|--------|
| 401 | Invalid token | Refresh access token |
| 429 | Rate limit exceeded | Wait and retry with backoff |
| 500 | Zoho server error | Retry up to 3 times |
| INVALID_TOKEN | Token expired | Refresh and retry |

#### Data Mapping

| Zoho Field | Internal Field | Transformation |
|------------|----------------|----------------|
| id | id | Direct |
| name | name | Trim whitespace |
| Alias_1 to Alias_4 | aliases | Array, filter empty |
| Short_Form | short_form | Uppercase, trim |
| Public_Description | public_description | Trim |
| Internal_Commentary | internal_commentary | Trim, nullable |
| Type | type | Validate enum |

#### Implementation Notes

1. **Pagination**: Loop through all pages until `more_records` is false
2. **Rate Limits**: Zoho allows 100 API calls per minute per org
3. **Retry Logic**: Exponential backoff for rate limits (wait 60s, 120s, 240s)
4. **Validation**: Ensure required fields (name, short_form, type) are present
5. **Type Validation**: Type must be one of: Horizon, Practice, Stream, Role, Vendor, Product, Topic
6. **Caching**: Store OAuth tokens in Secret Manager, refresh every 50 minutes
7. **Testing**: Use Zoho Sandbox environment for development

---

### 6.2 Vertex AI Integration

#### Overview
Use Google Gemini 1.5 Pro via Vertex AI for document classification.

#### Authentication
- **Method**: Application Default Credentials (ADC)
- **Service Account**: `ibrs-classifier@[project-id].iam.gserviceaccount.com`
- **Required Roles**: `roles/aiplatform.user`

#### Model Configuration

```python
{
  "model": "gemini-1.5-pro",
  "project": "[gcp-project-id]",
  "location": "us-central1",
  "generation_config": {
    "temperature": 0.1,  # Low temperature for consistent results
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json"
  },
  "safety_settings": {
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE"
  }
}
```

#### Prompt Structure

```
System Instruction:
You are a document classification assistant for IBRS (Information and Business Research Services). Your task is to analyze documents and assign relevant tags from a predefined taxonomy.

Classification Rules:
1. You MUST assign exactly 1 Horizon tag (Solve, Plan, or Explore)
2. You MUST assign exactly 1 Practice tag
3. You MAY assign 0 or more tags of types: Stream, Role, Vendor, Product, Topic
4. Only use tags from the provided list
5. Return confidence scores between 0.0 and 1.0
6. Match tags using name or aliases

User Prompt:
Analyze the following document and classify it using the provided tags.

Document Text:
[extracted text content]

Available Tags:
[JSON array of all tags with name, aliases, description, type]

Response Format:
Return a JSON object with this exact structure:
{
  "horizon": {"name": "Solve", "confidence": 0.92},
  "practice": {"name": "Cybersecurity", "confidence": 0.88},
  "streams": [{"name": "Risk Management", "confidence": 0.85}],
  "roles": [{"name": "CISO", "confidence": 0.81}],
  "vendors": [{"name": "Microsoft", "confidence": 0.79}],
  "products": [{"name": "Azure", "confidence": 0.81}],
  "topics": [{"name": "Zero Trust", "confidence": 0.76}]
}
```

#### Rate Limits & Quotas

| Metric | Limit | Notes |
|--------|-------|-------|
| Requests per minute | 60 | Default quota |
| Tokens per minute | 2M | Input + output combined |
| Concurrent requests | 10 | Configurable |
| Max input tokens | 1M | Gemini 1.5 Pro limit |
| Max output tokens | 8192 | Configured limit |

#### Error Handling

| Error | Description | Action |
|-------|-------------|--------|
| 429 | Quota exceeded | Retry with exponential backoff |
| 400 | Invalid request | Log error, return validation error |
| 500 | Model error | Retry up to 3 times |
| 503 | Service unavailable | Wait 30s and retry |

#### Cost Optimization

- **Input tokens**: $0.00125 per 1K tokens (> 128K) or $0.0003125 per 1K tokens (< 128K)
- **Output tokens**: $0.005 per 1K tokens (> 128K) or $0.00125 per 1K tokens (< 128K)
- **Optimization strategies**:
  1. Truncate very long documents to first 100K characters
  2. Use cached tag descriptions (don't repeat in every call)
  3. Request JSON output mode (more efficient parsing)
  4. Consider Gemini Flash for simple/short documents ($0.000035 per 1K tokens)

#### Implementation Notes

1. **SDK**: Use official `google-cloud-aiplatform` Python library
2. **Streaming**: Not required for this use case (wait for complete response)
3. **Response Validation**: Always validate JSON structure before returning
4. **Timeout**: Set 45-second timeout for Gemini calls
5. **Retry Logic**: Implement exponential backoff (1s, 2s, 4s)
6. **Logging**: Log token usage for cost tracking

---

## 7. Error Handling

### 7.1 Error Response Format

All error responses follow a consistent structure:

```json
{
  "status": "error",
  "error_code": "ERROR_CODE_CONSTANT",
  "message": "Human-readable error description",
  "details": {
    "field_name": "additional context",
    "another_field": "more information"
  },
  "timestamp": "2025-01-23T10:30:00Z",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 7.2 Error Codes

| Error Code | HTTP Status | Description | User Action |
|------------|-------------|-------------|-------------|
| **Authentication & Authorization** |
| INVALID_API_KEY | 401 | API key is missing or invalid | Provide valid X-API-Key header |
| EXPIRED_API_KEY | 401 | API key has expired | Contact admin for new key |
| INVALID_ADMIN_KEY | 403 | Endpoint requires admin key | Use admin API key |
| RATE_LIMIT_EXCEEDED | 429 | Too many requests | Wait and retry after Retry-After seconds |
| **Request Validation** |
| MISSING_FILE | 400 | No file provided in request | Include file in multipart upload or content in JSON |
| INVALID_MIME_TYPE | 400 | Unsupported file format | Use supported format (PDF, DOCX, PPTX, TXT, JPG, PNG, GIF) |
| DOCUMENT_TOO_LARGE | 413 | Document exceeds size limit | Use /classify/async for files 5-50MB |
| DOCUMENT_TOO_SMALL | 400 | Document is empty or < 100 bytes | Provide valid document with content |
| INVALID_BASE64 | 400 | Base64 content cannot be decoded | Check encoding format |
| INVALID_JSON | 400 | Request body is not valid JSON | Fix JSON syntax |
| MISSING_REQUIRED_FIELD | 400 | Required field missing | Include required fields in request |
| **Processing Errors** |
| EXTRACTION_FAILED | 500 | Failed to extract text | Document may be corrupted or password-protected |
| EXTRACTION_NO_TEXT | 422 | No text could be extracted | Document appears to be empty or image-only without OCR-able text |
| OCR_FAILED | 500 | OCR processing failed on image | Image quality too low or text not readable |
| TEXT_TOO_SHORT | 422 | Extracted text < 50 characters | Document doesn't contain enough text to classify |
| **Classification Errors** |
| CLASSIFICATION_FAILED | 500 | AI classification failed | Retry request or contact support |
| VERTEX_AI_ERROR | 500 | Vertex AI API error | Service issue, retry after delay |
| VERTEX_AI_TIMEOUT | 504 | AI response timeout | Document may be too complex, try /classify/async |
| VALIDATION_FAILED | 500 | Classification didn't meet rules | System error, contact support |
| NO_HORIZON_TAG | 500 | AI didn't assign Horizon tag | System validation failed, contact support |
| NO_PRACTICE_TAG | 500 | AI didn't assign Practice tag | System validation failed, contact support |
| TAG_CACHE_EMPTY | 503 | No tags available | Tag sync needed, contact admin |
| **Async Job Errors** |
| JOB_NOT_FOUND | 404 | Job ID not found or expired | Jobs expire after 24 hours |
| JOB_CREATION_FAILED | 500 | Failed to create async job | Retry request |
| QUEUE_FULL | 503 | Job queue at capacity | Wait and retry in a few minutes |
| **Integration Errors** |
| ZOHO_SYNC_FAILED | 500 | Failed to sync tags from Zoho | Check Zoho connectivity and credentials |
| ZOHO_AUTH_FAILED | 500 | Zoho authentication failed | OAuth token may need refresh |
| ZOHO_RATE_LIMIT | 429 | Zoho API rate limit hit | Wait 60 seconds and retry sync |
| TAG_CACHE_LOAD_FAILED | 500 | Failed to load tag cache | Check Cloud Storage permissions |
| **System Errors** |
| INTERNAL_ERROR | 500 | Unexpected internal error | Contact support with request_id |
| SERVICE_UNAVAILABLE | 503 | Service temporarily unavailable | Retry after delay |
| TIMEOUT | 504 | Request processing timeout | Try /classify/async for large documents |

### 7.3 Retry Strategies

#### For API Clients

| Error Type | Should Retry? | Strategy |
|------------|---------------|----------|
| 401 Unauthorized | No | Fix authentication |
| 400 Bad Request | No | Fix request format |
| 413 Payload Too Large | No | Use async endpoint |
| 422 Unprocessable | No | Document issue, don't retry |
| 429 Rate Limit | Yes | Wait per Retry-After header |
| 500 Internal Error | Yes | Exponential backoff: 1s, 2s, 4s |
| 503 Service Unavailable | Yes | Wait 30s, then retry |
| 504 Timeout | Yes | Switch to async or retry once |

#### For Internal Services

**Vertex AI Calls**:
```python
max_retries = 3
base_delay = 1  # seconds
for attempt in range(max_retries):
    try:
        response = vertex_ai.classify(...)
        break
    except RateLimitError:
        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)  # Exponential backoff
            time.sleep(delay)
        else:
            raise
```

**Zoho API Calls**:
```python
max_retries = 3
for attempt in range(max_retries):
    try:
        response = zoho_api.fetch_tags()
        break
    except RateLimitError as e:
        if attempt < max_retries - 1:
            wait_time = e.retry_after or 60
            time.sleep(wait_time)
        else:
            raise
```

### 7.4 Logging Strategy

#### Log Levels

| Level | Use Case | Examples |
|-------|----------|----------|
| DEBUG | Development debugging | Parameter values, intermediate results |
| INFO | Normal operations | Request received, classification completed |
| WARNING | Recoverable issues | Retry after transient error, stale cache |
| ERROR | Request failures | Extraction failed, classification failed |
| CRITICAL | System failures | Service unavailable, cannot load tag cache |

#### Required Log Fields

Every log entry should include:
```json
{
  "timestamp": "2025-01-23T10:30:00.123Z",
  "severity": "INFO",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "api_key_id": "key_001",
  "endpoint": "/classify",
  "message": "Classification completed successfully",
  "duration_ms": 3421,
  "document_size_bytes": 245678,
  "mime_type": "application/pdf",
  "tags_assigned": 7
}
```

#### Security Considerations

- **Never log**: Full API keys, document content, PII
- **Hash**: API keys (log key_id or hash only)
- **Sanitize**: Filenames (remove paths, limit length)
- **Redact**: Error details that might leak sensitive info

---

## 8. Constraints & Assumptions

### 8.1 Technical Constraints

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Maximum document size | 50MB | Vertex AI context limits, processing time |
| Minimum text length | 50 characters | Insufficient text for meaningful classification |
| Sync processing limit | 5MB | Keep response time under 10 seconds |
| Maximum concurrent requests | 10 | Vertex AI quota and cost management |
| Tag cache refresh interval | 6 hours | Balance freshness vs. Zoho API usage |
| Async job retention | 24 hours | Storage cost vs. user convenience |
| API key rate limit | 60 req/min | Prevent abuse, manage costs |
| Function timeout | 60 seconds | Cloud Functions limit (2nd gen) |
| Cold start budget | 5 seconds | Acceptable user experience |

### 8.2 Assumptions

#### About Documents
1. Documents are primarily English text
2. Documents contain sufficient text for classification (>50 words ideal)
3. PDF documents are not password-protected
4. Image documents have clear, readable text for OCR
5. Documents represent IBRS business domain (IT, cybersecurity, business strategy)

#### About Tags
1. Tags are well-maintained in Zoho CRM
2. Tag descriptions are clear and distinct
3. Tags are relatively stable (changes are infrequent)
4. Each tag type has sufficient examples in taxonomy
5. 6-hour sync interval is acceptable for tag freshness

#### About Usage
1. Volume is low initially (< 100 docs/day)
2. Most documents are under 5MB (sync processing)
3. Users can tolerate 5-10 second classification time
4. Async jobs are polled by client (no webhooks required initially)
5. API is primarily consumed by IBRS internal systems

#### About Infrastructure
1. GCP services have 99.9%+ uptime
2. Vertex AI Gemini API is reliable and available
3. Zoho CRM API is accessible from GCP
4. Network latency is minimal (< 100ms)
5. Cloud Functions can handle traffic spikes via auto-scaling

### 8.3 Future Enhancements (Out of Scope for v1.0)

1. **Webhook Support**: Push notifications when async jobs complete
2. **Batch Processing**: Upload multiple documents in one request
3. **Custom Training**: Fine-tune model on IBRS historical data
4. **Tag Suggestions**: API to suggest new tags based on unclassified content
5. **Confidence Thresholds**: Configurable minimum confidence scores
6. **Multi-language Support**: Support for non-English documents
7. **User Management**: Web UI for API key management
8. **Analytics Dashboard**: Visualization of classification trends
9. **Feedback Loop**: Allow users to correct classifications
10. **Version History**: Track classification changes over time

---

## Appendix A: Example API Calls

### Example 1: Classify Small PDF (Synchronous)

**Request**:
```bash
curl -X POST https://us-central1-ibrs-project.cloudfunctions.net/classify \
  -H "X-API-Key: ibrs_live_abc123xyz789def456" \
  -F "file=@cybersecurity_report.pdf"
```

**Response**:
```json
{
  "status": "success",
  "document": {
    "filename": "cybersecurity_report.pdf",
    "size_bytes": 524288,
    "mime_type": "application/pdf",
    "text_length": 3421
  },
  "classification": {
    "horizon": {
      "name": "Solve",
      "short_form": "SLV",
      "confidence": 0.89,
      "matched_via": "primary"
    },
    "practice": {
      "name": "Cybersecurity",
      "short_form": "CYB",
      "confidence": 0.94,
      "matched_via": "alias"
    },
    "streams": [
      {
        "name": "Risk Management",
        "short_form": "RISK",
        "confidence": 0.82,
        "matched_via": "primary"
      }
    ],
    "roles": [
      {
        "name": "CISO",
        "short_form": "CISO",
        "confidence": 0.87,
        "matched_via": "primary"
      }
    ],
    "vendors": [],
    "products": [],
    "topics": [
      {
        "name": "Zero Trust",
        "short_form": "ZT",
        "confidence": 0.79,
        "matched_via": "alias"
      },
      {
        "name": "Ransomware",
        "short_form": "RANS",
        "confidence": 0.85,
        "matched_via": "primary"
      }
    ]
  },
  "processing_time_ms": 4127,
  "model_used": "gemini-1.5-pro"
}
```

### Example 2: Classify Large Document (Asynchronous)

**Request**:
```bash
curl -X POST https://us-central1-ibrs-project.cloudfunctions.net/classify/async \
  -H "X-API-Key: ibrs_live_abc123xyz789def456" \
  -F "file=@large_whitepaper.pdf"
```

**Response**:
```json
{
  "status": "accepted",
  "job_id": "a3f12b8c-9d7e-4f1a-b2c3-456789abcdef",
  "status_url": "/classify/status/a3f12b8c-9d7e-4f1a-b2c3-456789abcdef",
  "estimated_completion_seconds": 35,
  "created_at": "2025-01-23T14:22:00Z"
}
```

**Check Status**:
```bash
curl -X GET https://us-central1-ibrs-project.cloudfunctions.net/classify/status/a3f12b8c-9d7e-4f1a-b2c3-456789abcdef \
  -H "X-API-Key: ibrs_live_abc123xyz789def456"
```

**Status Response (Completed)**:
```json
{
  "job_id": "a3f12b8c-9d7e-4f1a-b2c3-456789abcdef",
  "status": "completed",
  "created_at": "2025-01-23T14:22:00Z",
  "completed_at": "2025-01-23T14:22:38Z",
  "processing_time_ms": 38142,
  "result": {
    "status": "success",
    "document": {
      "filename": "large_whitepaper.pdf",
      "size_bytes": 10485760,
      "mime_type": "application/pdf",
      "text_length": 52341
    },
    "classification": {
      "horizon": {
        "name": "Explore",
        "short_form": "EXP",
        "confidence": 0.91,
        "matched_via": "primary"
      },
      "practice": {
        "name": "Cloud Computing",
        "short_form": "CLOUD",
        "confidence": 0.88,
        "matched_via": "alias"
      },
      "streams": [],
      "roles": [
        {
          "name": "CIO",
          "short_form": "CIO",
          "confidence": 0.78,
          "matched_via": "primary"
        }
      ],
      "vendors": [
        {
          "name": "AWS",
          "short_form": "AWS",
          "confidence": 0.85,
          "matched_via": "primary"
        }
      ],
      "products": [
        {
          "name": "AWS Lambda",
          "short_form": "LAMBDA",
          "confidence": 0.81,
          "matched_via": "primary"
        }
      ],
      "topics": [
        {
          "name": "Serverless",
          "short_form": "SVRLS",
          "confidence": 0.87,
          "matched_via": "primary"
        }
      ]
    },
    "model_used": "gemini-1.5-pro"
  }
}
```

### Example 3: Sync Tags from Zoho

**Request**:
```bash
curl -X POST https://us-central1-ibrs-project.cloudfunctions.net/admin/sync-tags \
  -H "X-API-Key: ibrs_admin_secure789admin456"
```

**Response**:
```json
{
  "status": "success",
  "sync_timestamp": "2025-01-23T15:00:00Z",
  "tags_total": 249,
  "changes": {
    "added": 3,
    "updated": 2,
    "removed": 1,
    "unchanged": 241
  },
  "added_tags": [
    {
      "name": "Quantum Computing",
      "short_form": "QCOMP",
      "type": "Topic"
    },
    {
      "name": "Sustainability",
      "short_form": "SUST",
      "type": "Topic"
    },
    {
      "name": "Web3",
      "short_form": "WEB3",
      "type": "Topic"
    }
  ],
  "updated_tags": [
    {
      "name": "Cloud Computing",
      "short_form": "CLOUD",
      "type": "Practice",
      "changes": ["public_description updated", "alias added"]
    }
  ],
  "removed_tags": [
    {
      "name": "Flash Storage",
      "short_form": "FLASH",
      "type": "Product",
      "reason": "Marked as deprecated in Zoho"
    }
  ],
  "processing_time_ms": 2847
}
```

---

## Document Change History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-01-23 | Initial specification | IBRS Development Team |

---

**End of Software Specifications Document**