from __future__ import annotations

import mimetypes
import sys
from pathlib import Path

from google.api_core.client_options import ClientOptions
from google.cloud import documentai

from penta.config import settings


def extract_text_bytes(content: bytes, mime_type: str) -> str:
    """Send raw document bytes to Document AI and return the extracted text."""
    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(api_endpoint=f"{settings.gcp_location}-documentai.googleapis.com")
    )
    processor_name = client.processor_path(settings.gcp_project_id, settings.gcp_location, settings.gcp_processor_id)

    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(content=content, mime_type=mime_type),
    )
    result = client.process_document(request=request)
    return result.document.text


def extract_text(file_path: str | Path) -> str:
    """Send the file at file_path to Document AI and return its extracted text."""
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
