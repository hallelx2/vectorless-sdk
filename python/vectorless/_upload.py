from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union


def prepare_multipart_upload(
    source: Union[str, bytes, BinaryIO, Path],
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> Tuple[List[Tuple[str, Any]], Dict[str, str]]:
    """
    Prepare file upload for httpx multipart POST.

    Returns ``(files, data)`` tuple for ``httpx.post(files=files, data=data)``.
    """
    files: List[Tuple[str, Any]] = []
    data: Dict[str, str] = {}

    if isinstance(source, str):
        path = Path(source)
        resolved_name = filename or path.name
        files = [("file", (resolved_name, path.read_bytes()))]
    elif isinstance(source, Path):
        resolved_name = filename or source.name
        files = [("file", (resolved_name, source.read_bytes()))]
    elif isinstance(source, bytes):
        resolved_name = filename or "document"
        files = [("file", (resolved_name, source))]
    else:
        # BinaryIO
        name = getattr(source, "name", "document")
        if isinstance(name, str) and "/" in name:
            name = name.rsplit("/", 1)[-1]
        resolved_name = filename or name
        files = [("file", (resolved_name, source.read()))]

    if content_type:
        data["content_type"] = content_type
    if metadata:
        for key, value in metadata.items():
            data[f"metadata[{key}]"] = value

    return files, data


def prepare_json_payload(
    source: Union[str, bytes, BinaryIO, Path],
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Prepare a JSON body for document ingestion (used by Connect transport).

    Encodes the file content as base64.
    """
    if isinstance(source, str):
        path = Path(source)
        raw = path.read_bytes()
        resolved_name = filename or path.name
    elif isinstance(source, Path):
        raw = source.read_bytes()
        resolved_name = filename or source.name
    elif isinstance(source, bytes):
        raw = source
        resolved_name = filename or "document"
    else:
        raw = source.read()
        name = getattr(source, "name", "document")
        if isinstance(name, str) and "/" in name:
            name = name.rsplit("/", 1)[-1]
        resolved_name = filename or name

    return {
        "content": base64.b64encode(raw).decode("ascii"),
        "filename": resolved_name,
        "content_type": content_type or "application/octet-stream",
        "metadata": metadata or {},
    }
