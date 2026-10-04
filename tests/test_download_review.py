"""Independent acquisition review: preserve good data across network failures."""
import io
from unittest.mock import patch

import pytest

from data.pipeline.download import download_source, validate_csv


SPEC = {"url": "https://example.org/data.csv", "catalogue_url": "https://example.org",
        "filename": "example.csv", "required_columns": ["id", "value"],
        "license": {"id": "cc-by"}, "attribution": "Example council"}
GOOD = b"id,value\n1,2\n"


class Response(io.BytesIO):
    def __init__(self, body=GOOD):
        super().__init__(body)
        self.headers = {"Content-Type": "text/csv"}

    def geturl(self):
        return SPEC["url"]


@pytest.mark.parametrize("body", [b"id,value,value\n1,2,3\n", b"id,value,\n1,2,3\n"])
def test_ambiguous_or_empty_header_rejected(body):
    with pytest.raises(ValueError):
        validate_csv(body, SPEC, "text/csv")


def test_timeout_exhaustion_preserves_authoritative_cache(tmp_path):
    with patch("urllib.request.urlopen", return_value=Response()):
        manifest = download_source("example", SPEC, tmp_path)
    manifest_before = (tmp_path / "example.manifest.json").read_bytes()
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")) as request, patch("time.sleep"):
        with pytest.raises(TimeoutError):
            download_source("example", SPEC, tmp_path, refresh=True, attempts=2)
        assert request.call_count == 2
    assert (tmp_path / "example.manifest.json").read_bytes() == manifest_before
    assert (tmp_path / manifest["snapshot"]).read_bytes() == GOOD
    assert (tmp_path / "example.csv").read_bytes() == GOOD


def test_stream_without_length_cannot_exceed_size_limit(tmp_path):
    with patch("data.pipeline.download.MAX_BYTES", 10), patch("urllib.request.urlopen", return_value=Response(GOOD)):
        with pytest.raises(ValueError, match="size limit"):
            download_source("example", SPEC, tmp_path)
    assert not (tmp_path / "example.manifest.json").exists()


def test_unverified_alias_is_not_treated_as_cache(tmp_path):
    (tmp_path / "example.csv").write_bytes(GOOD)
    with patch("urllib.request.urlopen", side_effect=TimeoutError("offline")):
        with pytest.raises(TimeoutError):
            download_source("example", SPEC, tmp_path, attempts=1)
    assert not (tmp_path / "example.manifest.json").exists()
