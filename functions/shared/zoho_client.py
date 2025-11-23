"""
Zoho CRM client for tag synchronization
"""

import time
import requests
from google.cloud import secretmanager
from . import config


class ZohoClient:
    """Client for Zoho CRM API"""

    def __init__(self):
        """Initialize Zoho client with OAuth credentials"""
        self.client_id = config.ZOHO_CLIENT_ID
        self.client_secret = self._get_secret(config.ZOHO_CLIENT_SECRET_NAME)
        self.refresh_token = self._get_secret(config.ZOHO_REFRESH_TOKEN_NAME)
        self.base_url = config.ZOHO_API_BASE_URL
        self.access_token = None
        self.token_expires_at = 0

    def _get_secret(self, secret_name):
        """Retrieve secret from Secret Manager"""
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{config.GCP_PROJECT_ID}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode('UTF-8')

    def _refresh_access_token(self):
        """Refresh OAuth access token"""
        url = "https://accounts.zoho.com/oauth/v2/token"

        params = {
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token'
        }

        try:
            response = requests.post(url, params=params)
            response.raise_for_status()

            data = response.json()
            self.access_token = data['access_token']
            # Zoho tokens typically expire in 1 hour
            self.token_expires_at = time.time() + 3600

            print("Zoho access token refreshed")
            return self.access_token

        except Exception as e:
            raise Exception(f"Failed to refresh Zoho access token: {str(e)}")

    def _get_access_token(self):
        """Get valid access token, refreshing if needed"""
        if not self.access_token or time.time() >= self.token_expires_at - 300:
            self._refresh_access_token()
        return self.access_token

    def fetch_all_tags(self):
        """
        Fetch all tags from Zoho CRM IBRS_Tags module

        Returns:
            list: List of tag dictionaries
        """
        all_tags = []
        page = 1
        has_more = True

        while has_more:
            try:
                tags, has_more = self._fetch_tags_page(page)
                all_tags.extend(tags)
                page += 1

                # Safety limit to prevent infinite loops
                if page > 100:
                    print("Warning: Reached maximum page limit (100 pages)")
                    break

            except Exception as e:
                print(f"Error fetching page {page}: {str(e)}")
                raise

        print(f"Fetched {len(all_tags)} tags from Zoho CRM")
        return all_tags

    def _fetch_tags_page(self, page):
        """
        Fetch a single page of tags

        Args:
            page: Page number (1-indexed)

        Returns:
            tuple: (tags list, has_more_records boolean)
        """
        url = f"{self.base_url}/crm/v2/{config.ZOHO_TAGS_MODULE}"

        headers = {
            'Authorization': f'Zoho-oauthtoken {self._get_access_token()}'
        }

        params = {
            'fields': 'id,name,Alias_1,Alias_2,Alias_3,Alias_4,Short_Form,Public_Description,Internal_Commentary,Type',
            'per_page': 200,
            'page': page
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                print(f"Rate limited by Zoho, waiting {retry_after} seconds")
                time.sleep(retry_after)
                return self._fetch_tags_page(page)  # Retry

            response.raise_for_status()
            data = response.json()

            # Extract tags from response
            tags = data.get('data', [])
            info = data.get('info', {})
            has_more = info.get('more_records', False)

            # Transform to internal format
            transformed_tags = [self._transform_tag(tag) for tag in tags]

            return transformed_tags, has_more

        except requests.exceptions.RequestException as e:
            raise Exception(f"Zoho API request failed: {str(e)}")

    def _transform_tag(self, zoho_tag):
        """
        Transform Zoho tag format to internal format

        Args:
            zoho_tag: Tag dictionary from Zoho API

        Returns:
            Transformed tag dictionary
        """
        # Extract aliases (filter out empty values)
        aliases = []
        for i in range(1, 5):
            alias = zoho_tag.get(f'Alias_{i}', '').strip()
            if alias:
                aliases.append(alias)

        return {
            'id': zoho_tag.get('id', ''),
            'name': zoho_tag.get('name', '').strip(),
            'aliases': aliases,
            'short_form': zoho_tag.get('Short_Form', '').strip().upper(),
            'public_description': zoho_tag.get('Public_Description', '').strip(),
            'internal_commentary': zoho_tag.get('Internal_Commentary', '').strip(),
            'type': zoho_tag.get('Type', '').strip(),
            'created_at': zoho_tag.get('Created_Time', ''),
            'updated_at': zoho_tag.get('Modified_Time', '')
        }

    def validate_tag(self, tag):
        """
        Validate tag has required fields

        Args:
            tag: Tag dictionary

        Returns:
            tuple: (is_valid: bool, errors: list)
        """
        errors = []

        # Check required fields
        if not tag.get('name'):
            errors.append("Missing required field: name")

        if not tag.get('short_form'):
            errors.append("Missing required field: short_form")

        tag_type = tag.get('type')
        if not tag_type:
            errors.append("Missing required field: type")
        elif tag_type not in config.TAG_TYPES:
            errors.append(f"Invalid tag type: {tag_type}")

        # Validate Horizon values
        if tag_type == 'Horizon':
            if tag.get('name') not in ['Solve', 'Plan', 'Explore']:
                errors.append(f"Invalid Horizon tag name: {tag.get('name')} (must be Solve, Plan, or Explore)")

        return len(errors) == 0, errors
