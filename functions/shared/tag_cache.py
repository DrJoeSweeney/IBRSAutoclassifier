"""
Tag cache management module
Handles loading and caching of tags from Cloud Storage
"""

import json
import time
from datetime import datetime
from google.cloud import storage
from . import config

# Global cache
_tags_cache = None
_cache_timestamp = 0
_cache_blob_timestamp = None


class TagCache:
    """Manages tag data and lookups"""

    def __init__(self, tags_data):
        self.tags_data = tags_data
        self.tags = tags_data.get('tags', [])
        self.sync_timestamp = tags_data.get('sync_timestamp', '')

        # Build lookup indexes for fast searching
        self._build_indexes()

    def _build_indexes(self):
        """Build lookup indexes for efficient tag matching"""
        self.by_name = {}
        self.by_type = {
            'Horizon': [],
            'Practice': [],
            'Stream': [],
            'Role': [],
            'Vendor': [],
            'Product': [],
            'Topic': []
        }
        self.by_alias = {}

        for tag in self.tags:
            name = tag.get('name', '').lower()
            tag_type = tag.get('type', '')

            # Index by name
            self.by_name[name] = tag

            # Index by type
            if tag_type in self.by_type:
                self.by_type[tag_type].append(tag)

            # Index by aliases
            aliases = tag.get('aliases', [])
            for alias in aliases:
                if alias:
                    alias_lower = alias.lower()
                    self.by_alias[alias_lower] = tag

    def get_by_name(self, name):
        """Get tag by exact name match"""
        return self.by_name.get(name.lower())

    def get_by_alias(self, alias):
        """Get tag by alias match"""
        return self.by_alias.get(alias.lower())

    def get_by_name_or_alias(self, text):
        """Get tag by name or alias"""
        tag = self.get_by_name(text)
        if tag:
            return tag, 'primary'
        tag = self.get_by_alias(text)
        if tag:
            return tag, 'alias'
        return None, None

    def get_by_type(self, tag_type):
        """Get all tags of a specific type"""
        return self.by_type.get(tag_type, [])

    def get_all_tags(self):
        """Get all tags"""
        return self.tags

    def get_tags_count(self):
        """Get total number of tags"""
        return len(self.tags)

    def get_formatted_for_prompt(self):
        """
        Format tags for Gemini prompt
        Returns a structured representation suitable for AI classification
        """
        formatted = []
        for tag in self.tags:
            formatted.append({
                'name': tag.get('name', ''),
                'aliases': [a for a in tag.get('aliases', []) if a],
                'short_form': tag.get('short_form', ''),
                'description': tag.get('public_description', ''),
                'type': tag.get('type', '')
            })
        return formatted


def load_tag_cache(force_refresh=False):
    """
    Load tag cache from Cloud Storage

    Args:
        force_refresh: If True, bypass cache and reload from storage

    Returns:
        TagCache: Initialized tag cache object
    """
    global _tags_cache, _cache_timestamp, _cache_blob_timestamp

    try:
        # Check if we need to refresh
        if not force_refresh and _tags_cache:
            # Check if cache is still fresh (< 5 minutes old)
            if (time.time() - _cache_timestamp) < 300:
                return _tags_cache

        # Load from Cloud Storage
        storage_client = storage.Client(project=config.GCP_PROJECT_ID)
        bucket = storage_client.bucket(config.TAG_CACHE_BUCKET)
        blob = bucket.blob(config.TAG_CACHE_BLOB_NAME)

        # Check if blob has been modified
        blob.reload()
        if not force_refresh and _cache_blob_timestamp and blob.updated == _cache_blob_timestamp:
            # Blob hasn't changed, keep current cache
            _cache_timestamp = time.time()
            return _tags_cache

        # Download and parse
        content = blob.download_as_text()
        tags_data = json.loads(content)

        # Validate structure
        if 'tags' not in tags_data:
            raise ValueError("Invalid tag cache format: missing 'tags' field")

        # Create new cache
        _tags_cache = TagCache(tags_data)
        _cache_timestamp = time.time()
        _cache_blob_timestamp = blob.updated

        print(f"Tag cache loaded: {_tags_cache.get_tags_count()} tags from {tags_data.get('sync_timestamp', 'unknown')}")

        return _tags_cache

    except Exception as e:
        print(f"Error loading tag cache: {str(e)}")
        # If we have an old cache, return it
        if _tags_cache:
            print("Using stale tag cache")
            return _tags_cache
        raise Exception(f"Failed to load tag cache: {str(e)}")


def save_tag_cache(tags_data):
    """
    Save tag cache to Cloud Storage

    Args:
        tags_data: Dictionary containing tags and metadata
    """
    try:
        storage_client = storage.Client(project=config.GCP_PROJECT_ID)
        bucket = storage_client.bucket(config.TAG_CACHE_BUCKET)

        # Save backup of current cache
        current_blob = bucket.blob(config.TAG_CACHE_BLOB_NAME)
        if current_blob.exists():
            backup_name = f"{config.TAG_CACHE_BACKUP_PREFIX}{int(time.time())}.json"
            backup_blob = bucket.blob(backup_name)
            current_content = current_blob.download_as_text()
            backup_blob.upload_from_string(current_content, content_type='application/json')
            print(f"Backup saved: {backup_name}")

        # Save new cache
        blob = bucket.blob(config.TAG_CACHE_BLOB_NAME)
        blob.upload_from_string(
            json.dumps(tags_data, indent=2),
            content_type='application/json'
        )

        print(f"Tag cache saved: {len(tags_data.get('tags', []))} tags")

        # Force refresh of cache
        load_tag_cache(force_refresh=True)

        return True

    except Exception as e:
        print(f"Error saving tag cache: {str(e)}")
        raise


def get_cache_age_hours():
    """Get age of current tag cache in hours"""
    if _tags_cache and _tags_cache.sync_timestamp:
        try:
            sync_time = datetime.fromisoformat(_tags_cache.sync_timestamp.replace('Z', '+00:00'))
            now = datetime.now(sync_time.tzinfo)
            delta = now - sync_time
            return delta.total_seconds() / 3600
        except Exception:
            return None
    return None
