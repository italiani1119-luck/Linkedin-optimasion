"""Klien LinkedIn: OAuth 2.0 (OpenID Connect) dan Posts API."""
from urllib.parse import urlencode

import requests

import tls  # noqa: F401  (pakai trust store OS untuk TLS)

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
SCOPES = "openid profile w_member_social"


class LinkedInError(RuntimeError):
    pass


def _message(resp):
    try:
        data = resp.json()
    except ValueError:
        return (resp.text or "")[:300]
    if isinstance(data, dict):
        for key in ("message", "error_description", "error"):
            if data.get(key):
                return str(data[key])[:300]
    return str(data)[:300]


def authorize_url(client_id, redirect_uri, state):
    query = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": SCOPES,
    })
    return AUTH_URL + "?" + query


def exchange_code(client_id, client_secret, redirect_uri, code):
    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise LinkedInError("Tidak bisa menghubungi LinkedIn: %s" % exc) from exc
    if resp.status_code >= 400:
        raise LinkedInError("Tukar kode OAuth gagal (%s): %s" % (resp.status_code, _message(resp)))
    data = resp.json()
    if not data.get("access_token"):
        raise LinkedInError("LinkedIn tidak mengembalikan access token.")
    return data


def fetch_userinfo(access_token):
    try:
        resp = requests.get(
            USERINFO_URL,
            headers={"Authorization": "Bearer " + access_token},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise LinkedInError("Tidak bisa menghubungi LinkedIn: %s" % exc) from exc
    if resp.status_code >= 400:
        raise LinkedInError("Ambil profil LinkedIn gagal (%s): %s" % (resp.status_code, _message(resp)))
    data = resp.json()
    if not data.get("sub"):
        raise LinkedInError("Profil LinkedIn tidak berisi member id (sub).")
    return data


def publish_post(access_token, person_sub, text):
    """Kirim satu post. Pakai endpoint ugcPosts: /rest/posts memotong teks panjang saat diterima."""
    body = {
        "author": "urn:li:person:%s" % person_sub,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    try:
        resp = requests.post(POSTS_URL, json=body, headers=headers, timeout=60)
    except requests.RequestException as exc:
        raise LinkedInError("Tidak bisa menghubungi LinkedIn: %s" % exc) from exc

    if resp.status_code >= 400:
        message = _message(resp)
        if resp.status_code == 401:
            message = "Token LinkedIn kedaluwarsa atau tidak valid. Hubungkan ulang di Pengaturan. " + message
        raise LinkedInError("LinkedIn %s: %s" % (resp.status_code, message))

    return resp.headers.get("x-restli-id") or resp.headers.get("X-Restli-Id") or ""
