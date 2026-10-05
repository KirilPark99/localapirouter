"""Bound untrusted custom regexes; built-in patterns use normal re.

ponyTail: one short-lived worker per custom rule; a pool only if measured
custom-rule volume justifies it. Call this synchronous API via to_thread
from async request paths so a slow rule cannot stall the event loop.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

MAX_PATTERN_CHARS = 512
MAX_INPUT_BYTES = 524288
MAX_OUTPUT_BYTES = 2097152
TIMEOUT_SECONDS = 0.25


def _run(operation: str, pattern: str, text: str = "", replacement: str = "", flags: int = 0):
    if not isinstance(pattern, str) or not pattern or len(pattern) > MAX_PATTERN_CHARS:
        raise ValueError("Custom regex must be a non-empty string of at most 512 characters")
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_INPUT_BYTES:
        raise ValueError("Custom regex input exceeds 512 KiB")
    if not isinstance(replacement, str) or len(replacement) > 4096:
        raise ValueError("Custom regex replacement exceeds 4096 characters")
    request = json.dumps([operation, pattern, text, replacement, int(flags)])
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            input=request, text=True, capture_output=True, timeout=TIMEOUT_SECONDS,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Custom regex exceeded its execution deadline") from exc
    if result.returncode or len(result.stdout.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ValueError("Custom regex exceeded its resource limits")
    try:
        response = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise ValueError("Custom regex worker failed") from exc
    if "error" in response:
        raise ValueError(response["error"])
    return response["result"]


def validate_pattern(pattern: str) -> None:
    _run("compile", pattern)


def subn(pattern: str, replacement: str, text: str, flags: int = 0):
    value, count = _run("subn", pattern, text, replacement, flags)
    return value, count


def search(pattern: str, text: str, flags: int = 0):
    """Return None or {match: str, span: [start, end]}, not a re.Match."""
    return _run("search", pattern, text, flags=flags)


def _worker():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
        resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
        operation, pattern, text, replacement, flags = json.load(sys.stdin)
        compiled = re.compile(pattern, flags)
        if operation == "compile":
            value = None
        elif operation == "subn":
            value = compiled.subn(replacement, text)
        elif operation == "search":
            match = compiled.search(text)
            value = None if match is None else {"match": match.group(0), "span": list(match.span())}
        else:
            raise ValueError("Unknown custom regex operation")
        encoded = json.dumps({"result": value})
        if len(encoded.encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise ValueError("Custom regex output exceeds 2 MiB")
        print(encoded)
    except Exception:
        # Do not echo patterns or payloads: they can contain user secrets.
        print(json.dumps({"error": "Invalid custom regex or replacement"}))


if __name__ == "__main__":
    _worker()
