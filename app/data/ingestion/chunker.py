from __future__ import annotations

from .models import DocumentChunk, IngestionConfig, RawDocument
from .text_processing import split_sections, split_sentences, token_count


def build_chunks(document: RawDocument, config: IngestionConfig) -> list[DocumentChunk]:
    sections = split_sections(document.text)
    chunks: list[DocumentChunk] = []
    chunk_index = 0

    for section in sections:
        sentence_buffer: list[str] = []
        sentence_tokens: list[int] = []

        for sentence in split_sentences(section.text):
            sent_tokens = token_count(sentence)
            proposed_tokens = sum(sentence_tokens) + sent_tokens
            if sentence_buffer and proposed_tokens > config.chunk_size_tokens:
                chunks.append(
                    _to_chunk(
                        document=document,
                        section=section.title,
                        chunk_index=chunk_index,
                        text=" ".join(sentence_buffer),
                    )
                )
                chunk_index += 1

                sentence_buffer, sentence_tokens = _apply_overlap(
                    sentence_buffer,
                    sentence_tokens,
                    config.overlap_tokens,
                )

            sentence_buffer.append(sentence)
            sentence_tokens.append(sent_tokens)

        if sentence_buffer:
            chunks.append(
                _to_chunk(
                    document=document,
                    section=section.title,
                    chunk_index=chunk_index,
                    text=" ".join(sentence_buffer),
                )
            )
            chunk_index += 1

    return chunks


def _apply_overlap(
    sentence_buffer: list[str],
    sentence_tokens: list[int],
    overlap_tokens: int,
) -> tuple[list[str], list[int]]:
    retained_sentences: list[str] = []
    retained_tokens: list[int] = []
    running = 0

    for sentence, tokens in zip(reversed(sentence_buffer), reversed(sentence_tokens)):
        if running >= overlap_tokens:
            break
        retained_sentences.insert(0, sentence)
        retained_tokens.insert(0, tokens)
        running += tokens

    return retained_sentences, retained_tokens


def _to_chunk(document: RawDocument, section: str, chunk_index: int, text: str) -> DocumentChunk:
    source = str(document.source)
    chunk_id = f"{document.source.stem}:{chunk_index:04d}"
    chunk_text = f"{section}\n\n{text}" if text else section
    return DocumentChunk(
        chunk_id=chunk_id,
        text=chunk_text,
        metadata={
            "source": source,
            "section": section,
            "year": document.year,
        },
    )
