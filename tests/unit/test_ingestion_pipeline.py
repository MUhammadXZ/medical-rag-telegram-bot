from pathlib import Path

from app.data.ingestion.models import IngestionConfig
from app.data.ingestion.pipeline import ingest_guidelines


def test_ingest_guidelines_txt_with_sections_and_metadata(tmp_path: Path) -> None:
    sample = tmp_path / "cardiology_guideline_2022.txt"
    sample.write_text(
        """
INTRODUCTION
This is a sentence. This is another sentence.

1.1 SCOPE
Third sentence is here. Fourth sentence is here.
""".strip(),
        encoding="utf-8",
    )

    records = ingest_guidelines(
        sample,
        config=IngestionConfig(chunk_size_tokens=8, overlap_ratio=0.15),
    )

    assert records
    assert all({"id", "text", "metadata"}.issubset(r.keys()) for r in records)
    first_meta = records[0]["metadata"]
    assert first_meta["source"].endswith("cardiology_guideline_2022.txt")
    assert first_meta["year"] == 2022
    assert "section" in first_meta

    # Ensure section titles are preserved in both metadata and chunk text payload.
    assert records[0]["metadata"]["section"] == "INTRODUCTION"
    assert records[0]["text"].startswith("INTRODUCTION\n\n")
    assert any(
        r["metadata"]["section"] == "1.1 SCOPE" and r["text"].startswith("1.1 SCOPE\n\n")
        for r in records
    )

    if len(records) > 1:
        prior_last = records[0]["text"].split()[-1]
        assert prior_last in records[1]["text"]
