# IBRS Document Auto-Classifier

AI-powered document classification system using Google Gemini on GCP. Automatically classifies documents against 240+ tags from Zoho CRM taxonomy.

## Overview

The IBRS Document Auto-Classifier is a stateless, serverless API system that:
- Accepts documents in multiple formats (PDF, Word, PowerPoint, images, text)
- Extracts text using OCR when needed
- Classifies content using Google Gemini 1.5 Pro AI
- Returns structured tags based on IBRS taxonomy
- Syncs tags from Zoho CRM automatically

## Features

- **Multi-Format Support**: PDF, DOCX, PPTX, TXT, JPG, PNG, GIF
- **AI-Powered Classification**: Google Gemini via Vertex AI
- **Flexible Processing**: Synchronous (< 5MB) and asynchronous (5-50MB)
- **Tag Management**: Automatic sync from Zoho CRM every 6 hours
- **Stateless Architecture**: Cloud Functions that scale automatically
- **Secure**: API key authentication, Secret Manager integration
- **Tag Rules**: Enforces exactly 1 Horizon + 1 Practice, plus optional tags

## Tag Types

| Type | Cardinality | Description |
|------|-------------|-------------|
| Horizon | Exactly 1 | Strategic timeframe (Solve, Plan, Explore) |
| Practice | Exactly 1 | Business practice area |
| Stream | 0+ | Content stream/category |
| Role | 0+ | Target audience role |
| Vendor | 0+ | Company/vendor mentioned |
| Product | 0+ | Specific product/service |
| Topic | 0+ | Subject matter |

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ├── POST /classify (sync)
       ├── POST /classify/async
       ├── GET /classify/status/{id}
       ├── POST /admin/sync-tags
       └── GET /health
       │
┌──────▼───────────────────────────────────┐
│      Cloud Functions (Python 3.11)       │
├──────────────────────────────────────────┤
│ • classify         (sync processing)     │
│ • classify-async   (job submission)      │
│ • classify-worker  (async processing)    │
│ • sync-tags        (Zoho sync)           │
│ • health           (health check)        │
└──────┬───────────────────────────────────┘
       │
       ├── Vertex AI (Gemini 1.5 Pro)
       ├── Cloud Storage (tag cache)
       ├── Firestore (job tracking)
       ├── Cloud Tasks (async queue)
       └── Zoho CRM (tag source)
```

## Project Structure

```
IBRSAutoclassifier/
├── Software Specifications.md   # Complete API specification
├── Admin Setup Guide.md         # Deployment instructions
├── README.md
├── requirements.txt
├── .gitignore
│
├── functions/
│   ├── classify/               # Sync classification endpoint
│   │   └── main.py
│   ├── classify_async/         # Async job management
│   │   └── main.py
│   ├── classify_worker/        # Background worker
│   │   └── main.py
│   ├── sync_tags/              # Tag sync from Zoho
│   │   └── main.py
│   ├── health/                 # Health check
│   │   └── main.py
│   └── shared/                 # Shared utilities
│       ├── __init__.py
│       ├── config.py           # Configuration
│       ├── auth.py             # API key auth
│       ├── document_parser.py  # Text extraction
│       ├── gemini_client.py    # AI classification
│       ├── tag_cache.py        # Tag management
│       └── zoho_client.py      # Zoho CRM integration
│
├── tests/                      # Unit tests
├── deployment/                 # Terraform/scripts
└── docs/                       # Additional documentation
```

## Quick Start

### Prerequisites

- Google Cloud Platform account with billing enabled
- gcloud CLI installed
- Python 3.11+
- Zoho CRM admin access

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/IBRSAutoclassifier.git
cd IBRSAutoclassifier
```

2. **Follow the Admin Setup Guide**

See [Admin Setup Guide.md](Admin%20Setup%20Guide.md) for complete deployment instructions.

Quick summary:
```bash
# Set up GCP project
export PROJECT_ID="ibrs-classifier"
gcloud config set project $PROJECT_ID

# Enable APIs
gcloud services enable cloudfunctions.googleapis.com aiplatform.googleapis.com

# Deploy functions
gcloud functions deploy classify --gen2 --runtime=python311 ...

# See full guide for complete steps
```

## API Usage

### Classify Document (Synchronous)

