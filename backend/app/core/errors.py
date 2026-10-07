from enum import Enum
from typing import Any, Optional
import httpx
import json

class ErrorCategory(str, Enum):
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    UPSTREAM_5XX = "UPSTREAM_5XX"
    INVALID_REQUEST = "INVALID_REQUEST"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    CONTEXT_LIMIT = "CONTEXT_LIMIT"
    CONTENT_POLICY = "CONTENT_POLICY"
    UNKNOWN = "UNKNOWN"

    @property
    def is_retryable(self) -> bool:
        return self in (
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.TIMEOUT,
            ErrorCategory.NETWORK_ERROR,
            ErrorCategory.UPSTREAM_5XX,
        )

    @property
    def is_fallback_eligible(self) -> bool:
        # Fallback should occur when upstream provider fails or limits, but NOT when the user sent an invalid request!
        return self in (
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.TIMEOUT,
            ErrorCategory.NETWORK_ERROR,
            ErrorCategory.UPSTREAM_5XX,
            ErrorCategory.MODEL_NOT_FOUND,
        )

    @property
    def default_http_status(self) -> int:
        match self:
            case ErrorCategory.AUTH_ERROR:
                return 401
            case ErrorCategory.RATE_LIMIT:
                return 429
            case ErrorCategory.TIMEOUT:
                return 504
            case ErrorCategory.NETWORK_ERROR:
                return 502
            case ErrorCategory.UPSTREAM_5XX:
                return 502
            case ErrorCategory.INVALID_REQUEST:
                return 400
            case ErrorCategory.MODEL_NOT_FOUND:
                return 404
            case ErrorCategory.CONTEXT_LIMIT:
                return 400
            case ErrorCategory.CONTENT_POLICY:
                return 400
            case _:
                return 500

class RouterException(Exception):
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        status_code: Optional[int] = None,
        upstream_status: Optional[int] = None,
        retry_after: Optional[float] = None,
        raw_error: Optional[Any] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.status_code = status_code or category.default_http_status
        self.upstream_status = upstream_status
        self.retry_after = retry_after
        self.raw_error = raw_error
        self.request_id = request_id

    def to_openai_dict(self, request_id: Optional[str] = None) -> dict:
        req_id = request_id or self.request_id or "req_unknown"
        return {
            "error": {
                "message": self.message,
                "type": f"router_{self.category.value.lower()}",
                "code": self.category.value.lower(),
                "request_id": req_id,
            }
        }

