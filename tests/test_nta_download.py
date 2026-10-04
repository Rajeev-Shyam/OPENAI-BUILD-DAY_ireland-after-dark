import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import zipfile

from data.pipeline.nta_download import download_source, validate_zip, REQUIRED

SPEC = {'url': 'https://example.org/gtfs.zip', 'filename': 'gtfs.zip',
        'catalogue_url': 'https://example.org', 'license': {'id': 'CC-BY-4.0'}, 'attribution': 'NTA'}


def archive(extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in sorted(REQUIRED | {'calendar.txt'}):
            z.writestr(name, 'id,name\n1,Example\n')
        if extra:
            z.writestr(*extra)
    return stream.getvalue()


class Response(io.BytesIO):
    def __init__(self, body=None, kind='application/zip', length=None):
        body = archive() if body is None else body
        super().__init__(body)
        self.headers = {'Content-Type': kind, 'Content-Length': str(len(body) if length is None else length)}

    def geturl(self):
        return SPEC['url']


class NTADownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def fetch(self, response=None, **kwargs):
        with patch('urllib.request.urlopen', return_value=response or Response()):
            return download_source('test', SPEC, self.output, **kwargs)

    def test_roundtrip_and_repair_alias_offline(self):
        manifest = self.fetch()
        self.assertEqual(manifest['bytes'], len(archive()))
        (self.output / 'gtfs.zip').write_bytes(b'broken')
        with patch('urllib.request.urlopen', side_effect=AssertionError('network must not be used')):
            self.assertEqual(download_source('test', SPEC, self.output), manifest)
        self.assertEqual((self.output / 'gtfs.zip').read_bytes(), archive())

    def test_corrupted_cache_rejected(self):
        manifest = self.fetch()
        (self.output / manifest['snapshot']).write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.fetch()

    def test_refresh_failure_preserves_good_manifest(self):
        old = self.fetch()
        with self.assertRaises(ValueError):
            self.fetch(Response(b'<html>error</html>', 'text/html'), refresh=True)
        self.assertEqual(json.loads((self.output / 'test.manifest.json').read_text()), old)
        self.assertEqual((self.output / 'gtfs.zip').read_bytes(), archive())

    def test_size_limits_and_truncation(self):
        for response, kw in [(Response(), {'max_bytes': 10}),
                             (Response(), {'max_uncompressed_bytes': 10}),
                             (Response(length=99999), {})]:
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.fetch(response, **kw)
        self.assertFalse((self.output / 'test.manifest.json').exists())

    def test_unannounced_size_limit(self):
        response = Response()
        del response.headers['Content-Length']
        with self.assertRaisesRegex(ValueError, 'size limit'):
            self.fetch(response, max_bytes=10)

    def test_invalid_zip_members(self):
        for extra in [('../escape.txt', 'x'), ('sub/file.txt', 'x')]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.fetch(Response(archive(extra)))
        with self.assertWarnsRegex(UserWarning, 'Duplicate name'):
            duplicate = archive(('stops.txt', 'duplicate'))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.fetch(Response(duplicate))
        with self.assertRaises(ValueError):
            self.fetch(Response(b'not a ZIP'))

    def test_missing_required_members(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z:
            z.writestr('stops.txt', 'id\n1')
        with self.assertRaisesRegex(ValueError, 'required GTFS'):
            self.fetch(Response(stream.getvalue()))

    def test_retry_transient_not_auth(self):
        with patch('urllib.request.urlopen', side_effect=[URLError('temporary'), Response()]) as call, patch('time.sleep'):
            download_source('test', SPEC, self.output)
            self.assertEqual(call.call_count, 2)
        with patch('urllib.request.urlopen', side_effect=HTTPError(SPEC['url'], 401, 'unauthorized', {}, None)) as call:
            with self.assertRaises(HTTPError):
                download_source('test', SPEC, self.output, refresh=True)
            self.assertEqual(call.call_count, 1)

    def test_snapshot_path_traversal_rejected(self):
        manifest = self.fetch()
        manifest['snapshot'] = '../outside.zip'
        (self.output / 'test.manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'snapshot path'):
            self.fetch()

    def test_all_payload_crc_checked(self):
        body = bytearray(archive(('optional.txt', 'payload')))
        marker = body.find(b'optional.txt') + len(b'optional.txt') + 2
        body[marker] ^= 1
        with self.assertRaises(ValueError):
            self.fetch(Response(bytes(body)))


if __name__ == '__main__':
    unittest.main()
