"""Pinned, validated public-source acquisition with content-addressed provenance."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.request

REGISTRY = Path(__file__).resolve().parents[1] / 'sources.json'
MAX_BYTES = 100 * 1024 * 1024


def registry():
    return json.loads(REGISTRY.read_text(encoding='utf-8'))['sources']


def validate_csv(body, spec, content_type):
    if content_type.split(';')[0].strip().lower() not in {
        'text/csv', 'application/csv', 'text/plain', 'application/octet-stream',
        'application/vnd.ms-excel',
    }:
        raise ValueError('Unexpected response content type: ' + content_type)
    text = body.decode('utf-8-sig')
    if not text.strip() or text.lstrip().lower().startswith(('<!doctype', '<html')):
        raise ValueError('Empty or HTML response is not a dataset')
    rows = csv.reader(io.StringIO(text), strict=True)
    header = next(rows)
    if any(not name.strip() for name in header) or len(set(header)) != len(header):
        raise ValueError("Blank or duplicate CSV column names")
    required = spec['required_columns']
    if not set(required).issubset(header):
        raise ValueError('Missing required CSV columns: ' + repr(sorted(set(required) - set(header))))
    if spec.get('reject_cyclists') and any('cyclist' in h.lower() or 'cyclists' in h.lower() for h in header):
        raise ValueError('Cyclist series must not be used as pedestrian counts')
    count = 0
    for row in rows:
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) != len(header):
            raise ValueError('CSV row width does not match header')
        count += 1
    if count == 0:
        raise ValueError('Dataset has no observations')
    return {'columns': header, 'rows': count}


def atomic_write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def download_source(name, spec, output, *, refresh=False, timeout=45, attempts=3):
    """Only reuse a cache when provenance, hash, and schema all agree.

    Immutable snapshots plus an atomic manifest are the authoritative pair. The
    named CSV is a convenience alias; interrupted alias updates are repaired by
    the next cache read. Validation failures never replace prior good data.
    """
    if timeout <= 0 or attempts < 1:
        raise ValueError('timeout and attempts must be positive')
    output = Path(output)
    target = output / spec['filename']
    manifest_path = output / (name + '.manifest.json')
    if not refresh and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        snapshot = output / manifest['snapshot']
        if manifest['source_url'] != spec['url']:
            raise ValueError('Cached source URL differs; use --refresh')
        body = snapshot.read_bytes()
        if hashlib.sha256(body).hexdigest() != manifest['sha256']:
            raise ValueError('Cached snapshot hash mismatch; use --refresh')
        validate_csv(body, spec, manifest['content_type'])
        if not target.exists() or target.read_bytes() != body:
            atomic_write(target, body)
        return manifest
    request = urllib.request.Request(spec['url'], headers={'User-Agent': 'DublinAfterDark-data/0.1', 'Accept': 'text/csv'})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content_type = response.headers.get('Content-Type', '')
                length = response.headers.get('Content-Length')
                if length and int(length) > MAX_BYTES:
                    raise ValueError('Dataset exceeds download size limit')
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError('Dataset exceeds download size limit')
                if length and len(body) != int(length):
                    raise ValueError('Truncated response')
                final_url = response.geturl()
                last_modified = response.headers.get('Last-Modified')
                etag = response.headers.get('ETag')
            break
        except urllib.error.HTTPError as error:
            if error.code not in {408, 429, 500, 502, 503, 504} or attempt + 1 == attempts:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt + 1 == attempts:
                raise
        time.sleep(min(2 ** attempt, 4))
    metadata = validate_csv(body, spec, content_type)
    digest = hashlib.sha256(body).hexdigest()
    snapshot = Path('snapshots') / (name + '-' + digest + '.csv')
    manifest = {
        'schema_version': 1, 'source': name, 'source_url': spec['url'],
        'resolved_url': final_url, 'catalogue_url': spec['catalogue_url'],
        'license': spec['license'], 'attribution': spec['attribution'],
        'fetched_at_utc': datetime.now(timezone.utc).isoformat(),
        'sha256': digest, 'bytes': len(body), 'content_type': content_type,
        'http_last_modified': last_modified, 'http_etag': etag,
        'snapshot': str(snapshot), 'filename': spec['filename'], **metadata,
    }
    atomic_write(output / snapshot, body)
    atomic_write(manifest_path, (json.dumps(manifest, indent=2) + '\n').encode())
    atomic_write(target, body)
    return manifest


def main():
    sources = registry()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=['all'] + list(sources), default='all')
    parser.add_argument('--output-dir', type=Path, default=REGISTRY.parent / 'raw')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--timeout', type=float, default=45)
    parser.add_argument('--attempts', type=int, default=3)
    args = parser.parse_args()
    selected = sources if args.source == 'all' else {args.source: sources[args.source]}
    try:
        for name, spec in selected.items():
            result = download_source(name, spec, args.output_dir, refresh=args.refresh,
                                     timeout=args.timeout, attempts=args.attempts)
            print(f"{name}: {result['rows']} rows, sha256={result['sha256']}")
    except (OSError, ValueError, KeyError, csv.Error) as error:
        parser.exit(1, f'Download failed: {error}\n')


if __name__ == '__main__':
    main()
