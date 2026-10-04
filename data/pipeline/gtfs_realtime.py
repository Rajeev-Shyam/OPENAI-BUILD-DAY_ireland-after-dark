"""NTA authenticated GTFS-RT snapshots. No prediction or routing inference."""
import argparse
from contextlib import contextmanager
import hashlib
import http.client
import json
import math
import os
import ssl
from pathlib import Path
import time
import urllib.error
import urllib.request

import certifi

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError
from google.protobuf.unknown_fields import UnknownFieldSet
from google.transit import gtfs_realtime_pb2

from .download import atomic_write

ENDPOINTS = {
    'trip_updates': 'https://api.nationaltransport.ie/gtfsr/v2/TripUpdates',
    'vehicles': 'https://api.nationaltransport.ie/gtfsr/v2/Vehicles',
}
MAX_BYTES = 20 * 1024 * 1024


@contextmanager
def _request_lock(path):
    """OS-backed lock shared by processes; failure never permits a request.

    Windows locks byte zero (even for an empty file); POSIX locks the file.
    Keep this inode/path stable: deleting the lock file would break exclusion.
    """
    with Path(path).open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def freshness(timestamp, now, max_age_seconds=90):
    """Consumer policy: absent/future timestamps cannot establish fresh data."""
    if timestamp is None:
        return {'status': 'unknown', 'age_seconds': None}
    age = now - int(timestamp)
    return {'status': 'future' if age < 0 else 'stale' if age > max_age_seconds else 'fresh',
            'age_seconds': age}


def _reject_unknown_fields(message):
    """Fail closed for wire fields/enums absent from our pinned protobuf schema.

    Proto2 preserves unknown enum numbers in unknown fields but reading the
    enum yields its default. Without this check NEW/DELETED could look SCHEDULED.
    Rejecting unknown fields also deliberately rejects unsupported extensions.
    """
    if list(UnknownFieldSet(message)):
        raise ValueError('Unsupported GTFS-RT wire fields or enum values; update the pinned schema')
    for field, value in message.ListFields():
        if field.message_type is not None:
            if field.is_repeated:
                for child in value:
                    _reject_unknown_fields(child)
            else:
                _reject_unknown_fields(value)


def normalize_feed(body, *, now=None, max_age_seconds=90):
    """Preserve optional-field absence and GTFS IDs; never turn absence into zero.

    Freshness is assessed at normalization time and MUST be assessed again by a
    later consumer. Entity timestamps cannot be inferred from the header.
    Differential snapshots are rejected: this pipeline does not maintain state.
    """
    now = time.time() if now is None else now
    if not math.isfinite(now) or not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
        raise ValueError('Finite time and positive max_age_seconds required')
    if not body or len(body) > MAX_BYTES:
        raise ValueError('Empty or oversized GTFS-RT body')
    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(body)
    except DecodeError:
        raise ValueError('Invalid GTFS-RT protobuf') from None
    _reject_unknown_fields(feed)
    if not feed.IsInitialized():
        raise ValueError('GTFS-RT required protobuf fields are missing')
    if feed.header.gtfs_realtime_version not in {'1.0', '2.0'}:
        raise ValueError('Unsupported GTFS-RT version')
    if feed.header.incrementality != gtfs_realtime_pb2.FeedHeader.FULL_DATASET:
        raise ValueError('DIFFERENTIAL feeds require a stateful merger; unsupported')
    header = MessageToDict(feed.header, preserving_proto_field_name=True)
    stamp = int(header['timestamp']) if 'timestamp' in header else None
    result = {
        'schema_version': 1, 'assessed_at_unix': now,
        'freshness_policy_seconds': max_age_seconds,
        'header': header, 'feed_freshness': freshness(stamp, now, max_age_seconds),
        'trip_updates': [], 'vehicle_positions': [], 'alerts': [],
        'unsupported_entities': [],
        'coverage': 'observed_entities_only; absence_is_unknown',
    }
    seen = set()
    for entity in feed.entity:
        if not entity.id or entity.id in seen:
            raise ValueError('Blank or duplicate GTFS-RT entity identifier')
        seen.add(entity.id)
        if entity.HasField('is_deleted'):
            raise ValueError('is_deleted is not valid in FULL_DATASET')
        present = [name for name in ('trip_update', 'vehicle', 'alert') if entity.HasField(name)]
        if len(present) > 1:
            raise ValueError('Multiple payloads in one GTFS-RT entity')
        if not present:
            result['unsupported_entities'].append(MessageToDict(entity, preserving_proto_field_name=True))
            continue
        name = present[0]
        payload = MessageToDict(getattr(entity, name), preserving_proto_field_name=True)
        if name == 'trip_update':
            sequences = [s['stop_sequence'] for s in payload.get('stop_time_update', []) if 'stop_sequence' in s]
            if sequences != sorted(set(sequences)):
                raise ValueError('Stop updates must have increasing unique stop_sequence')
            for stop in payload.get('stop_time_update', []):
                if not stop.get('stop_id') and 'stop_sequence' not in stop:
                    raise ValueError('Stop update lacks stop_id and stop_sequence')
        if name == 'vehicle' and 'position' in payload:
            pos = payload['position']
            lat, lon = pos['latitude'], pos['longitude']
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError('Invalid vehicle coordinates')
        measurement_stamp = int(payload['timestamp']) if 'timestamp' in payload else None
        state = freshness(measurement_stamp, now, max_age_seconds)
        # Alerts have no observation timestamp in GTFS-RT: header freshness is
        # tracked separately; active_period is preserved, never asserted active.
        item = {'entity_id': entity.id, 'data': payload, 'observation_freshness': state,
                'usable_as_current_observation': result['feed_freshness']['status'] == 'fresh' and state['status'] == 'fresh'}
        result[{'trip_update': 'trip_updates', 'vehicle': 'vehicle_positions', 'alert': 'alerts'}[name]].append(item)
    return result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('NTA redirect refused; authentication header was not forwarded')


