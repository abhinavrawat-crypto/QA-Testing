"""AI / Analysis Service — Google Gemini integration behind AIProvider interface.

Implements:
  - score_story()     : INVEST + Gherkin AC scoring
  - rewrite_story()   : Generate improved story (summary, description, AC)

All Gemini calls are abstracted via the AIProvider protocol so the model/vendor
can be swapped without touching callers.
"""
import json
import logging
import re
from typing import Any, Dict, Optional, Protocol, runtime_checkable

import google.generativeai as genai

from app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------
# Provider interface (swap Gemini for any other LLM here)
# ---------------------------------------------------------------
@runtime_checkable
class AIProvider(Protocol):
    async def score_story(self, summary: str, description: str, ac: str) -> Dict[str, Any]: ...
    async def rewrite_story(self, summary: str, description: str, ac: str, gaps: list) -> Dict[str, str]: ...
    async def embed_text(self, text: str) -> list[float]: ...


# ---------------------------------------------------------------
# Gemini implementation
# ---------------------------------------------------------------
class GeminiProvider:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.GEMINI_API_KEY
        model_name = settings.GEMINI_MODEL or "gemini-3.5-flash"
        if "1.5" in model_name or "1.0" in model_name:
            model_name = "gemini-3.5-flash"

        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(model_name)
                self._embed_model = settings.GEMINI_EMBEDDING_MODEL
            except Exception as e:
                logger.error(f"Failed to initialize Gemini AI model: {e}")
                self._model = None
                self._embed_model = None
        else:
            self._model = None
            self._embed_model = None

    async def score_story(self, summary: str, description: str, ac: str) -> Dict[str, Any]:
        if not self.api_key or not self._model:
            raise ValueError("Gemini API Key is not configured. Please set your Gemini API Key in Settings.")

        prompt = f"""You are an expert agile coach. Evaluate this JIRA user story strictly against the INVEST criteria and Gherkin acceptance-criteria completeness.

STORY TITLE: {summary}

DESCRIPTION:
{description or "(empty)"}

ACCEPTANCE CRITERIA:
{ac or "(empty)"}

Return ONLY valid JSON (no markdown, no extra text) with this exact structure:
{{
  "overall_score": <0-100 float, weighted average>,
  "invest_scores": {{
    "independent": <0-100>,
    "negotiable": <0-100>,
    "valuable": <0-100>,
    "estimable": <0-100>,
    "small": <0-100>,
    "testable": <0-100>
  }},
  "ac_score": <0-100, how complete the Gherkin Given/When/Then AC is>,
  "gaps": [<list of specific gap strings, max 6>]
}}"""
        try:
            resp = self._model.generate_content(prompt)
            raw = resp.text.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"Gemini API error during story scoring: {e}")

    async def rewrite_story(
        self, summary: str, description: str, ac: str, gaps: list
    ) -> Dict[str, str]:
        if not self.api_key or not self._model:
            raise ValueError("Gemini API Key is not configured. Please set your Gemini API Key in Settings.")

        gaps_text = "\n".join(f"- {g}" for g in gaps) if gaps else "- General quality improvement"
        prompt = f"""You are an expert agile coach. Rewrite the following JIRA user story to fix the identified quality gaps and meet the INVEST criteria with proper Gherkin acceptance criteria.

ORIGINAL TITLE: {summary}
ORIGINAL DESCRIPTION: {description or "(empty)"}
ORIGINAL AC: {ac or "(empty)"}

IDENTIFIED GAPS:
{gaps_text}

Return ONLY valid JSON (no markdown) with this exact structure:
{{
  "proposed_summary": "<improved story title, concise As a/I want/So that format if applicable>",
  "proposed_description": "<improved description with clear user value, context, and any NFRs>",
  "proposed_ac": "<ALL acceptance criteria rewritten in Gherkin Given/When/Then format, one scenario per line>"
}}"""
        try:
            resp = self._model.generate_content(prompt)
            raw = resp.text.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"Gemini API error during story rewrite: {e}")

    async def embed_text(self, text: str) -> list[float]:
        if not self.api_key or not self._embed_model:
            raise ValueError("Gemini API Key is not configured. Please set your Gemini API Key in Settings.")
        try:
            result = genai.embed_content(
                model=self._embed_model,
                content=text,
                task_type="retrieval_document",
            )
            return result["embedding"]
        except Exception as e:
            raise RuntimeError(f"Gemini API error during embedding: {e}")


# ---------------------------------------------------------------
# Singleton factory & reload
# ---------------------------------------------------------------
_provider: Optional[GeminiProvider] = None


def get_ai_provider() -> GeminiProvider:
    global _provider
    if _provider is None:
        _provider = GeminiProvider()
    return _provider


def reload_ai_provider() -> GeminiProvider:
    global _provider
    _provider = GeminiProvider()
    return _provider

