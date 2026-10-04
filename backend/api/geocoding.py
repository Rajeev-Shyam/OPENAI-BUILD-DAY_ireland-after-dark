"""User-triggered geocoding for one local API instance; no autocomplete/logging.

One process-local cache and a cross-process timestamp gate for the shared
workspace. Multiple machines must use a provider with suitable aggregate limits.
"""
from collections import OrderedDict
import json
import math
from pathlib import Path
import ssl
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi
from pydantic import BaseModel, Field

from backend.settings import settings
from data.pipeline.download import atomic_write
from data.pipeline.gtfs_realtime import _request_lock

GATE_DIR = Path(__file__).resolve().parents[2] / '.cache' / 'geocoding'
_cache = OrderedDict()
_mutex = threading.Lock()


class PlaceQuery(BaseModel):
    query: str = Field(min_length=2, max_length=200)


def search(query):
    query = ' '.join(query.split())
    if len(query) < 2:
        raise ValueError('Enter a place name or coordinates.')
    cache_key = query.casefold()
    with _mutex:
        if cache_key in _cache:
            _cache.move_to_end(cache_key)
            return _cache[cache_key]
        GATE_DIR.mkdir(parents=True, exist_ok=True)
        with _request_lock(GATE_DIR / 'request.lock'):
            stamp = GATE_DIR / 'last-request.json'
            previous = json.loads(stamp.read_text())['time'] if stamp.exists() else 0
            delay = max(0, 1.1 - (time.time() - previous))
            if not math.isfinite(delay) or delay > 5:
                raise ValueError('Place search clock changed; try again later.')
            time.sleep(delay)
            atomic_write(stamp, json.dumps({'time': time.time()}).encode())
            url = settings.geocoding_url + '?' + urlencode({'format': 'json', 'countrycodes': 'ie', 'limit': 1, 'q': query})
            request = Request(url, headers={'Accept': 'application/json',
                'User-Agent': 'IrelandAfterDark/0.1 (https://github.com/Rajeev-Shyam/ireland-after-dark)'})
            try:
                with urlopen(request, timeout=10, context=ssl.create_default_context(cafile=certifi.where())) as response:
                    body = response.read(128 * 1024 + 1)
                if len(body) > 128 * 1024:
                    raise ValueError()
                matches = json.loads(body)
                if not isinstance(matches, list):
                    raise ValueError()
                result = None
                if matches:
                    item = matches[0]
                    lon, lat = float(item['lon']), float(item['lat'])
                    if not (-11 <= lon <= -5 and 51 <= lat <= 56):
                        raise ValueError()
                    result = {'coordinates': [lon, lat], 'label': str(item['display_name']),
                              'attribution': 'OpenStreetMap contributors, ODbL; Nominatim'}
            except Exception:
                raise ValueError('Place search is unavailable. Enter latitude, longitude instead.') from None
        _cache[cache_key] = result
        if len(_cache) > 256:
            _cache.popitem(last=False)
        return result
