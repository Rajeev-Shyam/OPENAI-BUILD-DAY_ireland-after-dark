"""Independent failure-path review of authenticated transport acquisition."""
import pytest
from data.pipeline import gtfs_realtime as rt


def test_untrusted_content_length_does_not_escape_in_error(tmp_path, monkeypatch):
    class Response:
        headers = {'Content-Type': 'application/x-protobuf', 'Content-Length': 'sensitive-upstream-text'}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def geturl(self):
            return rt.ENDPOINTS['trip_updates']
    class Opener:
        def open(self, request, timeout):
            return Response()
    monkeypatch.setattr(rt.urllib.request, 'build_opener', lambda *args: Opener())
    with pytest.raises(ValueError) as error:
        rt.fetch_snapshot(tmp_path, api_key='synthetic-key')
    assert 'sensitive-upstream-text' not in str(error.value)
    assert not (tmp_path / 'trip_updates.manifest.json').exists()
