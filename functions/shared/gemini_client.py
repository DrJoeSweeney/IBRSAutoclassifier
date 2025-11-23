"""
Gemini AI client for document classification
"""

import json
import time
from vertexai.generative_models import GenerativeModel, GenerationConfig
import vertexai
from . import config


class GeminiClassifier:
    """Handles document classification using Gemini AI"""

    def __init__(self):
        """Initialize Vertex AI and Gemini model"""
        vertexai.init(
            project=config.GCP_PROJECT_ID,
            location=config.VERTEX_AI_LOCATION
        )

        self.generation_config = GenerationConfig(
            temperature=config.CLASSIFICATION_TEMPERATURE,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_mime_type="application/json"
        )

        self.model = GenerativeModel(
            config.VERTEX_AI_MODEL,
            generation_config=self.generation_config
        )

    def classify_document(self, document_text, tag_cache, max_retries=None):
        """
        Classify document using Gemini AI

        Args:
            document_text: Extracted text from document
            tag_cache: TagCache object with available tags
            max_retries: Maximum retry attempts (default from config)

        Returns:
            dict: Classification results with structure:
            {
                'horizon': {...},
                'practice': {...},
                'streams': [...],
                'roles': [...],
                'vendors': [...],
                'products': [...],
                'topics': [...]
            }
        """
        if max_retries is None:
            max_retries = config.CLASSIFICATION_MAX_RETRIES

        # Build prompt
        prompt = self._build_classification_prompt(document_text, tag_cache)

        # Try classification with retries
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                result_text = response.text

                # Parse JSON response
                classification = json.loads(result_text)

                # Validate and enrich classification
                validated = self._validate_and_enrich_classification(
                    classification,
                    tag_cache
                )

                return validated

            except json.JSONDecodeError as e:
                last_error = f"Invalid JSON response from Gemini: {str(e)}"
                print(f"Attempt {attempt + 1} failed: {last_error}")

            except Exception as e:
                last_error = str(e)
                print(f"Attempt {attempt + 1} failed: {last_error}")

                # Exponential backoff
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)

        raise Exception(f"Classification failed after {max_retries} attempts. Last error: {last_error}")

    def _build_classification_prompt(self, document_text, tag_cache):
        """Build the classification prompt for Gemini"""

        # Get formatted tags for prompt
        tags = tag_cache.get_formatted_for_prompt()

        # Truncate document text if too long (keep first 100k chars)
        if len(document_text) > 100000:
            document_text = document_text[:100000] + "\n\n[Document truncated for analysis]"

        system_instruction = """You are a document classification assistant for IBRS (Information and Business Research Services), a technology research and advisory firm.

Your task is to analyze documents and assign relevant tags from a predefined taxonomy.

CLASSIFICATION RULES (CRITICAL):
1. You MUST assign exactly 1 Horizon tag (must be one of: Solve, Plan, or Explore)
   - Solve: Content focused on solving current, immediate problems (tactical)
   - Plan: Content focused on planning and mid-term strategy (6-18 months)
   - Explore: Content exploring emerging technologies and long-term trends

2. You MUST assign exactly 1 Practice tag (from the provided list)
   - Practice tags represent IBRS's core business practice areas

3. You MAY assign 0 or more tags of these types: Stream, Role, Vendor, Product, Topic
   - Only assign these if they are clearly relevant to the document
   - Be selective - quality over quantity

4. Only use tags from the provided list
5. Match tags using their name or any of their aliases
6. Provide confidence scores between 0.0 and 1.0 for each tag
7. Higher confidence (>0.8) means the tag is central to the document
8. Lower confidence (0.5-0.8) means the tag is mentioned or relevant but not central

RESPONSE FORMAT:
Return ONLY valid JSON with this exact structure (no additional text):
{
  "horizon": {"name": "Solve", "confidence": 0.92},
  "practice": {"name": "Cybersecurity", "confidence": 0.88},
  "streams": [{"name": "Risk Management", "confidence": 0.85}],
  "roles": [{"name": "CISO", "confidence": 0.81}],
  "vendors": [{"name": "Microsoft", "confidence": 0.79}],
  "products": [{"name": "Azure", "confidence": 0.81}],
  "topics": [{"name": "Zero Trust", "confidence": 0.76}]
}
"""

        tags_json = json.dumps(tags, indent=2)

        prompt = f"""{system_instruction}

DOCUMENT TO CLASSIFY:
{document_text}

AVAILABLE TAGS:
{tags_json}

Analyze the document and return the classification in the exact JSON format specified above."""

        return prompt

    def _validate_and_enrich_classification(self, classification, tag_cache):
        """
        Validate classification meets rules and enrich with tag details

        Args:
            classification: Raw classification from Gemini
            tag_cache: TagCache object

        Returns:
            Validated and enriched classification
        """
        result = {
            'horizon': None,
            'practice': None,
            'streams': [],
            'roles': [],
            'vendors': [],
            'products': [],
            'topics': []
        }

        # Validate and enrich Horizon
        horizon = classification.get('horizon')
        if horizon and isinstance(horizon, dict):
            tag_name = horizon.get('name', '')
            tag, match_type = tag_cache.get_by_name_or_alias(tag_name)
            if tag and tag.get('type') == 'Horizon':
                result['horizon'] = {
                    'name': tag['name'],
                    'short_form': tag.get('short_form', ''),
                    'confidence': float(horizon.get('confidence', 0.0)),
                    'matched_via': match_type or 'primary'
                }

        # If no horizon or invalid, try to find one with highest confidence
        if not result['horizon']:
            print("Warning: No valid Horizon tag, using default 'Solve'")
            tag, _ = tag_cache.get_by_name_or_alias('Solve')
            if tag:
                result['horizon'] = {
                    'name': tag['name'],
                    'short_form': tag.get('short_form', ''),
                    'confidence': 0.5,
                    'matched_via': 'default'
                }

        # Validate and enrich Practice
        practice = classification.get('practice')
        if practice and isinstance(practice, dict):
            tag_name = practice.get('name', '')
            tag, match_type = tag_cache.get_by_name_or_alias(tag_name)
            if tag and tag.get('type') == 'Practice':
                result['practice'] = {
                    'name': tag['name'],
                    'short_form': tag.get('short_form', ''),
                    'confidence': float(practice.get('confidence', 0.0)),
                    'matched_via': match_type or 'primary'
                }

        # If no practice, try to pick one (should not happen, but handle gracefully)
        if not result['practice']:
            print("Warning: No valid Practice tag assigned")
            practices = tag_cache.get_by_type('Practice')
            if practices:
                # Use first practice as fallback
                tag = practices[0]
                result['practice'] = {
                    'name': tag['name'],
                    'short_form': tag.get('short_form', ''),
                    'confidence': 0.3,
                    'matched_via': 'default'
                }

        # Process optional tag types
        for tag_type_key, tag_type_name in [
            ('streams', 'Stream'),
            ('roles', 'Role'),
            ('vendors', 'Vendor'),
            ('products', 'Product'),
            ('topics', 'Topic')
        ]:
            tags_list = classification.get(tag_type_key, [])
            if isinstance(tags_list, list):
                for tag_data in tags_list:
                    if isinstance(tag_data, dict):
                        tag_name = tag_data.get('name', '')
                        tag, match_type = tag_cache.get_by_name_or_alias(tag_name)
                        if tag and tag.get('type') == tag_type_name:
                            result[tag_type_key].append({
                                'name': tag['name'],
                                'short_form': tag.get('short_form', ''),
                                'confidence': float(tag_data.get('confidence', 0.0)),
                                'matched_via': match_type or 'primary'
                            })

        return result

    def validate_classification_rules(self, classification):
        """
        Validate that classification meets mandatory rules

        Args:
            classification: Classification result

        Returns:
            tuple: (is_valid: bool, errors: list)
        """
        errors = []

        # Check for exactly 1 Horizon
        if not classification.get('horizon'):
            errors.append("Missing mandatory Horizon tag")
        elif classification['horizon'].get('name') not in ['Solve', 'Plan', 'Explore']:
            errors.append(f"Invalid Horizon value: {classification['horizon'].get('name')}")

        # Check for exactly 1 Practice
        if not classification.get('practice'):
            errors.append("Missing mandatory Practice tag")

        return len(errors) == 0, errors
