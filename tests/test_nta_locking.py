"""Real spawned processes, shared gate, no upstream requests."""
import multiprocessing
import urllib.error
from unittest.mock import patch

import pytest

from data.pipeline import gtfs_realtime as rt


def _fetch_worker(output, endpoint, start, results):
    start.wait(10)
    def fail_request(*args, **kwargs):
        results.put('attempted')
        raise urllib.error.URLError('synthetic failure')
    with patch.object(rt.urllib.request.OpenerDirector, 'open', fail_request):
        try:
            rt.fetch_snapshot(output, endpoint=endpoint, api_key='synthetic-key')
        except ValueError as exc:
            results.put('gated' if '60 seconds' in str(exc) else 'failed')


def test_cross_process_gate_includes_failed_requests_and_both_endpoints(tmp_path):
    ctx = multiprocessing.get_context('spawn')
    start, results = ctx.Event(), ctx.Queue()
    workers = [ctx.Process(target=_fetch_worker, args=(str(tmp_path), ep, start, results))
               for ep in ('trip_updates', 'vehicles')]
    try:
        for worker in workers:
            worker.start()
        start.set()
        observed = [results.get(timeout=20) for _ in range(3)]
        for worker in workers:
            worker.join(20)
            assert worker.exitcode == 0
        assert sorted(observed) == ['attempted', 'failed', 'gated']
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
        results.close()


def test_lock_releases_after_exception(tmp_path):
    lock = tmp_path / '.request.lock'
    with pytest.raises(RuntimeError):
        with rt._request_lock(lock):
            raise RuntimeError('synthetic')
    with rt._request_lock(lock):
        pass


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '"invalid"'])
def test_invalid_gate_fails_closed(tmp_path, value):
    (tmp_path / '.last-request.json').write_text('{"requested_at_unix":' + value + '}')
    with patch.object(rt.urllib.request, 'build_opener') as opener:
        with pytest.raises(ValueError, match='Invalid NTA request gate'):
            rt.fetch_snapshot(tmp_path, api_key='synthetic-key')
        opener.assert_not_called()
