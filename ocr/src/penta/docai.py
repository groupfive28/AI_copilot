from __future__ import annotations

import mimetypes
import sys
from dataclasses import dataclass, field
from pathlib import Path

from google.api_core.client_options import ClientOptions
from google.cloud import documentai

from penta.config import settings

_client: documentai.DocumentProcessorServiceClient | None = None


def _get_client() -> documentai.DocumentProcessorServiceClient:
    """Lazy singleton, shared across every call and every thread in the
    ThreadPoolExecutor. A fresh DocumentProcessorServiceClient() used to be
    constructed per call — under concurrent extraction that meant several
    threads creating new gRPC channels at once, which crashed the whole
    process with a native (non-Python, unrecoverable) abort in gRPC's
    c-ares DNS resolver: "Check failed: channel_ != nullptr". A single
    client's channel is safe to use concurrently from multiple threads;
    it's concurrently *creating* several that isn't."""
    global _client
    if _client is None:
        _client = documentai.DocumentProcessorServiceClient(
            client_options=ClientOptions(api_endpoint=f"{settings.gcp_location}-documentai.googleapis.com")
        )
    return _client


@dataclass
class ExtractionResult:
    text: str
    entities: dict[str, str] = field(default_factory=dict)  # type_ -> first mention_text
    raw_entities: list[dict] = field(default_factory=list)  # every entity, with confidence


def process_bytes(content: bytes, mime_type: str, processor_id: str) -> ExtractionResult:
    """Send raw document bytes to the given Document AI processor and parse the response."""
    client = _get_client()
    processor_name = client.processor_path(settings.gcp_project_id, settings.gcp_location, processor_id)

    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(content=content, mime_type=mime_type),
    )
    document = client.process_document(request=request).document

    entities: dict[str, str] = {}
    raw_entities: list[dict] = []
    for entity in document.entities:
        value = entity.normalized_value.text if entity.normalized_value.text else entity.mention_text
        raw_entities.append(
            {"type": entity.type_, "value": value, "mention_text": entity.mention_text, "confidence": entity.confidence}
        )
        entities.setdefault(entity.type_, value)

    return ExtractionResult(text=document.text, entities=entities, raw_entities=raw_entities)


def extract_text_bytes(content: bytes, mime_type: str) -> str:
    """Send raw document bytes to the default OCR processor and return just the text."""
    return process_bytes(content, mime_type, settings.gcp_processor_id).text


def extract_text(file_path: str | Path) -> str:
    """Send the file at file_path to the default OCR processor and return its extracted text."""
    path = Path(file_path)
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type is None:
        raise ValueError(f"could not determine mime type for {path.name}")
    return extract_text_bytes(path.read_bytes(), mime_type)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m penta.docai <path-to-document>")
        raise SystemExit(1)
    print(extract_text(sys.argv[1]))
