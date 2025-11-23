"""
Asynchronous classification worker
Processes jobs from Cloud Tasks queue
"""

import time
import sys
import os
from flask import Flask, request, jsonify
from google.cloud import firestore, storage
from datetime import datetime

# Add parent directory to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import config
from shared.document_parser import DocumentParser
from shared.tag_cache import load_tag_cache
from shared.gemini_client import GeminiClassifier

app = Flask(__name__)

# Initialize clients
db = firestore.Client(project=config.GCP_PROJECT_ID, database=config.FIRESTORE_DATABASE)
storage_client = storage.Client(project=config.GCP_PROJECT_ID)


@app.route('/classify-worker', methods=['POST'])
def classify_worker():
    """
    Process async classification job

    Triggered by Cloud Tasks with job_id in request body
    """
    start_time = time.time()

    try:
        # Extract job ID from request
        data = request.get_json()
        if not data or 'job_id' not in data:
            return jsonify({'error': 'Missing job_id'}), 400

        job_id = data['job_id']
        print(f"Processing job: {job_id}")

        # Get job from Firestore
        job_ref = db.collection(config.JOBS_COLLECTION).document(job_id)
        job_doc = job_ref.get()

        if not job_doc.exists:
            print(f"Job not found: {job_id}")
            return jsonify({'error': 'Job not found'}), 404

        job_data = job_doc.to_dict()

        # Update status to processing
        job_ref.update({
            'status': 'processing',
            'updated_at': datetime.utcnow(),
            'progress': {
                'stage': 'downloading',
                'percent_complete': 10
            }
        })

        # Download document from Cloud Storage
        document_info = job_data['document']
        storage_ref = document_info['storage_ref']

        # Parse storage ref (gs://bucket/path)
        bucket_name = storage_ref.split('/')[2]
        blob_path = '/'.join(storage_ref.split('/')[3:])

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        file_content = blob.download_as_bytes()

        # Update progress
        job_ref.update({
            'updated_at': datetime.utcnow(),
            'progress': {
                'stage': 'text_extraction',
                'percent_complete': 30
            }
        })

        # Extract text
        try:
            parser = DocumentParser()
            document_text = parser.extract_text(
                file_content,
                document_info['mime_type'],
                document_info['filename']
            )

            is_valid, error_msg = parser.validate_extracted_text(document_text)
            if not is_valid:
                _fail_job(job_ref, 'EXTRACTION_NO_TEXT', error_msg)
                return jsonify({'status': 'failed', 'error': error_msg}), 200

        except Exception as e:
            _fail_job(job_ref, 'EXTRACTION_FAILED', str(e))
            return jsonify({'status': 'failed', 'error': str(e)}), 200

        # Update progress
        job_ref.update({
            'updated_at': datetime.utcnow(),
            'progress': {
                'stage': 'classification',
                'percent_complete': 50
            }
        })

        # Load tag cache
        try:
            tag_cache = load_tag_cache()
        except Exception as e:
            _fail_job(job_ref, 'TAG_CACHE_LOAD_FAILED', str(e))
            return jsonify({'status': 'failed', 'error': str(e)}), 200

        # Classify document
        try:
            classifier = GeminiClassifier()
            classification = classifier.classify_document(document_text, tag_cache)

            is_valid, errors = classifier.validate_classification_rules(classification)
            if not is_valid:
                _fail_job(job_ref, 'VALIDATION_FAILED', ', '.join(errors))
                return jsonify({'status': 'failed', 'errors': errors}), 200

        except Exception as e:
            _fail_job(job_ref, 'CLASSIFICATION_FAILED', str(e))
            return jsonify({'status': 'failed', 'error': str(e)}), 200

        # Update progress
        job_ref.update({
            'updated_at': datetime.utcnow(),
            'progress': {
                'stage': 'completed',
                'percent_complete': 100
            }
        })

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Mark job as completed
        result = {
            'status': 'success',
            'document': {
                'filename': document_info['filename'],
                'size_bytes': document_info['size_bytes'],
                'mime_type': document_info['mime_type'],
                'text_length': len(document_text)
            },
            'classification': classification,
            'model_used': config.VERTEX_AI_MODEL
        }

        job_ref.update({
            'status': 'completed',
            'completed_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'result': result,
            'processing_time_ms': processing_time_ms
        })

        # Delete temporary document from storage
        try:
            blob.delete()
        except Exception as e:
            print(f"Failed to delete temporary file: {str(e)}")

        print(f"Job {job_id} completed successfully in {processing_time_ms}ms")

        return jsonify({
            'status': 'completed',
            'job_id': job_id,
            'processing_time_ms': processing_time_ms
        }), 200

    except Exception as e:
        print(f"Worker error: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


def _fail_job(job_ref, error_code, error_message):
    """
    Mark job as failed

    Args:
        job_ref: Firestore document reference
        error_code: Error code string
        error_message: Error message
    """
    job_ref.update({
        'status': 'failed',
        'failed_at': datetime.utcnow(),
        'updated_at': datetime.utcnow(),
        'error': {
            'error_code': error_code,
            'message': error_message
        }
    })


# For local testing
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8082, debug=True)
