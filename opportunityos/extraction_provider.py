"""Local JSON generation providers. Source posts are the only context sent."""
import json
import threading

INFERENCE = threading.BoundedSemaphore(1)
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Provider redirects are disabled")


def _generate(messages, schema, settings):
    provider = settings.get("extraction_provider", "codex")
    if provider == "codex":
        from .cloud_ai import generate as cloud_generate
        return cloud_generate(messages, schema, settings)
    endpoint = settings.get("extraction_endpoint", "http://127.0.0.1:11434").rstrip("/")
    parsed = urlsplit(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
        raise ValueError("Choose a loopback HTTP endpoint for local extraction")
    model = settings.get("extraction_model", "qwen3:4b")
    if provider == "ollama":
        url = endpoint + "/api/chat"
        body = {"model": model, "messages": messages, "stream": False, "format": schema,
                "keep_alive": 0, "think": False, "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 2600}}
    elif provider == "local_chat":
        url = endpoint + "/chat/completions"
        body = {"model": model, "messages": messages, "temperature": 0,
                "response_format": {"type": "json_schema", "json_schema": {"name": "opportunity", "strict": True, "schema": schema}}}
    else:
        raise ValueError("Unsupported extraction provider")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(url, json.dumps(body, ensure_ascii=False).encode(), {"Content-Type": "application/json"})
    with opener.open(request, timeout=settings.get("extraction_timeout", 180)) as response:
        content = response.read(500_001)
    if len(content) > 500_000:
        raise ValueError("Extraction response is too large")
    payload = json.loads(content)
    result = payload["message"]["content"] if provider == "ollama" else payload["choices"][0]["message"]["content"]
    return json.loads(result)


def generate(messages, schema, settings):
    if not INFERENCE.acquire(timeout=5):
        raise ValueError("Local extraction is busy")
    try:
        return _generate(messages, schema, settings)
    finally:
        INFERENCE.release()
