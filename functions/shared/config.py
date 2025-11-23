"""
Configuration module for IBRS Document Auto-Classifier
Loads configuration from environment variables
"""

import os

# GCP Configuration
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID', '')
GCP_REGION = os.getenv('GCP_REGION', 'us-central1')

# Cloud Storage
TAG_CACHE_BUCKET = os.getenv('TAG_CACHE_BUCKET', f'{GCP_PROJECT_ID}-ibrs-tags')
TAG_CACHE_BLOB_NAME = 'tags/current.json'
TAG_CACHE_BACKUP_PREFIX = 'tags/backups/'

# Firestore
FIRESTORE_DATABASE = os.getenv('FIRESTORE_DATABASE', '(default)')
JOBS_COLLECTION = 'classification_jobs'

# Vertex AI
VERTEX_AI_LOCATION = os.getenv('VERTEX_AI_LOCATION', 'us-central1')
VERTEX_AI_MODEL = os.getenv('VERTEX_AI_MODEL', 'gemini-1.5-pro')

# Document Processing
MAX_SYNC_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
MAX_ASYNC_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
MIN_TEXT_LENGTH = 50

# Classification
CLASSIFICATION_TEMPERATURE = 0.1
CLASSIFICATION_MAX_RETRIES = 3
CLASSIFICATION_TIMEOUT_SECONDS = 45

# Authentication
API_KEYS_SECRET_NAME = os.getenv('API_KEYS_SECRET_NAME', 'ibrs-classifier-api-keys')
ADMIN_KEYS_SECRET_NAME = os.getenv('ADMIN_KEYS_SECRET_NAME', 'ibrs-classifier-admin-keys')
RATE_LIMIT_PER_MINUTE = 60

# Zoho CRM
ZOHO_CLIENT_ID = os.getenv('ZOHO_CLIENT_ID', '')
ZOHO_CLIENT_SECRET_NAME = os.getenv('ZOHO_CLIENT_SECRET_NAME', 'zoho-client-secret')
ZOHO_REFRESH_TOKEN_NAME = os.getenv('ZOHO_REFRESH_TOKEN_NAME', 'zoho-refresh-token')
ZOHO_API_BASE_URL = os.getenv('ZOHO_API_BASE_URL', 'https://www.zohoapis.com')
ZOHO_TAGS_MODULE = 'IBRS_Tags'

# Job Processing
JOB_TTL_HOURS = 24
ASYNC_WORKER_QUEUE = os.getenv('ASYNC_WORKER_QUEUE', 'ibrs-classification-queue')
ASYNC_WORKER_LOCATION = os.getenv('ASYNC_WORKER_LOCATION', 'us-central1')

# Supported MIME Types
SUPPORTED_MIME_TYPES = {
    'application/pdf': 'pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
    'text/plain': 'txt',
    'image/jpeg': 'image',
    'image/png': 'image',
    'image/gif': 'image'
}

# Tag Types
TAG_TYPES = {
    'Horizon': {'cardinality': 'exactly_one', 'values': ['Solve', 'Plan', 'Explore']},
    'Practice': {'cardinality': 'exactly_one', 'values': None},
    'Stream': {'cardinality': 'zero_or_more', 'values': None},
    'Role': {'cardinality': 'zero_or_more', 'values': None},
    'Vendor': {'cardinality': 'zero_or_more', 'values': None},
    'Product': {'cardinality': 'zero_or_more', 'values': None},
    'Topic': {'cardinality': 'zero_or_more', 'values': None}
}
