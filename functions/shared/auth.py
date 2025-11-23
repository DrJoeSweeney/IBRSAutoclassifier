"""
Authentication module for API key validation
"""

import json
import hashlib
import time
from functools import wraps
from flask import request, jsonify
from google.cloud import secretmanager
from . import config

# Global cache for API keys (refreshed periodically)
_api_keys_cache = None
_admin_keys_cache = None
_cache_timestamp = 0
_cache_ttl_seconds = 300  # 5 minutes

# Rate limiting (simple in-memory, production should use Firestore/Memorystore)
_rate_limit_tracker = {}


def _get_secret(secret_name):
    """Retrieve secret from Secret Manager"""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{config.GCP_PROJECT_ID}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8')


def _load_api_keys():
    """Load API keys from Secret Manager"""
    global _api_keys_cache, _admin_keys_cache, _cache_timestamp

    current_time = time.time()
    if _api_keys_cache and (current_time - _cache_timestamp) < _cache_ttl_seconds:
        return

    try:
        # Load standard API keys
        keys_json = _get_secret(config.API_KEYS_SECRET_NAME)
        keys_data = json.loads(keys_json)
        _api_keys_cache = {
            key['key_value']: key
            for key in keys_data.get('keys', [])
            if key.get('active', True)
        }

        # Load admin API keys
        admin_json = _get_secret(config.ADMIN_KEYS_SECRET_NAME)
        admin_data = json.loads(admin_json)
        _admin_keys_cache = {
            key['key_value']: key
            for key in admin_data.get('admin_keys', [])
            if key.get('active', True)
        }

        _cache_timestamp = current_time
    except Exception as e:
        print(f"Error loading API keys: {str(e)}")
        raise


def _check_rate_limit(key_id):
    """
    Check if request exceeds rate limit
    Simple in-memory implementation - production should use Firestore or Memorystore
    """
    current_time = time.time()
    current_minute = int(current_time / 60)

    if key_id not in _rate_limit_tracker:
        _rate_limit_tracker[key_id] = {'minute': current_minute, 'count': 0}

    tracker = _rate_limit_tracker[key_id]

    # Reset counter if we're in a new minute
    if tracker['minute'] < current_minute:
        tracker['minute'] = current_minute
        tracker['count'] = 0

    tracker['count'] += 1

    # Check if over limit
    if tracker['count'] > config.RATE_LIMIT_PER_MINUTE:
        return False

    return True


def _hash_api_key(api_key):
    """Generate SHA-256 hash of API key"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def require_api_key(admin_only=False):
    """
    Decorator to require API key authentication

    Args:
        admin_only: If True, requires admin API key
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Load API keys
            try:
                _load_api_keys()
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'error_code': 'AUTH_SYSTEM_ERROR',
                    'message': 'Authentication system unavailable',
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }), 500

            # Extract API key from header
            api_key = request.headers.get('X-API-Key', '')

            if not api_key:
                return jsonify({
                    'status': 'error',
                    'error_code': 'INVALID_API_KEY',
                    'message': 'API key is missing. Provide X-API-Key header.',
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }), 401

            # Check if admin key is required
            if admin_only:
                if api_key not in _admin_keys_cache:
                    return jsonify({
                        'status': 'error',
                        'error_code': 'INVALID_ADMIN_KEY',
                        'message': 'Admin API key required for this endpoint',
                        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    }), 403
                key_info = _admin_keys_cache[api_key]
            else:
                # Check standard keys first, then admin keys (admin keys can access standard endpoints)
                if api_key in _api_keys_cache:
                    key_info = _api_keys_cache[api_key]
                elif api_key in _admin_keys_cache:
                    key_info = _admin_keys_cache[api_key]
                else:
                    return jsonify({
                        'status': 'error',
                        'error_code': 'INVALID_API_KEY',
                        'message': 'API key is invalid',
                        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    }), 401

            # Check if key has expired
            if key_info.get('expires_at'):
                # Simple date comparison (assumes ISO format)
                expires_at = key_info['expires_at']
                current_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                if current_time > expires_at:
                    return jsonify({
                        'status': 'error',
                        'error_code': 'EXPIRED_API_KEY',
                        'message': 'API key has expired',
                        'timestamp': current_time
                    }), 401

            # Check rate limit
            key_id = key_info.get('key_id', 'unknown')
            if not _check_rate_limit(key_id):
                return jsonify({
                    'status': 'error',
                    'error_code': 'RATE_LIMIT_EXCEEDED',
                    'message': 'Too many requests. Please try again later.',
                    'details': {
                        'rate_limit': config.RATE_LIMIT_PER_MINUTE,
                        'window': '1 minute'
                    },
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }), 429

            # Store key info in request context for logging
            request.api_key_info = key_info

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def get_api_key_hash():
    """Get hash of current request's API key for job ownership verification"""
    if hasattr(request, 'api_key_info'):
        api_key = request.headers.get('X-API-Key', '')
        return _hash_api_key(api_key)
    return None