```bash
curl -X POST "https://REGION-PROJECT.cloudfunctions.net/classify" \
  -H "X-API-Key: your-api-key" \
  -F "file=@document.pdf"
```

**Response:**
```json
{
  "status": "success",
  "classification": {
    "horizon": {"name": "Solve", "confidence": 0.92},
    "practice": {"name": "Cybersecurity", "confidence": 0.88},
    "topics": [{"name": "Zero Trust", "confidence": 0.76}]
  }
}
```

### Classify Document (Asynchronous)

```bash
# Submit job
curl -X POST "https://REGION-PROJECT.cloudfunctions.net/classify/async" \
  -H "X-API-Key: your-api-key" \
  -F "file=@large_document.pdf"

# Response: {"job_id": "uuid", "status_url": "/classify/status/uuid"}

# Check status
curl -X GET "https://REGION-PROJECT.cloudfunctions.net/classify/status/uuid" \
  -H "X-API-Key: your-api-key"
```

### Sync Tags from Zoho

```bash
curl -X POST "https://REGION-PROJECT.cloudfunctions.net/admin/sync-tags" \
  -H "X-API-Key: admin-api-key"
```

### Health Check

```bash
curl "https://REGION-PROJECT.cloudfunctions.net/health"
```

## Documentation

- **[Software Specifications.md](Software%20Specifications.md)** - Complete API specification with all endpoints, data models, and error codes
- **[Admin Setup Guide.md](Admin%20Setup%20Guide.md)** - Step-by-step deployment and configuration guide

## Cost Estimates

For 100 documents/day (~3,000/month):

| Service | Monthly Cost |
|---------|-------------|
| Cloud Functions | $0.50 |
| Vertex AI (Gemini) | $10.50 |
| Cloud Storage | $0.05 |
| Firestore | $0.10 |
| Cloud Tasks | $0.01 |
| Cloud Scheduler | $0.40 |
| Egress | $1.20 |
| **Total** | **~$12.76/month** |

Costs scale linearly with volume.

## Security

- API key authentication for all protected endpoints
- Secrets stored in GCP Secret Manager
- HTTPS only (TLS 1.2+)
- IAM-based service account permissions
- No persistent document storage (stateless)
- Rate limiting (60 requests/minute per key)

## Monitoring

The system includes:
- Cloud Logging for all requests
- Cloud Monitoring dashboards
- Alerts for errors, latency, and quota warnings
- Health check endpoint at `/health`

## Technology Stack

- **Runtime**: Python 3.11
- **Cloud Platform**: Google Cloud Platform
- **Compute**: Cloud Functions (Gen 2)
- **AI**: Vertex AI (Gemini 1.5 Pro)
- **Storage**: Cloud Storage, Firestore
- **Queue**: Cloud Tasks
- **Scheduler**: Cloud Scheduler
- **Secrets**: Secret Manager
- **Integration**: Zoho CRM API

## Python Libraries

- `google-cloud-aiplatform` - Vertex AI integration
- `google-cloud-storage` - Cloud Storage
- `google-cloud-firestore` - Firestore
- `google-cloud-tasks` - Cloud Tasks
- `google-cloud-secret-manager` - Secret Manager
- `PyPDF2`, `pdfplumber` - PDF processing
- `python-docx` - Word documents
- `python-pptx` - PowerPoint
- `Pillow`, `pytesseract` - OCR
- `requests` - Zoho API
- `flask` - HTTP framework

## Troubleshooting

See [Admin Setup Guide.md - Section 15: Troubleshooting](Admin%20Setup%20Guide.md#15-troubleshooting) for common issues and solutions.

**Common Issues:**
- Permission errors → Check service account roles
- Zoho auth failures → Regenerate refresh token
- High costs → Review Vertex AI usage, consider Gemini Flash
- Low quality results → Check tag cache freshness

## Development

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run function locally
cd functions/classify
python main.py
```

### Running Tests

```bash
pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

Proprietary - IBRS (Information and Business Research Services)

## Support

For issues and questions:
- **Email**: support@ibrs.com
- **Documentation**: See `Software Specifications.md` and `Admin Setup Guide.md`

## Version History

- **1.0.0** (January 2025) - Initial release
  - Multi-format document support
  - Gemini AI classification
  - Zoho CRM integration
  - Async processing
  - Tag management

---

**Built with ❤️ for IBRS using Google Cloud Platform and AI**
