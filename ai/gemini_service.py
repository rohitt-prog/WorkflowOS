import json
import logging
import os
from typing import List, Optional, Dict, Any
from google import genai
from google.genai import types
from pydantic import ValidationError

from backend.config import settings
from ai.models import WorkflowProposal, WorkflowAction, WorkflowTrigger

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are a workflow understanding engine.

Given a sequence of observed application events, infer the user's likely workflow intent.

Do not invent actions that are not supported by the observed events.

Preserve the observed action order.

Use semantic interpretation only to:
- name the workflow
- describe intent
- describe actions
- identify likely trigger
- identify variables
- identify involved applications

Do not generate executable code.
Do not generate Python, JavaScript, shell commands, browser code, or automation scripts.
Do not execute anything.

The workflow will require explicit human approval before automation."""


class GeminiServiceError(Exception):
    """Base exception for Gemini workflow understanding service errors."""
    pass


class GeminiConfigurationError(GeminiServiceError):
    """Raised when the Gemini API key or required configuration is missing."""
    pass


class WorkflowUnderstandingError(GeminiServiceError):
    """Raised when workflow generation fails or output cannot be validated."""
    pass


class GeminiWorkflowService:
    """
    Service responsible for communicating with the Gemini API to analyze
    detected user event sequences and synthesize structured workflow proposals.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client: Optional[genai.Client] = None
    ):
        if api_key is not None:
            self._api_key = api_key
        else:
            self._api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

        if model is not None:
            self._model = model
        else:
            self._model = settings.GEMINI_MODEL or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        self._client = client

    def _get_client(self) -> genai.Client:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise GeminiConfigurationError(
                "GEMINI_API_KEY is not configured in environment or .env. Please set a valid API key."
            )
        try:
            self._client = genai.Client(api_key=self._api_key)
            return self._client
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise GeminiConfigurationError(f"Failed to initialize Gemini client: {str(e)}")

    def _build_prompt(
        self,
        sequence: List[str],
        applications: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        prompt_lines = [
            "Detected workflow event sequence:",
        ]
        for i, step in enumerate(sequence, start=1):
            prompt_lines.append(f"{i}. {step}")

        prompt_lines.append("")

        if applications and len(applications) > 0:
            prompt_lines.append("Applications involved:")
            for app in applications:
                prompt_lines.append(f"- {app}")
            prompt_lines.append("")

        if context:
            prompt_lines.append("Additional context:")
            if "label" in context:
                prompt_lines.append(f"- Discovered pattern label: {context['label']}")
            if "occurrences" in context:
                prompt_lines.append(f"- Repetition occurrences: {context['occurrences']}")
            if "similarity" in context:
                prompt_lines.append(f"- Pattern similarity: {context['similarity']}")
            if "sample_events" in context:
                prompt_lines.append(f"- Sample event targets: {json.dumps(context['sample_events'])}")
            prompt_lines.append("")

        prompt_lines.append(
            "Analyze the above sequence and infer the user intent, likely trigger, ordered actions, "
            "variables, and involved applications. Maintain exact event order for the actions. "
            "Set requires_approval to true."
        )

        return "\n".join(prompt_lines)

    def generate_workflow(
        self,
        sequence: List[str],
        applications: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> WorkflowProposal:
        """
        Analyzes a sequence of user actions using Gemini and returns a validated WorkflowProposal.

        :param sequence: Ordered list of action verbs (e.g. ['open_email', 'download_attachment', ...])
        :param applications: Optional list of application names observed in the workflow
        :param context: Optional metadata from discovery (e.g. label, occurrences, similarity)
        :return: Validated WorkflowProposal instance
        :raises GeminiConfigurationError: If API key is missing or invalid
        :raises WorkflowUnderstandingError: If generation fails or output does not conform to schema
        """
        if not sequence or len(sequence) == 0:
            raise WorkflowUnderstandingError("Cannot generate workflow from an empty event sequence.")

        client = self._get_client()
        prompt = self._build_prompt(sequence, applications, context)

        # Determine candidate models to try in order
        candidate_models = [self._model]
        for fallback in ["gemini-3.8-flash", "gemini-2.5-flash"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_error = None
        for current_model in candidate_models:
            logger.info(
                f"Invoking Gemini ({current_model}) for workflow inference on sequence of {len(sequence)} steps..."
            )

            try:
                config = types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=WorkflowProposal,
                    temperature=0.2,
                )

                response = client.models.generate_content(
                    model=current_model,
                    contents=prompt,
                    config=config,
                )

                # Extract parsed output or fallback to parsing response.text
                proposal: Optional[WorkflowProposal] = None
                if hasattr(response, "parsed") and response.parsed is not None:
                    if isinstance(response.parsed, WorkflowProposal):
                        proposal = response.parsed
                    elif isinstance(response.parsed, dict):
                        proposal = WorkflowProposal.model_validate(response.parsed)

                if proposal is None and response.text:
                    proposal = WorkflowProposal.model_validate_json(response.text)

                if proposal is None:
                    raise WorkflowUnderstandingError("Gemini returned an empty response with no proposal data.")

                # Safety enforcement: requires_approval must always be True
                proposal.requires_approval = True

                logger.info(f"Successfully synthesized WorkflowProposal via {current_model}: '{proposal.name}'")
                return proposal

            except ValidationError as ve:
                logger.error(f"Gemini structured output failed Pydantic validation: {ve}")
                raise WorkflowUnderstandingError(f"Response validation error: {str(ve)}")
            except GeminiConfigurationError:
                raise
            except Exception as e:
                err_str = str(e)
                logger.warning(f"Model {current_model} call failed: {err_str}")
                last_error = e
                # If server is overloaded (503/429/404), continue to next fallback candidate
                continue

        logger.error(f"All Gemini models exhausted. Last error: {last_error}", exc_info=True)
        raise WorkflowUnderstandingError(f"Gemini generation error: {str(last_error)}")


# Singleton instance for application use
gemini_workflow_service = GeminiWorkflowService()
