"""Email preview draft LinkedIn via Resend, dengan tautan setujui/batalkan."""
import hashlib
import hmac
import html
import logging
import os

import db
import resend_client
from util import fmt_dt, now

log = logging.getLogger("email_preview")


def _secret():
    return db.get_setting("app_secret") or ""


def make_token(post_id, action):
    message = ("%s:%s" % (action, post_id)).encode("utf-8")
    return hmac.new(_secret().encode("utf-8"), message, hashlib.sha256).hexdigest()[:32]


def verify_token(post_id, action, token):
    expected = make_token(post_id, action)
    return bool(token) and hmac.compare_digest(expected, str(token))


def base_url(settings=None):
    settings = settings or db.all_settings()
    base = (settings.get("public_base_url") or "").strip().rstrip("/")
    if base:
        return base
    return "http://127.0.0.1:%s" % os.environ.get("PORT", "8080")


def _recipients(value):
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _paragraphs(text):
    blocks = [html.escape(block.strip()) for block in text.split("\n\n") if block.strip()]
    return "".join(
        "<p style='margin:0 0 12px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.55;color:#1a1a1a'>%s</p>"
        % block.replace("\n", "<br>")
        for block in blocks
    )


def build_email(post, settings):
    base = base_url(settings)
    approve_url = "%s/email/aksi/%s/setujui?t=%s" % (base, post["id"], make_token(post["id"], "setujui"))
    cancel_url = "%s/email/aksi/%s/batalkan?t=%s" % (base, post["id"], make_token(post["id"], "batalkan"))
    revise_url = "%s/email/aksi/%s/revisi?t=%s" % (base, post["id"], make_token(post["id"], "revisi"))
    publish_time = settings.get("publish_time", "19:30")
    subject = "Preview post LinkedIn %s - butuh persetujuan" % post["post_date"]

    body = _paragraphs(post.get("text") or "")
    html_body = """<!doctype html>
<html><body style="margin:0;padding:0;background:#f4f6f8">
<div style="max-width:640px;margin:0 auto;padding:24px 16px">
  <div style="background:#ffffff;border:1px solid #e2e6ea;border-radius:10px;padding:22px">
    <p style="margin:0 0 4px;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6b7280">LinkedIn Auto-Post &middot; %s</p>
    <h1 style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:20px;color:#111827">Preview post&nbsp;hari ini</h1>
    <div style="border-left:3px solid #0a66c2;background:#f7f9fb;border-radius:6px;padding:14px 16px;margin:0 0 18px">
      %s
    </div>
    <p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#4b5563">
      Post <b>tidak akan terbit</b> tanpa persetujuan Anda. Jika disetujui, post dijadwalkan pukul <b>%s WIB</b>
      (atau langsung terbit bila jam itu sudah lewat).
    </p>
    <p style="margin:0 0 10px">
      <a href="%s" style="display:inline-block;background:#0a66c2;color:#ffffff;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;padding:12px 20px;border-radius:6px">Setujui &amp; jadwalkan</a>
      <a href="%s" style="display:inline-block;background:#fff7e6;color:#8a5a00;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-size:14px;padding:12px 20px;border-radius:6px;margin-left:8px">Minta revisi</a>
      <a href="%s" style="display:inline-block;background:#eef1f4;color:#374151;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-size:14px;padding:12px 20px;border-radius:6px;margin-left:8px">Batalkan</a>
    </p>
    <p style="margin:14px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#9ca3af">
      Tautan ini hanya berlaku untuk draft #%s. Anda juga bisa mengedit teks di <a href="%s" style="color:#0a66c2">dashboard</a> sebelum menyetujui.
    </p>
  </div>
  <p style="text-align:center;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#9ca3af;margin:14px 0 0">Dikirim otomatis oleh LinkedIn Auto-Post lokal.</p>
</div>
</body></html>""" % (
        html.escape(post.get("post_date") or ""),
        body,
        html.escape(str(publish_time)),
        approve_url,
        revise_url,
        cancel_url,
        post["id"],
        base,
    )

    text_body = "%s\n\nSetujui: %s\nMinta revisi: %s\nBatalkan: %s\n\nPost tidak terbit tanpa persetujuan." % (
        post.get("text") or "",
        approve_url,
        revise_url,
        cancel_url,
    )
    return subject, html_body, text_body, base


def send_for_post(post_id):
    """Kirim preview bila fitur aktif dan key tersedia. Tidak pernah melempar exception."""
    try:
        settings = db.all_settings()
        if settings.get("email_preview_enabled", "1") != "1":
            return False, "Email preview dimatikan."
        post = db.get_post(post_id)
        if not post or not (post.get("text") or "").strip():
            return False, "Draft belum punya teks."
        key, _source = db.effective_resend_key(settings)
        if not key:
            message = "Gagal: Resend API key belum ada."
            db.set_setting("resend_last_status", message)
            return False, message
        recipients = _recipients(settings.get("resend_to"))
        if not recipients:
            message = "Gagal: alamat email tujuan belum diisi."
            db.set_setting("resend_last_status", message)
            return False, message
        subject, html_body, text_body, _base = build_email(post, settings)
        resend_client.send_email(
            key,
            (settings.get("resend_from") or "").strip(),
            recipients,
            subject,
            html_body,
            text_body,
        )
        message = "Terkirim ke %s pada %s" % (", ".join(recipients), fmt_dt(now()))
        db.set_setting("resend_last_status", message)
        return True, message
    except Exception as exc:  # email gagal tidak boleh menggagalkan draft
        log.warning("Gagal mengirim preview email: %s", exc)
        message = "Gagal: %s" % exc
        try:
            db.set_setting("resend_last_status", message[:400])
        except Exception:
            pass
        return False, message


def send_test(settings):
    """Email uji tanpa tautan aksi."""
    key, _source = db.effective_resend_key(settings)
    if not key:
        return False, "Resend API key belum ada."
    recipients = _recipients(settings.get("resend_to"))
    if not recipients:
        return False, "Alamat email tujuan belum diisi."
    subject = "Tes email preview LinkedIn Auto-Post"
    html_body = """<!doctype html><html><body style="background:#f4f6f8;padding:24px">
<div style="max-width:560px;margin:0 auto;background:#fff;border:1px solid #e2e6ea;border-radius:10px;padding:22px;font-family:Arial,Helvetica,sans-serif">
<h2 style="margin:0 0 10px;font-size:18px;color:#111827">Email preview berfungsi</h2>
<p style="margin:0 0 10px;font-size:14px;color:#374151">Ini email uji dari LinkedIn Auto-Post. Preview draft asli akan dikirim otomatis setiap kali draft baru selesai dibuat.</p>
<p style="margin:0;font-size:12px;color:#9ca3af">Dikirim pada %s.</p>
</div></body></html>""" % fmt_dt(now())
    try:
        resend_client.send_email(key, (settings.get("resend_from") or "").strip(), recipients, subject, html_body)
    except Exception as exc:
        return False, str(exc)
    return True, "Email uji terkirim ke %s." % ", ".join(recipients)
