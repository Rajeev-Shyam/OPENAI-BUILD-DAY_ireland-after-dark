"""Serve local, verified NTA snapshots. Browser requests never call NTA."""
import hashlib
import json
from pathlib import Path
import time

from data.pipeline.gtfs_realtime import MAX_BYTES, normalize_feed

DATA = Path(__file__).resolve().parents[2] / 'data'


def stops():
    document = json.loads((DATA / 'processed/luas-stops.geojson').read_text(encoding='utf-8'))
    manifest = json.loads((DATA / 'raw/nta/nta_gtfs_luas.manifest.json').read_text(encoding='utf-8'))
    if document.get('type') != 'FeatureCollection' or document['metadata']['archive_sha256'] != manifest['sha256']:
        raise ValueError('Stop snapshot provenance mismatch')
    document['metadata'].update({'fetched_at_utc': manifest['fetched_at_utc'],
        'http_last_modified': manifest.get('http_last_modified'),
        'attribution': 'National Transport Authority, CC BY 4.0. Data provided as is; NTA is not responsible for errors or inaccuracies.'})
    return document


def realtime_status():
    root = DATA / 'raw/nta-realtime'
    manifest_path = root / 'trip_updates.manifest.json'
    if not manifest_path.exists():
        return {'status': 'missing', 'received_at_unix': None, 'age_seconds': None,
                'message': 'No accepted realtime snapshot is available.'}
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    path = (root / manifest['snapshot']).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Invalid realtime snapshot path')
    with path.open('rb') as handle:
        body = handle.read(MAX_BYTES + 1)
    if len(body) != manifest['bytes'] or hashlib.sha256(body).hexdigest() != manifest['sha256']:
        raise ValueError('Realtime snapshot checksum mismatch')
    feed = normalize_feed(body, now=time.time())
    return {**feed['feed_freshness'], 'received_at_unix': manifest['received_at_unix'],
            'observed_trip_updates': len(feed['trip_updates']),
            'message': 'Saved NTA snapshot; not automatic live tracking. Missing updates do not mean on time.'}