def normalize_upstream_error(
    status_code: Optional[int] = None,
    response_body: Optional[Any] = None,
    exception: Optional[Exception] = None,
    retry_after: Optional[float] = None,
) -> RouterException:
    """Normalize any upstream HTTP status code, response body, or Python exception into RouterException."""
    if exception is not None:
        if isinstance(exception, (httpx.TimeoutException, TimeoutError)):
            return RouterException(
                message=f"Upstream request timed out: {type(exception).__name__}",
                category=ErrorCategory.TIMEOUT,
                status_code=504,
                raw_error=str(exception)
            )
        if isinstance(exception, (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError)):
            return RouterException(
                message=f"Network error connecting to upstream: {type(exception).__name__}",
                category=ErrorCategory.NETWORK_ERROR,
                status_code=502,
                raw_error=str(exception)
            )

    # Parse response body message if available
    err_msg = ""
    if isinstance(response_body, dict):
        if "error" in response_body:
            err = response_body["error"]
            if isinstance(err, dict):
                err_msg = err.get("message", "")
            elif isinstance(err, str):
                err_msg = err
        elif "message" in response_body:
            err_msg = str(response_body["message"])
        elif "detail" in response_body:
            err_msg = str(response_body["detail"])
    elif isinstance(response_body, str):
        try:
            parsed = json.loads(response_body)
            if isinstance(parsed, dict) and "error" in parsed:
                err_val = parsed["error"]
                err_msg = err_val.get("message", "") if isinstance(err_val, dict) else str(err_val)
            else:
                err_msg = response_body[:300]
        except Exception:
            err_msg = response_body[:300]

    if not err_msg and exception is not None:
        err_msg = str(exception)

    category = ErrorCategory.UNKNOWN
    if status_code is not None:
        if status_code == 401:
            category = ErrorCategory.AUTH_ERROR
            if not err_msg:
                err_msg = "Upstream authentication failed (invalid API key or unauthorized)"
        elif status_code == 402:
            # Provider billing failure; another candidate can still serve the request.
            category = ErrorCategory.UPSTREAM_5XX
            if not err_msg:
                err_msg = "Upstream payment required (402)"
        elif status_code == 403:
            lower_msg = err_msg.lower()
            if any(kw in lower_msg for kw in (
                "credit",
                "balance",
                "quota",
                "free tier",
                "capacity",
                "billing",
                "payment",
                "region",
                "country",
                "territory",
                "unsupported",
                "error from provider",
                "provider error",
            )):
                category = ErrorCategory.UPSTREAM_5XX
            else:
                category = ErrorCategory.AUTH_ERROR
            if not err_msg:
                err_msg = "Upstream authentication failed or access forbidden (403)"
        elif status_code == 429:
            category = ErrorCategory.RATE_LIMIT
            if not err_msg:
                err_msg = "Upstream rate limit exceeded (429)"
        elif status_code == 404:
            category = ErrorCategory.MODEL_NOT_FOUND
            if not err_msg:
                err_msg = "Upstream model or resource not found (404)"
        elif status_code == 400:
            lower_msg = err_msg.lower()
            if "context" in lower_msg or "maximum context" in lower_msg or "too many tokens" in lower_msg:
                category = ErrorCategory.CONTEXT_LIMIT
            elif "safety" in lower_msg or "policy" in lower_msg or "content_filter" in lower_msg:
                category = ErrorCategory.CONTENT_POLICY
            elif any(kw in lower_msg for kw in (
                "error from provider",
                "provider error",
                "upstream",
                "free tier",
                "only be used in",
                "quota",
                "credit",
                "balance",
                "billing",
                "subscription",
                "plan",
                "tier",
                "payment",
                "capacity",
                "overloaded",
                "unavailable",
                "not available",
                "upgrade",
                "restricted",
                "region",
                "country",
                "territory",
                "disabled",
                "access denied",
                "permission denied",
                "not allowed",
                "forbidden",
                "temporarily",
                "suspended",
                "account",
                "console",
                "gateway",
            )):
                category = ErrorCategory.UPSTREAM_5XX
            elif any(kw in lower_msg for kw in (
                "rate limit",
                "too many requests",
                "requests per minute",
                "tokens per minute",
                "exceeded limit",
                "retry after",
            )):
                category = ErrorCategory.RATE_LIMIT
            elif any(kw in lower_msg for kw in (
                "model not found",
                "does not exist",
                "unsupported model",
                "model is not supported",
                "unknown model",
                "invalid model",
            )):
                category = ErrorCategory.MODEL_NOT_FOUND
            else:
                category = ErrorCategory.INVALID_REQUEST
            if not err_msg:
                err_msg = "Bad request sent to upstream"
        elif status_code == 408:
            category = ErrorCategory.TIMEOUT
            if not err_msg:
                err_msg = "Upstream request timeout (408)"
        elif 500 <= status_code <= 599:
            category = ErrorCategory.UPSTREAM_5XX
            if not err_msg:
                err_msg = f"Upstream service error ({status_code})"
    else:
        status_code = 500
        if not err_msg:
            err_msg = "An unexpected error occurred contacting upstream"

    return RouterException(
        message=err_msg or f"Upstream error {status_code}",
        category=category,
        upstream_status=status_code,
        retry_after=retry_after,
        raw_error=response_body,
    )
