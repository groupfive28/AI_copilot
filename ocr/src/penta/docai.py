"""Call Google Cloud Document AI and parse its response.

    python -m penta.docai path/to/file.pdf

process_bytes() is processor-agnostic: point it at a plain Document OCR
processor and you get text with no entities; point it at a Custom Extractor
(or a prebuilt specialized processor, e.g. an identity-document parser) and
`entities`/`raw_entities` populate too, straight from whatever schema that
processor was trained with — this module doesn't need to know field names
in advance.
"""

from __future__ import annotations

import mimetypes
import sys
from dataclasses import dataclass, field
from pathlib import Path

from google.api_core.client_options import ClientOptions
from google.cloud import documentai

from penta.config import settings


@dataclass
class ExtractionResult:
    text: str
    entities: dict[str, str] = field(default_factory=dict)  # type_ -> first mention_text
    raw_entities: list[dict] = field(default_factory=list)  # every entity, with confidence


def process_bytes(content: bytes, mime_type: str, processor_id: str) -> ExtractionResult:
    """Send raw document bytes to the given Document AI processor and parse the response."""
    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(api_endpoint=f"{settings.gcp_location}-documentai.googleapis.com")
    )
    processor_name = client.processor_path(settings.gcp_project_id, settings.gcp_location, processor_id)

    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(content=content, mime_type=mime_type),
    )
    document = client.process_document(request=request).document

    entities: dict[str, str] = {}
    raw_entities: list[dict] = []
    for entity in document.entities:
        # normalized_value.text is Document AI's own cleaned-up value (e.g.
        # a date field printed as "01 JAN 1990" normalizes to "1990-01-01")
        # — use it when present so downstream typed columns (dates in
        # particular) get something a database will actually accept, rather
        # than whatever format happened to be printed on the document.
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
