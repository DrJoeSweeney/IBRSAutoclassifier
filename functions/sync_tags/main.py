"""
Tag synchronization endpoint
POST /admin/sync-tags
"""

import time
import sys
import os
from flask import Flask, jsonify
from datetime import datetime

# Add parent directory to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import config
from shared.auth import require_api_key
from shared.zoho_client import ZohoClient
from shared.tag_cache import load_tag_cache, save_tag_cache

app = Flask(__name__)


@app.route('/admin/sync-tags', methods=['POST'])
@require_api_key(admin_only=True)
def sync_tags():
    """
    Synchronize tags from Zoho CRM to Cloud Storage cache

    Requires admin API key
    """
    start_time = time.time()

    try:
        # Load current cache for comparison
        current_tags = {}
        try:
            cache = load_tag_cache()
            current_tags = {tag['id']: tag for tag in cache.get_all_tags()}
            print(f"Loaded current cache with {len(current_tags)} tags")
        except Exception:
            print("No existing cache found, will create new one")

        # Fetch tags from Zoho
        try:
            zoho_client = ZohoClient()
            zoho_tags = zoho_client.fetch_all_tags()
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error_code': 'ZOHO_SYNC_FAILED',
                'message': 'Failed to sync tags from Zoho CRM',
                'details': {
                    'error': str(e)
                },
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), 500

        # Validate and filter tags
        valid_tags = []
        invalid_count = 0
        for tag in zoho_tags:
            is_valid, errors = zoho_client.validate_tag(tag)
            if is_valid:
                valid_tags.append(tag)
            else:
                print(f"Invalid tag {tag.get('name', 'unknown')}: {', '.join(errors)}")
                invalid_count += 1

        # Compare with current cache to detect changes
        new_tags = {tag['id']: tag for tag in valid_tags}

        changes = {
            'added': [],
            'updated': [],
            'removed': [],
            'unchanged': 0
        }

        # Find added and updated tags
        for tag_id, tag in new_tags.items():
            if tag_id not in current_tags:
                changes['added'].append({
                    'name': tag['name'],
                    'short_form': tag['short_form'],
                    'type': tag['type']
                })
            elif _tag_has_changes(current_tags[tag_id], tag):
                changes['updated'].append({
                    'name': tag['name'],
                    'short_form': tag['short_form'],
                    'type': tag['type'],
                    'changes': _get_tag_changes(current_tags[tag_id], tag)
                })
            else:
                changes['unchanged'] += 1

        # Find removed tags
        for tag_id, tag in current_tags.items():
            if tag_id not in new_tags:
                changes['removed'].append({
                    'name': tag['name'],
                    'short_form': tag['short_form'],
                    'type': tag['type'],
                    'reason': 'Not found in Zoho'
                })

        # Create new cache data
        sync_timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        cache_data = {
            'version': '1.0',
            'sync_timestamp': sync_timestamp,
            'sync_source': 'zoho_crm',
            'tags_count': len(valid_tags),
            'tags': valid_tags
        }

        # Save to Cloud Storage
        try:
            save_tag_cache(cache_data)
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error_code': 'CACHE_SAVE_FAILED',
                'message': 'Failed to save tag cache',
                'details': {
                    'error': str(e)
                },
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }), 500

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Return success response
        response = {
            'status': 'success',
            'sync_timestamp': sync_timestamp,
            'tags_total': len(valid_tags),
            'changes': {
                'added': len(changes['added']),
                'updated': len(changes['updated']),
                'removed': len(changes['removed']),
                'unchanged': changes['unchanged']
            },
            'processing_time_ms': processing_time_ms
        }

        # Include details of changes if any
        if changes['added']:
            response['added_tags'] = changes['added'][:10]  # Limit to first 10
        if changes['updated']:
            response['updated_tags'] = changes['updated'][:10]
        if changes['removed']:
            response['removed_tags'] = changes['removed'][:10]

        if invalid_count > 0:
            response['warnings'] = {
                'invalid_tags_skipped': invalid_count
            }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error_code': 'INTERNAL_ERROR',
            'message': 'Unexpected error during sync',
            'details': {
                'error': str(e)
            },
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }), 500


def _tag_has_changes(old_tag, new_tag):
    """Check if tag has any changes"""
    # Compare key fields
    fields_to_compare = ['name', 'aliases', 'short_form', 'public_description',
                         'internal_commentary', 'type']

    for field in fields_to_compare:
        if old_tag.get(field) != new_tag.get(field):
            return True

    return False


def _get_tag_changes(old_tag, new_tag):
    """Get list of changed fields"""
    changes = []
    fields_to_compare = {
        'name': 'name changed',
        'aliases': 'aliases updated',
        'short_form': 'short form changed',
        'public_description': 'public description updated',
        'internal_commentary': 'internal commentary updated',
        'type': 'type changed'
    }

    for field, description in fields_to_compare.items():
        if old_tag.get(field) != new_tag.get(field):
            changes.append(description)

    return changes


# For local testing
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8083, debug=True)
