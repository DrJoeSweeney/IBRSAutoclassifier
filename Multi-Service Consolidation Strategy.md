# Multi-Service Consolidation Strategy
## Combining 12+ Low-Volume APIs on Google Cloud Platform

**Version:** 1.0
**Date:** January 2025
**Scenario:** 12+ API services, each with < 20 calls/day

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Consolidation Opportunity](#consolidation-opportunity)
3. [Architecture Options](#architecture-options)
4. [Recommended Approach](#recommended-approach)
5. [Cost Analysis](#cost-analysis)
6. [Implementation Guide](#implementation-guide)
7. [Migration Strategy](#migration-strategy)
8. [Operational Benefits](#operational-benefits)
9. [Risk Mitigation](#risk-mitigation)

---

## Current State Analysis

### Current Architecture (Assumed)

```
Service 1 (20 calls/day) → Separate deployment (Cloud Functions/Run)
Service 2 (15 calls/day) → Separate deployment
Service 3 (10 calls/day) → Separate deployment
Service 4 (20 calls/day) → Separate deployment
Service 5 (12 calls/day) → Separate deployment
Service 6 (18 calls/day) → Separate deployment
Service 7 (8 calls/day)  → Separate deployment
Service 8 (15 calls/day) → Separate deployment
Service 9 (20 calls/day) → Separate deployment
Service 10 (10 calls/day)→ Separate deployment
Service 11 (14 calls/day)→ Separate deployment
Service 12 (16 calls/day)→ Separate deployment
IBRS Classifier (40/day)→ Separate deployment

Total: 13 services, ~220 calls/day combined
```

### Current Cost Estimate (If Separate Cloud Functions)

| Service | Calls/Day | Monthly Calls | Est. Cost/Month |
|---------|-----------|---------------|-----------------|
| Service 1-12 (avg) | 15 | 450 | $5-8 each |
| IBRS Classifier | 40 | 1,200 | $8 |
| **Total (13 services)** | **220** | **6,600** | **$70-100** |

### Current Operational Burden

- ❌ **13 separate deployments** to manage
- ❌ **13 different endpoints** to document
- ❌ **13 sets of environment variables** to maintain
- ❌ **13 separate monitoring dashboards**
- ❌ **13 cold start problems** (each service hits cold start on nearly every call)
- ❌ **Duplicate code** (auth, logging, error handling repeated 13x)
- ❌ **Inconsistent patterns** across services
- ❌ **High cognitive overhead** for developers

---

## Consolidation Opportunity

### The Problem with Low-Volume Services

**With < 20 calls/day per service:**
- Functions go cold between every request
- Every user experiences 2-5 second cold start delay
- Paying infrastructure overhead 13x
- Managing complexity 13x
- Duplicating effort 13x

### The Solution: Unified Platform

**Consolidate into a single always-warm Cloud Run instance:**
```
                    ┌─────────────────────────────────┐
                    │   Unified API Platform          │
                    │   (Single Cloud Run Service)    │
                    │                                 │
All Requests ──────>│   /classifier/*                 │
                    │   /service1/*                   │
                    │   /service2/*                   │
                    │   /service3/*                   │
                    │   ... (all 13 services)         │
                    │                                 │
                    │   Shared:                       │
                    │   • Authentication              │
                    │   • Logging                     │
                    │   • Error Handling              │
                    │   • Monitoring                  │
                    │   • Rate Limiting               │
                    └─────────────────────────────────┘
                              ↓
                    Single always-warm instance
                    Zero cold starts for all services
                    $15-20/month total
```

### Benefits at a Glance

| Metric | Current (Separate) | Consolidated | Improvement |
|--------|-------------------|--------------|-------------|
| **Monthly Cost** | $70-100 | $15-20 | **75-85% reduction** |
| **Cold Starts** | 95%+ of requests | 0% | **100% elimination** |
| **Deployments** | 13 separate | 1 unified | **92% reduction** |
| **Response Time** | 8-20s (with cold start) | 5-15s | **Up to 60% faster** |
| **Maintenance Effort** | 13x everything | 1x everything | **92% reduction** |
| **Code Duplication** | High | Minimal | Shared utilities |
| **Monitoring Complexity** | 13 dashboards | 1 dashboard | Unified observability |

---

## Architecture Options

### Option 1: Single Monolithic Service (Simple) ⭐ **RECOMMENDED**

```python
# Single Flask app with all services
from flask import Flask

app = Flask(__name__)

# IBRS Classifier routes
@app.route('/classifier/classify', methods=['POST'])
def classifier_classify():
    # Classifier logic
    pass

@app.route('/classifier/health', methods=['GET'])
def classifier_health():
    pass

# Service 1 routes
@app.route('/service1/endpoint1', methods=['GET'])
def service1_endpoint1():
    pass

@app.route('/service1/endpoint2', methods=['POST'])
def service1_endpoint2():
    pass

# Service 2 routes
@app.route('/service2/process', methods=['POST'])
def service2_process():
    pass

# ... repeat for all 13 services
```

**Pros:**
- ✅ Simplest architecture
- ✅ Easiest to deploy (one command)
- ✅ Maximum resource sharing
- ✅ Lowest cost
- ✅ Fastest cold start (when needed)

**Cons:**
- ⚠️ All services share fate (if container crashes, all down)
- ⚠️ Larger container image
- ⚠️ Need good code organization

**Best For:** Your use case with 13 low-volume services

---

### Option 2: Modular Monolith with Blueprints (Organized)

```python
# Organized with Flask Blueprints
from flask import Flask
from services.classifier import classifier_bp
from services.service1 import service1_bp
from services.service2 import service2_bp

app = Flask(__name__)

# Register each service as a Blueprint
app.register_blueprint(classifier_bp, url_prefix='/classifier')
app.register_blueprint(service1_bp, url_prefix='/service1')
app.register_blueprint(service2_bp, url_prefix='/service2')
# ... repeat for all services
```

**Pros:**
- ✅ Better code organization
- ✅ Each service is a self-contained module
- ✅ Easier to test individual services
- ✅ Can add/remove services easily
- ✅ Still single deployment

**Cons:**
- ⚠️ Slightly more complex setup
- ⚠️ Still shared fate

**Best For:** Long-term maintainability with multiple developers

---

### Option 3: API Gateway + Multiple Cloud Run Services

```
API Gateway (single URL)
    ↓
    ├─> /classifier/* ──> Classifier Service (Cloud Run)
    ├─> /service1/*  ──> Service 1 (Cloud Run)
    ├─> /service2/*  ──> Service 2 (Cloud Run)
    └─> /service3/*  ──> Service 3 (Cloud Run)
```

**Pros:**
- ✅ Service isolation (failures don't cascade)
- ✅ Independent scaling
- ✅ Can use different languages/runtimes

**Cons:**
- ❌ Higher cost ($5-10 per service minimum)
- ❌ More complex to manage
- ❌ API Gateway costs extra
- ❌ Still have cold start issues

**Best For:** High-volume services needing isolation (not your case)

---

### Option 4: Shared Cloud Run + Service Mesh

```
Single Cloud Run with internal routing
├─> Classifier module
├─> Service 1 module
├─> Service 2 module
└─> Shared services (auth, logging, etc.)
```

**Pros:**
- ✅ Good code organization
- ✅ Shared infrastructure
- ✅ Internal service discovery

**Cons:**
- ⚠️ More complex architecture
- ⚠️ Overkill for low volume

**Best For:** Microservices at scale (not needed here)

---

## Recommended Approach

### 🏆 **Option 2: Modular Monolith with Flask Blueprints**

This provides the best balance of:
- Simplicity (single deployment)
- Organization (clear module boundaries)
- Cost efficiency (one always-warm instance)
- Maintainability (easy to understand and modify)

### Recommended Architecture

```
Unified API Platform (Cloud Run)
│
├── main.py                         # Entry point, app initialization
├── config/
│   ├── __init__.py
│   └── settings.py                 # Shared configuration
│
├── shared/                         # Shared utilities (reused by all services)
│   ├── __init__.py
│   ├── auth.py                     # Unified authentication
│   ├── error_handlers.py           # Standard error responses
│   ├── logging_config.py           # Centralized logging
│   ├── monitoring.py               # Metrics and tracing
│   └── utils.py                    # Common helpers
│
├── services/                       # Individual service modules
│   ├── classifier/                 # IBRS Classifier
│   │   ├── __init__.py
│   │   ├── routes.py               # Flask Blueprint
│   │   ├── logic.py                # Business logic
│   │   ├── models.py               # Data models
│   │   └── utils.py                # Service-specific helpers
│   │
│   ├── service1/                   # Your Service 1
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── logic.py
│   │   └── models.py
│   │
│   ├── service2/                   # Your Service 2
│   │   └── ... (same structure)
│   │
│   └── ... (all 13 services)
│
├── Dockerfile                      # Container definition
├── requirements.txt                # Python dependencies
└── .dockerignore
```

---

## Cost Analysis

### Current State (13 Separate Cloud Functions)

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| 13 Functions (avg 450 calls/mo) | 13 × $6 avg | $78 |
| Vertex AI (IBRS only) | ~600K tokens | $7.50 |
| Cloud Storage (13 separate) | 13 × $0.05 | $0.65 |
| Cloud Scheduler (if used) | 13 × $0.40 | $5.20 |
| **TOTAL** | | **~$91.35/month** |

### Consolidated State (Single Cloud Run)

| Item | Calculation | Monthly Cost |
|------|-------------|--------------|
| Cloud Run (1 instance, always-on) | 256MB-1GB RAM | $9.60 |
| Vertex AI (IBRS only) | ~600K tokens | $7.50 |
| Cloud Storage (shared) | Single bucket | $0.05 |
| Firestore (shared) | Minimal usage | $0.05 |
| Container Registry | < 1GB | $0.05 |
| Cloud Scheduler (1 job) | Trigger health check | $0.40 |
| **TOTAL** | | **~$17.65/month** |

### Cost Comparison

```
Current (Separate):  $91/month  ████████████████████
Consolidated:        $18/month  ████
                                ─────────────────────
Savings:             $73/month  (80% reduction!) 💰
Annual Savings:      $876/year
```

**ROI Calculation:**
- Migration time: ~16 hours (13 services × ~1.25 hours each)
- Monthly savings: $73
- **Payback period: 2.6 months**
- First-year net benefit: $876 - (16 hours × hourly rate)

---

## Implementation Guide

### Phase 1: Setup Unified Platform (2 hours)

#### 1.1 Create Project Structure

```bash
mkdir unified-api-platform
cd unified-api-platform

# Create directory structure
mkdir -p config shared services
mkdir -p services/classifier services/service1 services/service2

# Create __init__.py files
touch config/__init__.py shared/__init__.py services/__init__.py
touch services/classifier/__init__.py
touch services/service1/__init__.py
touch services/service2/__init__.py
```

#### 1.2 Create Main Application

```python
# main.py
"""
Unified API Platform
Consolidates 13+ low-volume services into single Cloud Run instance
"""

import os
from flask import Flask, jsonify
from config.settings import Config
from shared.auth import require_api_key
from shared.error_handlers import register_error_handlers
from shared.logging_config import setup_logging

# Import service blueprints
from services.classifier import classifier_bp
from services.service1 import service1_bp
from services.service2 import service2_bp
# ... import all service blueprints

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Setup logging
    setup_logging(app)

    # Register error handlers
    register_error_handlers(app)

    # Register service blueprints
    app.register_blueprint(classifier_bp, url_prefix='/classifier')
    app.register_blueprint(service1_bp, url_prefix='/service1')
    app.register_blueprint(service2_bp, url_prefix='/service2')
    # ... register all service blueprints

    # Health check endpoint (shared across all services)
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({
            'status': 'healthy',
            'services': {
                'classifier': 'operational',
                'service1': 'operational',
                'service2': 'operational',
                # ... all services
            }
        })

    # Service discovery endpoint
    @app.route('/services', methods=['GET'])
    @require_api_key()
    def list_services():
        return jsonify({
            'services': [
                {'name': 'classifier', 'prefix': '/classifier', 'version': '1.0'},
                {'name': 'service1', 'prefix': '/service1', 'version': '1.0'},
                {'name': 'service2', 'prefix': '/service2', 'version': '1.0'},
                # ... all services
            ]
        })

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
```

#### 1.3 Create Shared Configuration

```python
# config/settings.py
"""
Shared configuration for all services
"""

import os

class Config:
    # GCP Settings
    PROJECT_ID = os.getenv('GCP_PROJECT_ID')
    REGION = os.getenv('GCP_REGION', 'us-central1')

    # Authentication
    API_KEYS_SECRET = os.getenv('API_KEYS_SECRET', 'unified-api-keys')

    # Service-specific settings loaded from environment
    # Each service can access via app.config

    # Rate limiting
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 100))

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
```

#### 1.4 Create Shared Authentication

```python
# shared/auth.py
"""
Unified authentication for all services
Supports service-specific API keys
"""

from functools import wraps
from flask import request, jsonify, current_app
from google.cloud import secretmanager
import json
import time

_api_keys_cache = None
_cache_timestamp = 0

def load_api_keys():
    global _api_keys_cache, _cache_timestamp

    if _api_keys_cache and (time.time() - _cache_timestamp) < 300:
        return _api_keys_cache

    client = secretmanager.SecretManagerServiceClient()
    project_id = current_app.config['PROJECT_ID']
    secret_name = current_app.config['API_KEYS_SECRET']

    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})

    _api_keys_cache = json.loads(response.payload.data.decode('UTF-8'))
    _cache_timestamp = time.time()

    return _api_keys_cache

def require_api_key(service=None):
    """
    Authentication decorator

    Args:
        service: If specified, checks service-specific permissions
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            api_key = request.headers.get('X-API-Key')

            if not api_key:
                return jsonify({
                    'error': 'Missing API key',
                    'message': 'Provide X-API-Key header'
                }), 401

            keys = load_api_keys()
            key_info = keys.get(api_key)

            if not key_info:
                return jsonify({'error': 'Invalid API key'}), 401

            # Check service-specific permissions
            if service:
                allowed_services = key_info.get('services', ['*'])
                if '*' not in allowed_services and service not in allowed_services:
                    return jsonify({
                        'error': 'Unauthorized',
                        'message': f'API key not authorized for {service}'
                    }), 403

            request.api_key_info = key_info
            return f(*args, **kwargs)

        return decorated_function
    return decorator
```

#### 1.5 Create Shared Error Handlers

```python
# shared/error_handlers.py
"""
Standardized error handling across all services
"""

from flask import jsonify
import logging
import time

logger = logging.getLogger(__name__)

def register_error_handlers(app):

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'status': 'error',
            'error_code': 'BAD_REQUEST',
            'message': str(error),
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'status': 'error',
            'error_code': 'UNAUTHORIZED',
            'message': 'Authentication required',
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }), 401

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'status': 'error',
            'error_code': 'NOT_FOUND',
            'message': 'Endpoint not found',
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {str(error)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error_code': 'INTERNAL_ERROR',
            'message': 'An internal error occurred',
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        logger.error(f"Unhandled exception: {str(error)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error_code': 'UNHANDLED_EXCEPTION',
            'message': 'An unexpected error occurred',
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }), 500
```

### Phase 2: Migrate Each Service (1-2 hours per service)

#### Service Migration Template

```python
# services/service1/__init__.py
"""
Service 1 Blueprint
Original functionality migrated to unified platform
"""

from flask import Blueprint

service1_bp = Blueprint('service1', __name__)

# Import routes
from . import routes
```

```python
# services/service1/routes.py
"""
Service 1 API Routes
"""

from flask import request, jsonify
from . import service1_bp
from shared.auth import require_api_key
from .logic import process_request

@service1_bp.route('/endpoint1', methods=['GET'])
@require_api_key(service='service1')
def endpoint1():
    """
    Original endpoint1 functionality
    """
    try:
        # Your original logic here
        result = process_request(request.args)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@service1_bp.route('/endpoint2', methods=['POST'])
@require_api_key(service='service1')
def endpoint2():
    """
    Original endpoint2 functionality
    """
    try:
        data = request.get_json()
        # Your original logic here
        result = process_request(data)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Phase 3: Deploy Unified Platform

#### 3.1 Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (add as needed for your services)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application
COPY . .

# Expose port
EXPOSE 8080

# Run with gunicorn
CMD exec gunicorn --bind :$PORT \
    --workers 1 \
    --threads 8 \
    --timeout 600 \
    --access-logfile - \
    --error-logfile - \
    main:app
```

#### 3.2 Deploy to Cloud Run

```bash
#!/bin/bash
# deploy-unified-platform.sh

export PROJECT_ID="your-project-id"
export REGION="us-central1"
export SERVICE_NAME="unified-api-platform"

# Build
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy with always-warm instance
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --region $REGION \
  --min-instances 1 \
  --max-instances 10 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 600s \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION"

# Get URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION --format='value(status.url)')

echo "Deployment complete!"
echo "Service URL: $SERVICE_URL"
echo ""
echo "Endpoints:"
echo "  Health: $SERVICE_URL/health"
echo "  Services: $SERVICE_URL/services"
echo "  Classifier: $SERVICE_URL/classifier/*"
echo "  Service 1: $SERVICE_URL/service1/*"
```

---

## Migration Strategy

### Phased Rollout (Recommended)

#### Week 1: Setup & First Service
- [ ] Create unified platform structure
- [ ] Set up shared utilities
- [ ] Migrate IBRS Classifier (most complex)
- [ ] Deploy to Cloud Run
- [ ] Test thoroughly
- [ ] Monitor for issues

#### Week 2-3: Migrate Remaining Services
- [ ] Migrate 3-4 services per week
- [ ] Test each after migration
- [ ] Update documentation
- [ ] Monitor performance

**Per Service: ~1-2 hours each**

#### Week 4: Cutover & Cleanup
- [ ] Update all client applications
- [ ] Switch DNS/routing
- [ ] Monitor consolidated platform
- [ ] Delete old services
- [ ] Celebrate savings! 🎉

### Service Prioritization

**Migrate in this order:**

1. **Simplest service first** (build confidence)
2. **IBRS Classifier** (most complex, template for others)
3. **High-value services** (most used)
4. **Remaining services** (batch migration)

---

## Operational Benefits

### Single Pane of Glass

**Before (13 services):**
```
Where do I check logs?
  → 13 different log streams
  → 13 different metrics
  → 13 different deployments

How do I update authentication?
  → Change in 13 places
  → Test 13 times
  → Deploy 13 times
```

**After (Unified platform):**
```
Where do I check logs?
  → One log stream, filter by service

How do I update authentication?
  → Change shared/auth.py once
  → Test once
  → Deploy once
  → All services updated
```

### Consistency Across Services

| Aspect | Before | After |
|--------|--------|-------|
| **Error Format** | Inconsistent | Standardized |
| **Logging** | Different patterns | Unified |
| **Auth** | 13 implementations | 1 implementation |
| **Monitoring** | Fragmented | Centralized |
| **Documentation** | 13 separate docs | 1 comprehensive doc |

### Developer Experience

```
# Before: Deploy changes to Service 5
cd service5-repo
git pull
gcloud functions deploy service5 --region us-central1 ...
# Wait 3-5 minutes
# Test
# Repeat for each service

# After: Deploy changes to any service
cd unified-api-platform
git pull
gcloud run deploy unified-api-platform ...
# Wait 2-3 minutes
# All services updated simultaneously
```

---

## Risk Mitigation

### Risk: All services share fate

**Mitigation:**
- Comprehensive error handling (errors don't crash container)
- Health checks for each service module
- Graceful degradation (one service failure doesn't affect others)
- Automatic restart on crash (Cloud Run feature)
- Consider blue/green deployments for zero-downtime updates

### Risk: Larger container image

**Mitigation:**
- Use multi-stage Docker builds
- Share dependencies between services
- Remove unused dependencies
- Container size ~500MB-1GB is fine for Cloud Run

### Risk: Migration complexity

**Mitigation:**
- Migrate one service at a time
- Keep old services running during migration
- Use feature flags for gradual rollout
- Maintain rollback capability

### Risk: Performance degradation

**Mitigation:**
- 1GB memory should handle all 13 low-volume services
- Can increase to 2GB if needed (+$10/month still cheaper)
- Monitor per-service metrics
- Optimize as needed

---

## Success Metrics

### Post-Migration Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Monthly Cost | < $20 | GCP billing |
| Cold Start Rate | 0% | Cloud Run metrics |
| Response Time (p95) | < 15s | Cloud Run latency |
| Deployment Time | < 5 min | CI/CD pipeline |
| Error Rate | < 1% | Logging analysis |
| Uptime | > 99.5% | Monitoring |

### 90-Day Success Criteria

- [ ] All 13 services migrated
- [ ] Monthly cost reduced by 70%+
- [ ] Zero cold start issues reported
- [ ] Single deployment process working
- [ ] Team comfortable with new architecture
- [ ] Documentation complete
- [ ] Old services deleted

---

## Conclusion

### The Numbers

```
Current State:
  • 13 separate services
  • $90/month
  • 13 deployments
  • 95% cold starts
  • High operational overhead

Consolidated State:
  • 13 services, 1 platform
  • $18/month (80% savings)
  • 1 deployment
  • 0% cold starts
  • Minimal operational overhead

ROI: Payback in 2.6 months
```

### Recommendation

**✅ Strongly recommend consolidation**

This is a textbook case for consolidation:
- All services are low-volume
- All services are similar (APIs)
- High opportunity for code reuse
- Massive cost savings
- Dramatic operational simplification
- Better user experience (no cold starts)

**Next Steps:**
1. Review this strategy with team
2. Start with Phase 1 (setup, 2 hours)
3. Migrate one simple service as proof of concept
4. Migrate remaining services over 3-4 weeks
5. Enjoy 80% cost reduction and simpler operations!

---

**Total Migration Effort:** ~20-25 hours
**Annual Savings:** ~$876/year
**Payback Period:** 2.6 months
**Long-term Benefit:** Massive 💰🎉

