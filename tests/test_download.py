import io
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from data.pipeline.download import download_source

SPEC = {'url': 'https://example.org/data.csv', 'catalogue_url': 'https://example.org',
        'filename': 'example.csv', 'required_columns': ['id', 'value'],
        'license': {'id': 'cc-by'}, 'attribution': 'Example council'}
GOOD = b'id,value\n1,2\n'


class Response(io.BytesIO):
    def __init__(self, body=GOOD, kind='text/csv', length=None):
        super().__init__(body)
        self.headers = {'Content-Type': kind, 'Content-Length': str(len(body) if length is None else length)}

    def geturl(self):
        return SPEC['url']


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def fetch(self, response=None, **kwargs):
        with patch('urllib.request.urlopen', return_value=response or Response()):
            return download_source('example', SPEC, self.output, **kwargs)

    def test_verified_snapshot_and_offline_cache(self):
        manifest = self.fetch()
        self.assertEqual(manifest['rows'], 1)
        self.assertEqual((self.output / manifest['snapshot']).read_bytes(), GOOD)
        with patch('urllib.request.urlopen', side_effect=AssertionError('Must reuse cache')):
            self.assertEqual(download_source('example', SPEC, self.output), manifest)
        (self.output / 'example.csv').write_bytes(b'broken alias')
        with patch('urllib.request.urlopen', side_effect=AssertionError('Must repair from snapshot')):
            download_source('example', SPEC, self.output)
        self.assertEqual((self.output / 'example.csv').read_bytes(), GOOD)

    def test_invalid_refresh_preserves_existing_snapshot_and_manifest(self):
        original = self.fetch()
        before = (self.output / 'example.manifest.json').read_bytes()
        for response in [Response(b'<html>Error</html>', 'text/html'),
                         Response(b'id,value\n'), Response(b'wrong,fields\n1,2\n'),
                         Response(b'id,value\n1\n'), Response(GOOD, length=999)]:
            with self.subTest(response=response), self.assertRaises(ValueError):
                self.fetch(response, refresh=True)
            self.assertEqual((self.output / 'example.csv').read_bytes(), GOOD)
            self.assertEqual((self.output / 'example.manifest.json').read_bytes(), before)
            self.assertEqual((self.output / original['snapshot']).read_bytes(), GOOD)

    def test_malformed_csv_does_not_replace_valid_cache(self):
        self.fetch()
        before = (self.output / 'example.manifest.json').read_bytes()
        with self.assertRaises(csv.Error):
            self.fetch(Response(b'id,value\n1,"unterminated'), refresh=True)
        self.assertEqual((self.output / 'example.manifest.json').read_bytes(), before)
        self.assertEqual((self.output / 'example.csv').read_bytes(), GOOD)

    def test_corrupt_cache_is_not_silently_trusted(self):
        manifest = self.fetch()
        (self.output / manifest['snapshot']).write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.fetch()

    def test_non_retryable_http_failure_leaves_good_cache(self):
        self.fetch()
        with patch('urllib.request.urlopen', side_effect=HTTPError(SPEC['url'], 404, 'Missing', {}, None)) as call:
            with self.assertRaises(HTTPError):
                download_source('example', SPEC, self.output, refresh=True)
            self.assertEqual(call.call_count, 1)
        self.assertEqual((self.output / 'example.csv').read_bytes(), GOOD)

    def test_transient_http_and_network_errors_retry(self):
        failures = [HTTPError(SPEC['url'], 503, 'Retry', {}, None), URLError('temporary DNS')]
        with patch('urllib.request.urlopen', side_effect=failures + [Response()]) as call, patch('time.sleep'):
            self.assertEqual(download_source('example', SPEC, self.output)['rows'], 1)
            self.assertEqual(call.call_count, 3)

    def test_cyclists_rejected_even_with_pedestrian_header(self):
        spec = dict(SPEC, reject_cyclists=True)
        response = Response(b'id,value,Some Cyclist IN\n1,2,3\n')
        with patch('urllib.request.urlopen', return_value=response), self.assertRaisesRegex(ValueError, 'Cyclist'):
            download_source('example', spec, self.output)
        self.assertFalse((self.output / 'example.manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