def fetch_snapshot(output, *, endpoint='trip_updates', api_key=None, timeout=30,
                   max_age_seconds=90):
    """Fetch once, normalize, atomically publish manifest last. No cache fallback.

    Request gate is shared across both endpoints within output. All clients using
    the same key must share this directory (external clients remain caller-owned).
    Errors never expose upstream text, request headers, or credentials.
    """
    if endpoint not in ENDPOINTS:
        raise ValueError('Unknown NTA endpoint')
    key = os.environ.get('NTA_API_KEY') if api_key is None else api_key
    if key is None or key == '':
        raise ValueError('Set NTA_API_KEY from the NTA developer portal')
    if not isinstance(key, str) or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise ValueError('Invalid API key header')
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Positive timeout required')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Lock covers gate read/write only, then records failed requests too.
    with _request_lock(output / '.request.lock'):
        gate = output / '.last-request.json'
        now = time.time()
        if gate.exists():
            previous = json.loads(gate.read_text())['requested_at_unix']
            if not isinstance(previous, (int, float)) or not math.isfinite(previous):
                raise ValueError('Invalid NTA request gate; refusing request')
            if now - previous < 60:
                raise ValueError('NTA fair usage: wait at least 60 seconds between requests across endpoints')
        atomic_write(gate, json.dumps({'requested_at_unix': now}).encode())
    request = urllib.request.Request(ENDPOINTS[endpoint], headers={
        'x-api-key': key, 'Accept': 'application/x-protobuf',
        'User-Agent': 'DublinAfterDark-data/0.1', 'Accept-Encoding': 'identity'})
    # Explicit Mozilla roots also work on Windows hosts with incomplete OS roots.
    # Certificate and hostname verification remain enabled.
    opener = urllib.request.build_opener(
        _NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())))
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.geturl() != ENDPOINTS[endpoint]:
                raise ValueError('Unexpected NTA response URL')
            content_type = response.headers.get('Content-Type', '').split(';')[0].lower().strip()
            if content_type not in {'application/x-protobuf', 'application/octet-stream', 'application/protobuf', 'application/vnd.google.protobuf'}:
                raise ValueError('NTA response is not a protobuf content type')
            if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                raise ValueError('Unexpected NTA content encoding')
            length = response.headers.get('Content-Length')
            if length is not None:
                try:
                    length = int(length)
                    if length < 0:
                        raise ValueError
                except (TypeError, ValueError):
                    raise ValueError('Invalid NTA Content-Length header') from None
            if length is not None and length > MAX_BYTES:
                raise ValueError('NTA response exceeds size limit')
            body = response.read(MAX_BYTES + 1)
            if length is not None and len(body) != length:
                raise ValueError('NTA response Content-Length mismatch')
    except urllib.error.HTTPError as exc:
        raise ValueError('NTA HTTP error %s; check subscription, access and rate limits' % exc.code) from None
    except (urllib.error.URLError, OSError, http.client.HTTPException):
        raise ValueError('NTA network request failed') from None
    received = time.time()
    normalized = normalize_feed(body, now=received, max_age_seconds=max_age_seconds)
    digest = hashlib.sha256(body).hexdigest()
    snapshot = 'snapshots/%s.pb' % digest
    normalized_name = 'snapshots/%s-%s.json' % (digest, time.time_ns())
    manifest = {'schema_version': 1, 'source_url': ENDPOINTS[endpoint],
                'endpoint': endpoint, 'received_at_unix': received, 'sha256': digest,
                'bytes': len(body), 'content_type': content_type, 'snapshot': snapshot,
                'normalized': normalized_name,
                'feed_freshness': normalized['feed_freshness'],
                'assessed_at_unix': received,
                'attribution': 'National Transport Authority, CC BY 4.0; data provided as is'}
    atomic_write(output / snapshot, body)
    atomic_write(output / normalized_name, json.dumps(normalized, indent=2).encode())
    atomic_write(output / (endpoint + '.manifest.json'), json.dumps(manifest, indent=2).encode())
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    fetch = sub.add_parser('fetch')
    fetch.add_argument('--output', type=Path, required=True)
    fetch.add_argument('--endpoint', choices=ENDPOINTS, default='trip_updates')
    fetch.add_argument('--env-file', type=Path)
    normalize = sub.add_parser('normalize')
    normalize.add_argument('--input', type=Path, required=True)
    normalize.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'fetch':
            from .credentials import load_nta_api_key
            print(json.dumps(fetch_snapshot(args.output, endpoint=args.endpoint,
                                            api_key=load_nta_api_key(args.env_file)), indent=2))
        else:
            if args.input.resolve() == args.output.resolve():
                raise ValueError('Output must not overwrite the raw protobuf input')
            with args.input.open('rb') as source:
                result = normalize_feed(source.read(MAX_BYTES + 1))
            atomic_write(args.output, json.dumps(result, indent=2).encode())
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
