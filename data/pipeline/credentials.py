"""Read one explicitly selected NTA credential without shell evaluation."""
from __future__ import annotations

import os
from pathlib import Path
import shlex


def load_nta_api_key(env_file: str | Path | None = None) -> str:
    """Environment wins; otherwise read only NTA_API_KEY from an explicit file.

    Supports a single literal assignment, optional `export`, quotes and comments.
    Variable interpolation, multiline values and shell evaluation are not supported.
    Never include the credential or an input line in an error message.
    """
    key = os.environ.get("NTA_API_KEY", "")
    if not key and env_file is not None:
        values = []
        for line in Path(env_file).read_text(encoding="utf-8-sig").splitlines():
            text = line.strip()
            if text.startswith("export "):
                text = text[7:].lstrip()
            name, separator, value = text.partition("=")
            if not separator or name.strip() != "NTA_API_KEY":
                continue
            try:
                words = shlex.split(value, comments=True, posix=True)
            except ValueError:
                raise ValueError("Malformed NTA_API_KEY assignment in environment file") from None
            if len(words) > 1:
                raise ValueError("NTA_API_KEY must be a single literal value")
            values.append(words[0] if words else "")
        if len(values) > 1:
            raise ValueError("Multiple NTA_API_KEY assignments in environment file")
        key = values[0] if values else ""
    if not key:
        raise ValueError("NTA_API_KEY is required; set it in the environment or use --env-file")
    if len(key) > 4096 or not key.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise ValueError("NTA_API_KEY must be a nonempty printable value without whitespace")
    return key
