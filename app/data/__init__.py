"""Data ingestion and retrieval utilities for guideline documents."""

from .ingestion.pipeline import build_faiss_index, ingest_guidelines, load_faiss_index, rebuild_index
from .ingestion.models import DocumentChunk, IngestionConfig
from .emergency_detection import EMERGENCY_RESPONSE_TEMPLATE, is_emergency_query, maybe_get_emergency_response
from .retrieval import retrieve_chunks

__all__ = [
    "ingest_guidelines",
    "build_faiss_index",
    "rebuild_index",
    "load_faiss_index",
    "retrieve_chunks",
    "is_emergency_query",
    "maybe_get_emergency_response",
    "EMERGENCY_RESPONSE_TEMPLATE",
    "DocumentChunk",
    "IngestionConfig",
]
