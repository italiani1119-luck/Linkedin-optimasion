"""Klien Resend untuk email preview (tanpa SDK)."""
import requests

import tls  # noqa: F401  (pakai trust store OS untuk TLS)

ENDPOINT = "https://api.resend.com/emails"


class ResendError(RuntimeError):
    pass


def _message(resp):
    try:
        data = resp.json()
    except ValueError:
        return (resp.text or "")[:300]
    message = data.get("message") or data.get("error")
    if isinstance(message, dict):
        return str(message.get("message") or message)[:300]
    if message:
        return str(message)[:300]
    return str(data)[:300]


def send_email(api_key, sender, recipients, subject, html, text=None, timeout=30):
    payload = {
        "from": sender,
        "to": recipients,
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    try:
        resp = requests.post(
            ENDPOINT,
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise ResendError("Tidak bisa menghubungi Resend: %s" % exc) from exc

    if resp.status_code >= 400:
        raise ResendError("Resend %s: %s" % (resp.status_code, _message(resp)))

    try:
        data = resp.json()
    except ValueError:
        return ""
    return str(data.get("id") or "")
