"""
Document Classifier Service
----------------------------
Uses Groq (llama-3.1-8b-instant) to classify documents across multiple dimensions.
Returns a structured JSON classification with:
  - document_type, topic_domain, content_characteristics
  - sensitivity_level, sensitivity_reasons
  - summary, key_entities, classification_confidence
"""
import json
import os
import logging
from typing import Optional

from groq import Groq

from models.document import PageData

logger = logging.getLogger(__name__)

# Max chars sent to LLM for classification (prevent prompt injection)
MAX_CLASSIFICATION_CHARS = 3000

# Model for fast classification
CLASSIFIER_MODEL = "llama-3.1-8b-instant"


def _get_client() -> Groq:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY environment variable not set")
    return Groq(api_key=key)


def build_classification_prompt(pages: list[PageData]) -> str:
    """
    Build the LLM prompt from the first ~3 pages of text.
    """
    excerpt_parts = []
    for p in pages[:3]:
        text_chunk = p.text[:1000] if p.text else ""
        if text_chunk:
            excerpt_parts.append(f"[Page {p.page_num}]\n{text_chunk}")

    excerpt = "\n\n".join(excerpt_parts)[:MAX_CLASSIFICATION_CHARS]

    # Sanitize: ensure no prompt injection characters
    excerpt = excerpt.replace("SYSTEM:", "").replace("USER:", "").replace("ASSISTANT:", "")

    has_tables = any(p.has_tables for p in pages)
    has_ocr = any(p.extraction_method == "ocr" for p in pages)
    total_pages = len(pages)

    prompt = f"""You are a document classification expert. Analyze the document excerpt below and return ONLY a valid JSON object — no markdown fences, no explanation.

Document excerpt:
---
{excerpt}
---

Document metadata:
- Total pages: {total_pages}
- Has tables: {has_tables}
- Contains scanned/OCR pages: {has_ocr}

Return ONLY this JSON structure (fill in the values based on the document):
{{
  "document_type": "<one of: invoice | report | research_paper | legal | medical | meeting_notes | resume | contract | presentation | other>",
  "topic_domain": "<one of: finance | healthcare | technology | legal | academic | business | personal | government | other>",
  "content_characteristics": {{
    "has_tables": {str(has_tables).lower()},
    "has_images": false,
    "is_scanned": {str(has_ocr).lower()},
    "language": "English",
    "approximate_page_count": {total_pages},
    "text_density": "<high | medium | low>"
  }},
  "sensitivity_level": "<one of: public | internal | confidential | restricted>",
  "sensitivity_reasons": ["<reason1>", "<reason2>"],
  "summary": "<2-3 sentences: what this document is about, its main purpose, and key takeaways>",
  "key_entities": ["<entity1>", "<entity2>", "<entity3>"],
  "classification_confidence": 0.85
}}

Respond ONLY with the JSON. No markdown, no explanations."""

    return prompt


def classify_document(pages: list[PageData]) -> dict:
    """
    Classify a document using Groq llama-3.1-8b-instant.
    Returns a structured classification dict.
    Retries once if JSON parsing fails.
    """
    try:
        client = _get_client()
        prompt = build_classification_prompt(pages)

        for attempt in range(2):
            try:
                completion = client.chat.completions.create(
                    model=CLASSIFIER_MODEL,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                raw = completion.choices[0].message.content.strip()

                # Strip markdown fences if present (defensive)
                raw = raw.replace("```json", "").replace("```", "").strip()

                result = json.loads(raw)

                # Validate required keys
                required_keys = ["document_type", "topic_domain", "sensitivity_level", "summary"]
                for key in required_keys:
                    if key not in result:
                        raise ValueError(f"Missing key: {key}")

                logger.info(f"Classification successful: {result.get('document_type')}")
                return result

            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed (attempt {attempt + 1}): {e}")
                if attempt == 0:
                    prompt += "\n\nIMPORTANT: Your previous response was not valid JSON. Return ONLY the JSON object, starting with {{ and ending with }}."
                    continue
                break
            except Exception as e:
                logger.error(f"LLM call failed (attempt {attempt + 1}): {e}")
                break

    except Exception as e:
        logger.error(f"Classification failed: {e}")

    # Fallback classification
    return _fallback_classification(pages)


def _fallback_classification(pages: list[PageData]) -> dict:
    """Returns a safe default classification when LLM is unavailable."""
    has_tables = any(p.has_tables for p in pages)
    has_ocr = any(p.extraction_method == "ocr" for p in pages)

    return {
        "document_type": "other",
        "topic_domain": "other",
        "content_characteristics": {
            "has_tables": has_tables,
            "has_images": False,
            "is_scanned": has_ocr,
            "language": "English",
            "approximate_page_count": len(pages),
            "text_density": "medium"
        },
        "sensitivity_level": "internal",
        "sensitivity_reasons": ["classification_unavailable"],
        "summary": "Document classification unavailable. Please configure GROQ_API_KEY.",
        "key_entities": [],
        "classification_confidence": 0.0,
        "fallback": True
    }