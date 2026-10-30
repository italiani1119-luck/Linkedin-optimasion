"""Penjadwal lokal: buat draft berkala + publikasikan hanya draft yang disetujui."""
import logging
import threading
from datetime import timedelta

import anthropic_client
import db
import email_preview
import prompts
from linkedin_client import publish_post
from openai_client import generate_post
from util import hhmm, iso, now, parse

log = logging.getLogger("scheduler")

MAX_TEXT = 3000
TICK_SECONDS = 10

_stop = threading.Event()
_thread = None


def _interval(settings):
    mode = settings.get("gen_mode", "daily")
    if mode not in ("hours", "minutes"):
        return None
    try:
        value = int(settings.get("gen_every_value") or 1)
    except (TypeError, ValueError):
        value = 1
    value = max(1, value)
    return timedelta(hours=value) if mode == "hours" else timedelta(minutes=value)


def next_generation_at(settings, at=None):
    at = at or now()
    last = parse(settings.get("last_generate_at"))
    delta = _interval(settings)
    if delta is not None:
        return (last + delta) if last else at + delta
    hour, minute = hhmm(settings.get("gen_daily_time"))
    candidate = at.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if last and last >= candidate:
        candidate += timedelta(days=1)
    elif not last and at >= candidate:
        candidate += timedelta(days=1)
    return candidate


def generation_due(settings, at):
    last = parse(settings.get("last_generate_at"))
    delta = _interval(settings)
    if delta is not None:
        return bool(last) and at >= last + delta
    hour, minute = hhmm(settings.get("gen_daily_time"))
    target = at.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return at >= target and (not last or last < target)


def _call_llm(provider, api_key, settings, prompt):
    if provider == "anthropic":
        model = (settings.get("anthropic_model") or "claude-sonnet-5-5").strip()
        return anthropic_client.generate_post(api_key, model, prompt)
    model = (settings.get("openai_model") or "gpt-5-mini").strip()
    return generate_post(api_key, model, prompt)


def generate_draft():
    settings = db.all_settings()
    at = now()
    provider, api_key, _source = db.effective_llm_key(settings)
    label = "Claude" if provider == "anthropic" else "OpenAI"
    post_id = db.create_post(post_date=at.strftime("%Y-%m-%d"), slot=iso(at), source=provider)
    text, error = "", ""
    if not api_key:
        if provider == "anthropic":
            hint = (
                "Claude API key belum ada. Isi di Pengaturan, atau simpan ke file anthropic_key.txt "
                "di folder aplikasi, atau set environment ANTHROPIC_API_KEY."
            )
        else:
            hint = (
                "OpenAI API key belum ada. Isi di Pengaturan, atau simpan ke file openai_key.txt "
                "di folder aplikasi, atau set environment OPENAI_API_KEY."
            )
        error = hint
    else:
        try:
            prompt = prompts.build_prompt(settings.get("profile_summary", ""), at)
            text = _call_llm(provider, api_key, settings, prompt)
            if len(text) > MAX_TEXT:
                error = "Teks dari %s %d karakter, melebihi batas LinkedIn 3.000. Ringkas dulu sebelum menyetujui." % (label, len(text))
        except Exception as exc:  # kegagalan API tidak boleh mematikan scheduler
            log.warning("Gagal membuat draft: %s", exc)
            error = str(exc)
    db.update_post(post_id, text=text, error=error[:800], status="failed" if error else "pending")
    db.set_setting("last_generate_at", iso(at))
    if text and not error:
        email_preview.send_for_post(post_id)
    return post_id


def revise_draft(post_id, instruction=""):
    """Tulis ulang satu draft berdasarkan permintaan revisi, lalu kirim ulang preview email."""
    settings = db.all_settings()
    post = db.get_post(post_id)
    if not post:
        raise RuntimeError("Draft tidak ditemukan.")
    provider, api_key, _source = db.effective_llm_key(settings)
    if not api_key:
        raise RuntimeError(
            "API key %s belum ada." % ("Claude" if provider == "anthropic" else "OpenAI")
        )
    prompt = prompts.build_prompt(settings.get("profile_summary", ""), parse(post.get("post_date")) or now())
    previous = (post.get("text") or "").strip()
    if previous:
        prompt += (
            "\n\nPrevious draft. Rewrite it completely: new opening line, different angle, "
            "do not reuse sentences from it:\n" + previous
        )
    instruction = (instruction or "").strip()[:1000]
    if instruction:
        prompt += "\n\nOwner's revision request (follow it strictly):\n" + instruction

    text = _call_llm(provider, api_key, settings, prompt)
    if len(text) > MAX_TEXT:
        raise RuntimeError("Teks hasil revisi melebihi batas LinkedIn 3.000 karakter. Coba lagi.")
    db.update_post(post_id, text=text, status="pending", error="")
    email_preview.send_for_post(post_id)
    return text


def publish_draft(post_id):
    post = db.get_post(post_id)
    if not post:
        return False
    settings = db.all_settings()
    token = (settings.get("linkedin_access_token") or "").strip()
    person = (settings.get("linkedin_person_sub") or "").strip()
    if not token or not person:
        db.update_post(
            post_id,
            status="failed",
            error="LinkedIn belum terhubung. Buka Pengaturan lalu klik Hubungkan LinkedIn.",
        )
        return False
    text = post["text"] or ""
    log.info(
        "Posting #%s: %d karakter | awal=%r | akhir=%r",
        post_id,
        len(text),
        text[:40],
        text[-40:],
    )
    try:
        urn = publish_post(token, person, text)
    except Exception as exc:
        log.warning("Gagal memposting #%s: %s", post_id, exc)
        db.update_post(post_id, status="failed", error=("Posting gagal: " + str(exc))[:800])
        return False
    log.info("Post #%s terbit, urn=%s, karakter=%d", post_id, urn, len(text))
    db.update_post(post_id, status="posted", posted_at=iso(now()), linkedin_urn=urn, error="")
    return True


def tick():
    settings = db.all_settings()
    at = now()
    if generation_due(settings, at):
        provider, api_key, _source = db.effective_llm_key(settings)
        if not api_key:
            # Tanpa key, jangan menumpuk draft kosong; cukup catat dan lewati slot ini.
            log.info("Slot draft dilewati: API key %s belum ada.", "Claude" if provider == "anthropic" else "OpenAI")
            db.set_setting("last_generate_at", iso(at))
        else:
            try:
                generate_draft()
            except Exception:
                log.exception("Gagal menjalankan pembuatan draft terjadwal")
    for post in db.due_posts(at):
        if db.claim_post(post["id"]):
            publish_draft(post["id"])


def _loop():
    while not _stop.wait(TICK_SECONDS):
        try:
            tick()
        except Exception:
            log.exception("Tick scheduler gagal")


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="scheduler", daemon=True)
    _thread.start()


def stop():
    _stop.set()
