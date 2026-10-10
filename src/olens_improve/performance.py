"""Opt-in operational timing; never record request content or alter accounting."""
from collections import Counter
from contextvars import ContextVar
from functools import wraps
import asyncio
import json
from pathlib import Path
import random
import sys
import time
import threading
import weakref


CURRENT_PROFILE = ContextVar('olens_operational_profile', default=None)


def profile_condition(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        output = kwargs.pop('performance_profile', None)
        if output is None: return function(*args, **kwargs)
        profile = OperationalProfile(output, metadata={
            'family': kwargs.get('family_only'), 'method': kwargs.get('method'),
            'n': kwargs.get('n'), 'concurrency': kwargs.get('concurrency',8),
            'rpm': kwargs.get('rpm',120)})
        token = CURRENT_PROFILE.set(profile); status = 'completed'
        try: return function(*args, **kwargs)
        except BaseException as exc:
            status = 'failed:'+type(exc).__name__; raise
        finally:
            CURRENT_PROFILE.reset(token)
            try:
                profile.close(status)
            except Exception as exc:
                # A measurement sidecar must never change an accounting/science
                # outcome, including the original transport exception.
                print(json.dumps({'status': 'operational_profile_write_failed',
                                  'exception_class': type(exc).__name__}),
                      file=sys.stderr, flush=True)
    return wrapped


class OperationalProfile:
    def __init__(self, output, *, heartbeat_seconds=.1, sample_limit=2048, metadata=None):
        if heartbeat_seconds <= 0 or sample_limit < 1:
            raise ValueError('Positive bounded profiling settings required')
        self.output = Path(output)
        if self.output.exists(): raise FileExistsError('Performance evidence already exists; use a new profile path')
        self.period = heartbeat_seconds
        self.limit = sample_limit
        self.metadata = {k: v for k, v in (metadata or {}).items()
                         if k in ('family', 'method', 'n', 'concurrency', 'rpm', 'offline')}
        self.metrics = {}
        self.metric_lock = threading.Lock()
        self.rng = random.Random(20261010)
        self.started = time.perf_counter()
        self.tasks = weakref.WeakKeyDictionary()
        self.patches = []

    def observe(self, name, seconds, exception=None):
        with self.metric_lock:
            stat = self.metrics.setdefault(name, {'count': 0, 'total_seconds': 0.,
                                                'maximum_seconds': 0., 'samples': [], 'errors': Counter()})
            stat['count'] += 1; stat['total_seconds'] += seconds
            stat['maximum_seconds'] = max(stat['maximum_seconds'], seconds)
            if exception is not None: stat['errors'][type(exception).__name__] += 1
            if len(stat['samples']) < self.limit: stat['samples'].append(seconds)
            else:
                index = self.rng.randrange(stat['count'])
                if index < self.limit: stat['samples'][index] = seconds

    def call(self, name, function, *args, **kwargs):
        started = time.perf_counter(); error = None
        try: return function(*args, **kwargs)
        except BaseException as exc:
            error = exc; raise
        finally: self.observe(name, time.perf_counter()-started, error)

    def wrap(self, name, function):
        @wraps(function)
        def timed(*args, **kwargs): return self.call(name, function, *args, **kwargs)
        return timed

    def attach_ledger(self, ledger):
        if getattr(ledger, '_operational_profile', None) is not None:
            raise ValueError('Ledger already has an operational profiler')
        for name in ('snapshot', 'reserve_attempt', 'reserve_attempts', 'record_evidence', 'settle', 'mark_unknown'):
            original = getattr(ledger, name)
            self.patches.append((ledger, name, original))
            setattr(ledger, name, self.wrap('ledger.'+name, original))
        ledger._operational_profile = self

    def ensure_heartbeat(self):
        loop = asyncio.get_running_loop()
        if loop in self.tasks and not self.tasks[loop].done(): return
        async def heartbeat():
            while True:
                expected = loop.time()+self.period
                await asyncio.sleep(self.period)
                self.observe('event_loop.scheduling_lag', max(0., loop.time()-expected))
        self.tasks[loop] = loop.create_task(heartbeat())

    def close(self, status):
        for task in list(self.tasks.values()):
            if not task.done(): task.cancel()
        for ledger, name, original in self.patches:
            setattr(ledger, name, original)
            ledger._operational_profile = None
        self.patches.clear()
        def quantile(samples, fraction):
            if not samples: return None
            rank = (len(samples)-1)*fraction; lo = int(rank); hi = min(lo+1,len(samples)-1)
            return samples[lo]+(samples[hi]-samples[lo])*(rank-lo)
        metrics = {}
        with self.metric_lock:
            for name, stat in self.metrics.items():
                samples = sorted(stat['samples'])
                metrics[name] = {k: v for k, v in stat.items() if k not in ('samples', 'errors')}
                metrics[name].update(sample_count=len(samples), median_seconds=quantile(samples,.5),
                                     p95_seconds=quantile(samples,.95), exception_classes=dict(stat['errors']))
        report = {'status': status, 'metadata': self.metadata,
                  'wall_seconds': time.perf_counter()-self.started,
                  'heartbeat_seconds': self.period, 'per_metric_sample_limit': self.limit,
                  'sample_policy': 'Bounded deterministic reservoir; counts/sums/maxima include every observation',
                  'metrics': metrics, 'scope': 'Operational timings only; no request content, identifiers or credentials'}
        self.output.parent.mkdir(parents=True, exist_ok=True)
        with self.output.open('x') as f: f.write(json.dumps(report,indent=2)+'\n')
        return report
