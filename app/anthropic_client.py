"""Klien Anthropic Messages API (Claude), tanpa SDK."""
import requests

import tls  # noqa: F401  (pakai trust store OS untuk TLS)

ENDPOINT = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class AnthropicError(RuntimeError):
    pass


def _message(resp):
    try:
        data = resp.json()
    except ValueError:
        return (resp.text or "")[:300]
    error = data.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("type") or error)[:300]
    if error:
        return str(error)[:300]
    return str(data)[:300]


def generate_post(api_key, model, prompt, timeout=90):
    payload = {
        "model": model,
        "max_tokens": 3000,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        resp = requests.post(
            ENDPOINT,
            headers={
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise AnthropicError("Tidak bisa menghubungi Claude: %s" % exc) from exc

    if resp.status_code >= 400:
        raise AnthropicError("Claude %s: %s" % (resp.status_code, _message(resp)))

    try:
        data = resp.json()
    except ValueError as exc:
        raise AnthropicError("Respons Claude bukan JSON.") from exc

    parts = []
    for chunk in data.get("content") or []:
        if isinstance(chunk, dict) and chunk.get("type") == "text" and chunk.get("text"):
            parts.append(chunk["text"])

    text = "\n".join(parts).strip()
    if not text:
        raise AnthropicError("Claude tidak mengembalikan teks. Coba lagi atau ganti model.")
    if data.get("stop_reason") == "max_tokens":
        raise AnthropicError("Claude berhenti karena batas token sehingga teks terpotong. Coba lagi.")
    return text
