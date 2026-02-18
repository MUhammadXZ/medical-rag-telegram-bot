from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from app.data.emergency_detection import maybe_get_emergency_response
from app.data.ingestion.pipeline import load_faiss_index
from app.data.retrieval import retrieve_chunks


logger = logging.getLogger(__name__)


REFUSAL_MESSAGE = (
    "I can only help with cow's milk protein allergy (CMPA) questions.\n"
    "Please ask about CMPA symptoms, diagnosis, management, emergency red flags, or safe feeding alternatives."
)

PROCESSING_ERROR_MESSAGE = (
    "I couldn't complete your request right now due to a temporary processing issue.\n"
    "Please try again in a moment."
)


@dataclass(frozen=True)
class CmpaRagServiceConfig:
    top_k: int = 5
    min_similarity: float = 0.75


@dataclass(frozen=True)
class CmpaAnswer:
    text: str
    is_emergency: bool
    is_refusal: bool


class CmpaRagService:
    """Application service for CMPA-focused retrieval and response formatting."""

    def __init__(
        self,
        *,
        index: Any,
        metadata: dict[str, object],
        embedding_model: str = "text-embedding-3-small",
        embedding_client: object | None = None,
        config: CmpaRagServiceConfig | None = None,
    ) -> None:
        self._index = index
        self._metadata = metadata
        self._embedding_model = embedding_model
        self._embedding_client = embedding_client
        self._config = config or CmpaRagServiceConfig()

    @classmethod
    def from_index_files(
        cls,
        *,
        index_path: str,
        metadata_path: str,
        embedding_client: object | None = None,
    ) -> "CmpaRagService":
        index, metadata = load_faiss_index(index_path=index_path, metadata_path=metadata_path)
        embedding_model = str(metadata.get("embedding_model", "text-embedding-3-small"))
        return cls(
            index=index,
            metadata=metadata,
            embedding_model=embedding_model,
            embedding_client=embedding_client,
        )

    async def answer(self, query: str) -> CmpaAnswer:
        return await asyncio.to_thread(self._answer_sync, query)

    def _answer_sync(self, query: str) -> CmpaAnswer:
        emergency_text = maybe_get_emergency_response(query)
        if emergency_text:
            return CmpaAnswer(
                text=self._format_emergency_only_response(emergency_text),
                is_emergency=True,
                is_refusal=False,
            )

        try:
            retrieval_result = retrieve_chunks(
                query=query,
                index=self._index,
                metadata=self._metadata,
                embedding_model=self._embedding_model,
                embedding_client=self._embedding_client,
                top_k=self._config.top_k,
                min_similarity=self._config.min_similarity,
            )
        except Exception:  # pragma: no cover - defensive runtime handling.
            logger.exception("CMPA retrieval failed.")
            return CmpaAnswer(text=PROCESSING_ERROR_MESSAGE, is_emergency=False, is_refusal=True)

        if bool(retrieval_result.get("rejected", False)):
            return CmpaAnswer(
                text=self._format_refusal_response(),
                is_emergency=False,
                is_refusal=True,
            )

        retrieved = retrieval_result.get("retrieved", [])
        if not isinstance(retrieved, list) or not retrieved:
            return CmpaAnswer(text=self._format_refusal_response(), is_emergency=False, is_refusal=True)

        return CmpaAnswer(
            text=self._format_cmpa_response(query=query, retrieved=retrieved),
            is_emergency=False,
            is_refusal=False,
        )

    def _format_emergency_only_response(self, emergency_text: str) -> str:
        return (
            "🚨 *EMERGENCY WARNING*\n"
            f"{emergency_text}\n\n"
            "*Immediate action*\n"
            "• Seek urgent in-person medical care now.\n"
            "• Do not wait for online advice if breathing, consciousness, or swelling symptoms are present."
        )

    def _format_refusal_response(self) -> str:
        return (
            "*Scope notice*\n"
            f"{REFUSAL_MESSAGE}\n\n"
            "*How to ask for better help*\n"
            "• Mention CMPA-specific symptoms or concerns.\n"
            "• Include age, feeding type, and timeline when relevant."
        )

    def _format_cmpa_response(self, *, query: str, retrieved: list[dict[str, object]]) -> str:
        evidence_lines: list[str] = []
        for item in retrieved[:3]:
            metadata = item.get("metadata", {})
            section = ""
            if isinstance(metadata, dict):
                section = str(metadata.get("section", "")).strip()

            text = str(item.get("text", "")).strip().replace("\n", " ")
            excerpt = text[:260] + "..." if len(text) > 260 else text

            if section:
                evidence_lines.append(f"• [{section}] {excerpt}")
            else:
                evidence_lines.append(f"• {excerpt}")

        evidence_block = "\n".join(evidence_lines)

        return (
            "*CMPA Guidance*\n"
            f"Question: {query.strip()}\n\n"
            "*Evidence from CMPA knowledge base*\n"
            f"{evidence_block}\n\n"
            "*Safety note*\n"
            "• This is educational support and not a diagnosis.\n"
            "• Seek clinician evaluation for persistent, worsening, or severe symptoms."
        )
