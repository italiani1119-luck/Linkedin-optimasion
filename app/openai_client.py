"""Klien OpenAI Responses API (tanpa SDK, cukup requests)."""
import requests

import tls  # noqa: F401  (pakai trust store OS untuk TLS)

ENDPOINT = "https://api.openai.com/v1/responses"


class OpenAIError(RuntimeError):
    pass


def _message(resp):
    try:
        data = resp.json()
    except ValueError:
        return (resp.text or "")[:300]
    error = data.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error)[:300]
    if error:
        return str(error)[:300]
    return str(data)[:300]


def generate_post(api_key, model, prompt, timeout=90):
    payload = {
        "model": model,
        "input": prompt,
        "max_output_tokens": 800,
    }
    try:
        resp = requests.post(
            ENDPOINT,
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise OpenAIError("Tidak bisa menghubungi OpenAI: %s" % exc) from exc

    if resp.status_code >= 400:
        raise OpenAIError("OpenAI %s: %s" % (resp.status_code, _message(resp)))

    try:
        data = resp.json()
    except ValueError as exc:
        raise OpenAIError("Respons OpenAI bukan JSON.") from exc

    parts = []
    for item in data.get("output") or []:
        content = item.get("content") if isinstance(item, dict) else None
        if not isinstance(content, list):
            continue
        for chunk in content:
            if not isinstance(chunk, dict):
                continue
            if chunk.get("type") in ("output_text", "text") and chunk.get("text"):
                parts.append(chunk["text"])
            elif chunk.get("type") == "refusal" and chunk.get("refusal"):
                raise OpenAIError("OpenAI menolak permintaan: %s" % chunk["refusal"])

    text = "\n".join(parts).strip()
    if not text:
        raise OpenAIError("OpenAI tidak mengembalikan teks. Coba lagi atau ganti model.")
    return text
