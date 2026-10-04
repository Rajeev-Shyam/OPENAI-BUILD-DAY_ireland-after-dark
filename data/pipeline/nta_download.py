"""Stream and validate NTA GTFS archives with immutable snapshots and provenance."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
import zlib

from .download import atomic_write

REGISTRY = Path(__file__).resolve().parents[1] / 'nta-sources.json'
MAX_BYTES = 512 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 4 * 1024 * 1024 * 1024
CHUNK = 1024 * 1024
REQUIRED = {'agency.txt', 'stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt'}


def registry():
    return json.loads(REGISTRY.read_text(encoding='utf-8'))['sources']


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_zip(path, *, max_bytes=MAX_BYTES, max_uncompressed_bytes=MAX_UNCOMPRESSED_BYTES):
    """Validate bounds, paths, required tables and every CRC; never extract files.

    Table semantics are validated by gtfs before publication to routing.
    """
    if Path(path).stat().st_size > max_bytes:
        raise ValueError('Archive exceeds compressed size limit')
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(entries) > 100 or len(names) != len(set(names)):
                raise ValueError('Too many or duplicate ZIP members')
            if not REQUIRED.issubset(names) or not {'calendar.txt', 'calendar_dates.txt'}.intersection(names):
                raise ValueError('Archive lacks required GTFS tables')
            total = 0
            for entry in entries:
                p = PurePosixPath(entry.filename)
                if p.is_absolute() or len(p.parts) != 1 or '\\' in entry.filename or ':' in entry.filename or entry.is_dir():
                    raise ValueError('Unsafe or nested ZIP member')
                if entry.flag_bits & 1:
                    raise ValueError('Encrypted ZIP is unsupported')
                total += entry.file_size
                if total > max_uncompressed_bytes:
                    raise ValueError('Archive exceeds uncompressed size limit')
                if entry.filename in REQUIRED and not entry.file_size:
                    raise ValueError('Required GTFS table is empty')
            consumed = 0
            for entry in entries:
                with archive.open(entry) as handle:
                    while True:
                        chunk = handle.read(CHUNK)
                        if not chunk:
                            break
                        consumed += len(chunk)
                        if consumed > max_uncompressed_bytes:
                            raise ValueError('Archive exceeds uncompressed size limit')
            return {'members': names, 'uncompressed_bytes': total}
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, zlib.error, EOFError) as exc:
        raise ValueError('Invalid GTFS ZIP: ' + str(exc)) from exc


def copy_atomic(source, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            with Path(source).open('rb') as incoming:
                shutil.copyfileobj(incoming, handle, CHUNK)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def download_source(name, spec, output, *, refresh=False, timeout=60, attempts=3,
                    max_bytes=MAX_BYTES, max_uncompressed_bytes=MAX_UNCOMPRESSED_BYTES):
    if not re.fullmatch(r'[a-z0-9_]+', name) or Path(spec['filename']).name != spec['filename']:
        raise ValueError('Invalid source identifier or filename')
    if timeout <= 0 or attempts < 1 or max_bytes < 1 or max_uncompressed_bytes < 1:
        raise ValueError('Resource limits must be positive')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / spec['filename']
    manifest_path = output / (name + '.manifest.json')
    if not refresh and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        expected = 'snapshots/' + name + '-' + manifest['sha256'] + '.zip'
        if not re.fullmatch('[0-9a-f]{64}', manifest['sha256']) or manifest['snapshot'] != expected:
            raise ValueError('Invalid cached snapshot path')
        snapshot = output / expected
        if manifest['source_url'] != spec['url'] or file_hash(snapshot) != manifest['sha256']:
            raise ValueError('Cached source or hash mismatch; use --refresh')
        validate_zip(snapshot, max_bytes=max_bytes, max_uncompressed_bytes=max_uncompressed_bytes)
        if not target.exists() or file_hash(target) != manifest['sha256']:
            copy_atomic(snapshot, target)
        return manifest
    request = urllib.request.Request(spec['url'], headers={
        'User-Agent': 'DublinAfterDark-data/0.1', 'Accept': 'application/zip', 'Accept-Encoding': 'identity'})
    temporary = None
    try:
        for attempt in range(attempts):
            try:
                with tempfile.NamedTemporaryFile(dir=output, delete=False) as handle:
                    temporary = Path(handle.name)
                    with urllib.request.urlopen(request, timeout=timeout) as response:
                        content_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
                        if content_type not in {'application/zip', 'application/x-zip-compressed', 'application/octet-stream'}:
                            raise ValueError('Unexpected response content type: ' + content_type)
                        length = response.headers.get('Content-Length')
                        length = int(length) if length is not None else None
                        if length is not None and (length < 0 or length > max_bytes):
                            raise ValueError('Archive exceeds download size limit')
                        total = 0
                        while True:
                            chunk = response.read(min(CHUNK, max_bytes - total + 1))
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > max_bytes:
                                raise ValueError('Archive exceeds download size limit')
                            handle.write(chunk)
                        if length is not None and total != length:
                            raise ValueError('Truncated response')
                        final_url = response.geturl()
                        modified = response.headers.get('Last-Modified')
                        etag = response.headers.get('ETag')
                    handle.flush()
                    os.fsync(handle.fileno())
                break
            except (urllib.error.URLError, TimeoutError) as exc:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
                if isinstance(exc, urllib.error.HTTPError) and exc.code not in {408, 429, 500, 502, 503, 504}:
                    raise
                if attempt + 1 == attempts:
                    raise
                time.sleep(min(2 ** attempt, 4))
        metadata = validate_zip(temporary, max_bytes=max_bytes, max_uncompressed_bytes=max_uncompressed_bytes)
        digest = file_hash(temporary)
        snapshot = Path('snapshots') / (name + '-' + digest + '.zip')
        (output / snapshot).parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, output / snapshot)
        manifest = {
            'schema_version': 1, 'source': name, 'source_url': spec['url'],
            'resolved_url': final_url, 'catalogue_url': spec['catalogue_url'],
            'license': spec['license'], 'attribution': spec['attribution'],
            'fetched_at_utc': datetime.now(timezone.utc).isoformat(),
            'sha256': digest, 'bytes': total, 'content_type': content_type,
            'http_last_modified': modified, 'http_etag': etag,
            'snapshot': snapshot.as_posix(), 'filename': spec['filename'], **metadata}
        atomic_write(manifest_path, (json.dumps(manifest, indent=2) + '\n').encode())
        copy_atomic(output / snapshot, target)
        return manifest
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    sources = registry()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=list(sources), default='nta_gtfs_realtime')
    parser.add_argument('--output-dir', type=Path, default=REGISTRY.parent / 'raw' / 'nta')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    try:
        result = download_source(args.source, sources[args.source], args.output_dir, refresh=args.refresh)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, 'NTA download failed: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
