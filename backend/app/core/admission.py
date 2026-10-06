"""Process-local inference admission; discovered provider limits are metadata only."""
from collections import deque
from threading import Lock
from time import monotonic

from app.core.errors import ErrorCategory, RouterException


class Reservation:
    def __init__(self, owner, state, event):
        self._owner, self._state, self._event = owner, state, event
        self._finished = False

    def finish(self, actual_tokens: int | None = None):
        with self._owner._lock:
            if self._finished:
                return
            self._finished = True
            self._state['active'] -= 1
            if actual_tokens is not None:
                self._event[1] = max(0, actual_tokens)


class Admission:
    # ponytail: process-local lock/window; use DB/Redis for multiple workers.
    # Fail closed at the memory ceiling: never evict active or unexpired budgets.
    _MAX_ENTRIES = 100_000

    def __init__(self):
        self._lock = Lock()
        self._states = {}

    @staticmethod
    def _deny(message, retry_after=60.0):
        raise RouterException(message, ErrorCategory.RATE_LIMIT, status_code=429,
                              retry_after=max(1.0, retry_after), raw_error={'local_admission': True})

    def reserve(self, namespace: str, subject_id: int, *, rpm=None, tpm=None,
                concurrency=None, tokens: int = 0) -> Reservation:
        now = monotonic()
        with self._lock:
            entries = 0
            for key, state in list(self._states.items()):
                while state['events'] and state['events'][0][0] <= now - 60:
                    state['events'].popleft()
                if not state['events'] and not state['active']:
                    del self._states[key]
                else:
                    entries += 1 + len(state['events'])
            key = (namespace, subject_id)
            state = self._states.get(key)
            events = state['events'] if state else ()
            retry = max(1.0, events[0][0] + 60 - now) if events else 60.0
            if concurrency is not None and (state['active'] if state else 0) >= concurrency:
                self._deny('Local concurrency limit exceeded', 1)
            if rpm is not None and len(events) >= rpm:
                self._deny('Local requests-per-minute limit exceeded', retry)
            if tpm is not None and sum(e[1] for e in events) + max(0, tokens) > tpm:
                self._deny('Local tokens-per-minute limit exceeded', retry)
            if entries + (1 if state else 2) > self._MAX_ENTRIES:
                self._deny('Local admission capacity exceeded')
            if state is None:
                state = {'events': deque(), 'active': 0}
                self._states[key] = state
            event = [now, max(0, tokens)]
            state['events'].append(event)
            state['active'] += 1
            return Reservation(self, state, event)


admission = Admission()
