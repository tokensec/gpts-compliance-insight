"""Risk classification service using Instructor for structured outputs."""

import logging

from gci.llm.client import LLMClient
from gci.llm.prompts import create_risk_classification_messages
from gci.models.gpt import GPT
from gci.models.risk import BatchRiskResponse, GPTRiskClassification, RiskLevel

logger = logging.getLogger(__name__)


class RiskClassificationService:
    """Service for classifying GPT risk levels based on file names."""

    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize risk classification service.

        Args:
            llm_client: LLM client for making classification requests
        """
        self.llm_client = llm_client

    def classify_batch(
        self,
        gpts_data: list[tuple[str, str, list[str]]],
    ) -> list[GPTRiskClassification]:
        """Classify a batch of GPTs using structured outputs.

        Args:
            gpts_data: List of (gpt_id, gpt_name, file_names) tuples

        Returns:
            List of risk classifications
        """
        if not gpts_data:
            return []

        # Format GPTs for prompt
        gpt_info_parts = []
        for _, gpt_name, file_names in gpts_data:
            file_names_str = ", ".join(file_names) if file_names else "No files"
            gpt_info_parts.append(f"GPT Name: {gpt_name}\nFile Names: {file_names_str}")

        gpt_info = "\n\n".join(gpt_info_parts)

        # Create messages for LLM
        messages = create_risk_classification_messages(gpt_info)

        logger.debug(f"Classifying batch of {len(gpts_data)} GPTs")

        try:
            # Get structured response using Instructor
            response = self.llm_client.complete(messages=messages, response_model=BatchRiskResponse)

            # Convert to storage format
            results = []
            for classification in response.classifications:
                # Find matching GPT ID
                gpt_id = ""
                for gid, name, _ in gpts_data:
                    if name == classification.gpt_name:
                        gpt_id = gid
                        break

                if not gpt_id:
                    logger.warning(f"Could not find GPT ID for: {classification.gpt_name}")

                results.append(
                    GPTRiskClassification(
                        gpt_id=gpt_id,
                        gpt_name=classification.gpt_name,
                        file_names=classification.file_names,
                        risk_level=RiskLevel(classification.risk_level),
                        reasoning=classification.reasoning,
                    )
                )

            logger.debug(f"Successfully classified {len(results)} GPTs")
            return results

        except Exception as e:
            logger.error(f"Error classifying batch: {e}")
            # Return empty classifications with error reasoning
            return [
                GPTRiskClassification(
                    gpt_id=gpt_id,
                    gpt_name=gpt_name,
                    file_names=file_names,
                    risk_level=RiskLevel.LOW,
                    reasoning=f"Classification failed: {e!s}",
                )
                for gpt_id, gpt_name, file_names in gpts_data
            ]

    @staticmethod
    def extract_file_names_from_gpt(gpt: GPT) -> list[str]:
        """Extract file names from GPT model.

        Args:
            gpt: GPT model instance

        Returns:
            List of file names associated with the GPT
        """
        return [f.name for f in gpt.files if f.name]
