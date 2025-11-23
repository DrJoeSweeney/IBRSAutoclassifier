"""
Health check endpoint
GET /health
"""

import time
import sys
import os
from flask import Flask, jsonify
from google.cloud import firestore, storage
import vertexai

# Add parent directory to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import config
from shared.tag_cache import load_tag_cache, get_cache_age_hours

app = Flask(__name__)

# Track function start time
_start_time = time.time()


@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint

    No authentication required
    Returns health status of all system dependencies
    """
    try:
        health_status = {
            'status': 'healthy',
            'version': '1.0.0',
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'services': {},
            'uptime_seconds': int(time.time() - _start_time)
        }

        overall_healthy = True

        # Check Vertex AI
        try:
            vertexai.init(project=config.GCP_PROJECT_ID, location=config.VERTEX_AI_LOCATION)
            health_status['services']['vertex_ai'] = {
                'status': 'operational',
                'model': config.VERTEX_AI_MODEL,
                'region': config.VERTEX_AI_LOCATION
            }
        except Exception as e:
            health_status['services']['vertex_ai'] = {
                'status': 'error',
                'error': str(e)
            }
            overall_healthy = False

        # Check Tag Cache
        try:
            tag_cache = load_tag_cache()
            cache_age = get_cache_age_hours()

            tag_status = {
                'status': 'operational',
                'tags_count': tag_cache.get_tags_count(),
                'last_sync': tag_cache.sync_timestamp
            }

            if cache_age:
                tag_status['age_hours'] = round(cache_age, 2)

                # Warn if cache is stale (> 24 hours)
                if cache_age > 24:
                    tag_status['status'] = 'warning'
                    tag_status['warning'] = f'Cache is stale ({round(cache_age, 1)} hours old)'
                    if cache_age > 48:
                        overall_healthy = False

            health_status['services']['tag_cache'] = tag_status

        except Exception as e:
            health_status['services']['tag_cache'] = {
                'status': 'error',
                'error': str(e)
            }
            overall_healthy = False

        # Check Firestore
        try:
            db = firestore.Client(project=config.GCP_PROJECT_ID, database=config.FIRESTORE_DATABASE)
            # Try to count active jobs
            jobs_ref = db.collection(config.JOBS_COLLECTION)
            active_count = len(list(jobs_ref.where('status', 'in', ['pending', 'processing']).limit(100).stream()))

            health_status['services']['firestore'] = {
                'status': 'operational',
                'active_jobs': active_count
            }
        except Exception as e:
            health_status['services']['firestore'] = {
                'status': 'error',
                'error': str(e)
            }
            overall_healthy = False

        # Check Cloud Storage
        try:
            storage_client = storage.Client(project=config.GCP_PROJECT_ID)
            bucket = storage_client.bucket(config.TAG_CACHE_BUCKET)
            # Just check if bucket is accessible
            bucket.exists()

            health_status['services']['cloud_storage'] = {
                'status': 'operational'
            }
        except Exception as e:
            health_status['services']['cloud_storage'] = {
                'status': 'error',
                'error': str(e)
            }
            overall_healthy = False

        # Set overall status
        if not overall_healthy:
            health_status['status'] = 'degraded'
            return jsonify(health_status), 503

        return jsonify(health_status), 200

    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }), 503


# For local testing
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8084, debug=True)
