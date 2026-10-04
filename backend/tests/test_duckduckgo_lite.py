from app.services.search.duckduckgo_lite import (
    parse_duckduckgo_lite,
    resolve_result_url,
    is_safe_public_url,
    strip_tags,
)


def test_strip_tags():
    html_sample = "<b>FastAPI</b> &amp; <i>Python</i>"
    clean = strip_tags(html_sample)
    assert clean == "FastAPI & Python"


def test_ssrf_protection():
    assert is_safe_public_url("https://example.com/search") is True
    assert is_safe_public_url("http://127.0.0.1:8000") is False
    assert is_safe_public_url("http://localhost:5173") is False
    assert is_safe_public_url("http://192.168.1.10") is False
    assert is_safe_public_url("http://10.0.0.5") is False
    assert is_safe_public_url("file:///etc/passwd") is False
    assert is_safe_public_url("javascript:alert(1)") is False


def test_resolve_result_url():
    # Direct
    assert resolve_result_url("https://docs.python.org/3/") == "https://docs.python.org/3/"
    # Wrapped in uddg redirect
    wrapped = "//duckduckgo.com/l/?uddg=https%3A%2F%2Ffastapi.tiangolo.com%2F&rut=..."
    resolved = resolve_result_url(wrapped)
    assert resolved == "https://fastapi.tiangolo.com/"


def test_parse_duckduckgo_lite():
    mock_html = """
    <table>
      <tr>
        <td>
          <a class='result-link' href='https://fastapi.tiangolo.com/'>FastAPI framework, high performance</a>
        </td>
      </tr>
      <tr>
        <td class='result-snippet'>
          FastAPI is a modern, fast (high-performance), web framework for building APIs with Python.
        </td>
      </tr>
      <tr>
        <td>
          <a class='result-link' href='https://python.org/'>Welcome to Python.org</a>
        </td>
      </tr>
      <tr>
        <td class='result-snippet'>
          The official home of the Python Programming Language.
        </td>
      </tr>
    </table>
    """
    results = parse_duckduckgo_lite(mock_html)
    assert len(results) == 2
    assert results[0]["title"] == "FastAPI framework, high performance"
    assert results[0]["url"] == "https://fastapi.tiangolo.com/"
    assert "web framework for building APIs" in results[0]["snippet"]
    assert results[1]["title"] == "Welcome to Python.org"
