"""
Asynchronous document classification endpoint
POST /classify/async - Submit job
GET /classify/status/{job_id} - Check status
"""

import time
import sys
import os
import uuid
import base64
from flask import Flask, request, jsonify
from google.cloud import firestore, storage, tasks_v2
from datetime import datetime, timedelta

# Add parent directory to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import config
from shared.auth import require_api_key, get_api_key_hash

app = Flask(__name__)

# Initialize clients
db = firestore.Client(project=config.GCP_PROJECT_ID, database=config.FIRESTORE_DATABASE)
storage_client = storage.Client(project=config.GCP_PROJECT_ID)
tasks_client = tasks_v2.CloudTasksClient()


@app.route('/classify/async', methods=['POST'])
@require_api_key(admin_only=False)
def classify_async():
    """
    Submit document for asynchronous classification (for documents 5MB - 50MB)

    Returns job ID immediately for status polling
    """
    try:
        # Extract document from request
        file_content, filename, mime_type, file_size = _extract_document_from_request()

        # Validate size (5MB - 50MB for async processing)
        if file_size < config.MAX_SYNC_SIZE_BYTES:
            return jsonify({
                'status': 'error',
                'error_code': 'DOCUMENT_TOO_SMALL',
                'message': 'Document is under 5MB. Use /classify endpoint for synchronous processing.',
                'details': {
                    'min_size_bytes': config.MAX_SYNC_SIZE_BYTES,
                    'received_size_bytes': file_size
                },
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), 400

        if file_size > config.MAX_ASYNC_SIZE_BYTES:
            return jsonify({
                'status': 'error',
                'error_code': 'DOCUMENT_TOO_LARGE',
                'message': 'Document exceeds maximum size of 50MB',
                'details': {
                    'max_size_bytes': config.MAX_ASYNC_SIZE_BYTES,
                    'received_size_bytes': file_size
                },
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), 413

        # Validate MIME type
        if mime_type not in config.SUPPORTED_MIME_TYPES:
            return jsonify({
                'status': 'error',
                'error_code': 'UNSUPPORTED_FORMAT',
                'message': f'Unsupported file format: {mime_type}',
                'details': {
                    'supported_formats': list(config.SUPPORTED_MIME_TYPES.keys())
                },
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), 400

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Store document temporarily in Cloud Storage
        bucket = storage_client.bucket(f'{config.GCP_PROJECT_ID}-ibrs-temp')
        blob_name = f'jobs/{job_id}/{filename}'
        blob = bucket.blob(blob_name)
        blob.upload_from_string(file_content, content_type=mime_type)

        # Create job document in Firestore
        now = datetime.utcnow()
        ttl_expires = now + timedelta(hours=config.JOB_TTL_HOURS)

        job_doc = {
            'job_id': job_id,
            'status': 'pending',
            'created_at': now,
            'updated_at': now,
            'document': {
                'filename': filename,
                'size_bytes': file_size,
                'mime_type': mime_type,
                'storage_ref': f'gs://{bucket.name}/{blob_name}'
            },
            'api_key_hash': get_api_key_hash(),
            'result': None,
            'ttl_expires_at': ttl_expires
        }

        db.collection(config.JOBS_COLLECTION).document(job_id).set(job_doc)

        # Create Cloud Task to trigger worker
        _create_worker_task(job_id)

        # Estimate completion time (rough: 1MB = 5 seconds)
        estimated_seconds = min(60, max(10, int(file_size / (1024 * 1024) * 5)))

        return jsonify({
            'status': 'accepted',
            'job_id': job_id,
            'status_url': f'/classify/status/{job_id}',
            'estimated_completion_seconds': estimated_seconds,
            'created_at': now.strftime('%Y-%m-%dT%H:%M:%SZ')
        }), 202

    except ValueError as e:
        return jsonify({
            'status': 'error',
            'error_code': 'INVALID_REQUEST',
            'message': str(e),
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }), 400

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error_code': 'JOB_CREATION_FAILED',
            'message': 'Failed to create classification job',
            'details': {
                'error': str(e)
            },
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }), 500


@app.route('/classify/status/<job_id>', methods=['GET'])
@require_api_key(admin_only=False)
def classify_status(job_id):
    """
    Check status of asynchronous classification job

    Args:
        job_id: UUID of the job
    """
    try:
        # Retrieve job from Firestore
        job_ref = db.collection(config.JOBS_COLLECTION).document(job_id)
        job_doc = job_ref.get()

        if not job_doc.exists:
            return jsonify({
                'status': 'error',
                'error_code': 'JOB_NOT_FOUND',
                'message': 'Job not found or has expired',
                'details': {
                    'job_id': job_id,
                    'note': f'Jobs expire {config.JOB_TTL_HOURS} hours after creation'
                },
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), 404

        job_data = job_doc.to_dict()

        # Verify API key ownership (compare hashes)
        request_key_hash = get_api_key_hash()
        if request_key_hash != job_data.get('api_key_hash'):
            return jsonify({
                'status': 'error',
                'error_code': 'UNAUTHORIZED',
                'message': 'This job belongs to a different API key',
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), 403

        # Build response based on status
        response = {
            'job_id': job_id,
            'status': job_data['status'],
            'created_at': job_data['created_at'].strftime('%Y-%m-%dT%H:%M:%SZ'),
            'updated_at': job_data['updated_at'].strftime('%Y-%m-%dT%H:%M:%SZ')
        }

        if job_data['status'] == 'pending':
            response['message'] = 'Job is queued for processing'

        elif job_data['status'] == 'processing':
            progress = job_data.get('progress', {})
            response['progress'] = progress

        elif job_data['status'] == 'completed':
            response['completed_at'] = job_data.get('completed_at').strftime('%Y-%m-%dT%H:%M:%SZ')
            response['result'] = job_data.get('result')
            if 'processing_time_ms' in job_data:
                response['processing_time_ms'] = job_data['processing_time_ms']

        elif job_data['status'] == 'failed':
            response['failed_at'] = job_data.get('failed_at').strftime('%Y-%m-%dT%H:%M:%SZ')
            response['error'] = job_data.get('error')

        return jsonify(response), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error_code': 'INTERNAL_ERROR',
            'message': 'Failed to retrieve job status',
            'details': {
                'error': str(e)
            },
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }), 500


def _extract_document_from_request():
    """
    Extract document from request (multipart or JSON)

    Returns:
        tuple: (file_content: bytes, filename: str, mime_type: str, file_size: int)
    """
    # Check if multipart upload
    if request.files:
        file = request.files.get('file')
        if not file:
            raise ValueError("No file provided in upload")

        file_content = file.read()
        filename = file.filename
        mime_type = file.content_type or 'application/octet-stream'
        file_size = len(file_content)

        return file_content, filename, mime_type, file_size

    # Check if JSON with base64
    elif request.is_json:
        data = request.get_json()

        if 'content' not in data:
            raise ValueError("Missing 'content' field in JSON")
        if 'filename' not in data:
            raise ValueError("Missing 'filename' field in JSON")
        if 'mime_type' not in data:
            raise ValueError("Missing 'mime_type' field in JSON")

        try:
            file_content = base64.b64decode(data['content'])
        except Exception as e:
            raise ValueError(f"Invalid base64 encoding: {str(e)}")

        filename = data['filename']
        mime_type = data['mime_type']
        file_size = len(file_content)

        return file_content, filename, mime_type, file_size

    else:
        raise ValueError("Request must be multipart/form-data or application/json")


def _create_worker_task(job_id):
    """
    Create Cloud Task to trigger async worker

    Args:
        job_id: Job UUID
    """
    parent = tasks_client.queue_path(
        config.GCP_PROJECT_ID,
        config.ASYNC_WORKER_LOCATION,
        config.ASYNC_WORKER_QUEUE
    )

    # Worker function URL (will be deployed separately)
    worker_url = f'https://{config.ASYNC_WORKER_LOCATION}-{config.GCP_PROJECT_ID}.cloudfunctions.net/classify-worker'

    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': worker_url,
            'headers': {'Content-Type': 'application/json'},
            'body': f'{{"job_id": "{job_id}"}}'.encode()
        }
    }

    tasks_client.create_task(request={'parent': parent, 'task': task})


# For local testing
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8081, debug=True)
