"""
Synchronous document classification endpoint
POST /classify
"""

import time
import sys
import os
from flask import Flask, request, jsonify

# Add parent directory to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import config
from shared.auth import require_api_key
from shared.document_parser import DocumentParser
from shared.tag_cache import load_tag_cache
from shared.gemini_client import GeminiClassifier

app = Flask(__name__)


@app.route('/classify', methods=['POST'])
@require_api_key(admin_only=False)
def classify():
    """
    Classify document synchronously (for documents < 5MB)

    Accepts multipart/form-data or JSON with base64-encoded content
    Returns classification results immediately
    """
    start_time = time.time()

    try:
        # Extract document from request
        file_content, filename, mime_type, file_size = _extract_document_from_request()

        # Validate size (must be under 5MB for sync processing)
        if file_size > config.MAX_SYNC_SIZE_BYTES:
            return jsonify({
                'status': 'error',
                'error_code': 'DOCUMENT_TOO_LARGE',
                'message': 'Document exceeds 5MB limit for synchronous processing. Use /classify/async endpoint.',
                'details': {
                    'max_size_bytes': config.MAX_SYNC_SIZE_BYTES,
                    'received_size_bytes': file_size,
                    'recommendation': 'Use POST /classify/async for this document'
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

        # Extract text from document
        try:
            parser = DocumentParser()
            document_text = parser.extract_text(file_content, mime_type, filename)

            # Validate extracted text
            is_valid, error_msg = parser.validate_extracted_text(document_text)
            if not is_valid:
                return jsonify({
                    'status': 'error',
                    'error_code': 'TEXT_TOO_SHORT',
                    'message': error_msg,
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }), 422

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error_code': 'EXTRACTION_FAILED',
                'message': 'Failed to extract text from document',
                'details': {
                    'error': str(e)
                },
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), 500

        # Load tag cache
        try:
            tag_cache = load_tag_cache()
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error_code': 'TAG_CACHE_LOAD_FAILED',
                'message': 'Failed to load tag cache',
                'details': {
                    'error': str(e)
                },
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), 500

        # Classify document using Gemini
        try:
            classifier = GeminiClassifier()
            classification = classifier.classify_document(document_text, tag_cache)

            # Validate classification meets rules
            is_valid, errors = classifier.validate_classification_rules(classification)
            if not is_valid:
                return jsonify({
                    'status': 'error',
                    'error_code': 'VALIDATION_FAILED',
                    'message': 'Classification validation failed',
                    'details': {
                        'errors': errors
                    },
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }), 500

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error_code': 'CLASSIFICATION_FAILED',
                'message': 'Failed to classify document',
                'details': {
                    'error': str(e)
                },
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), 500

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Return successful classification
        return jsonify({
            'status': 'success',
            'document': {
                'filename': filename,
                'size_bytes': file_size,
                'mime_type': mime_type,
                'text_length': len(document_text)
            },
            'classification': classification,
            'processing_time_ms': processing_time_ms,
            'model_used': config.VERTEX_AI_MODEL
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error_code': 'INTERNAL_ERROR',
            'message': 'Unexpected error occurred',
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

        import base64
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


# For local testing
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
