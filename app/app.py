"""LinkedIn Auto-Post lokal: dashboard review/edit/approve + scheduler + auto-post.

Jalankan dengan run.bat (Windows) atau: python app.py
"""
import hashlib
import logging
import os
import secrets
from datetime import timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

import db
import email_preview
import linkedin_client
import scheduler
from util import fmt_date, fmt_dt, hhmm, iso, now, parse

BASE_DIR = Path(__file__).resolve().parent
MAX_TEXT = 3000

logger = logging.getLogger()


def configure_logging():
    log_dir = BASE_DIR / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(handler)


configure_logging()
db.init_db()

app = Flask(__name__)
app.secret_key = db.get_setting("app_secret")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

STATUS_LABEL = {
    "pending": "Menunggu persetujuan",
    "approved": "Disetujui",
    "publishing": "Sedang diposting",
    "posted": "Terbit",
    "failed": "Gagal",
    "cancelled": "Dibatalkan",
}


# ---------- helpers ----------

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200000)
    return "pbkdf2$%s$%s" % (salt, digest.hex())


def verify_password(stored, password):
    try:
        _, salt, digest = stored.split("$")
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200000)
    return secrets.compare_digest(digest, candidate.hex())


def password_set():
    return bool(db.get_setting("dashboard_password_hash"))


def authorized():
    return (not password_set()) or bool(session.get("auth_ok"))


def ensure_csrf():
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
    return token


def valid_hhmm(value):
    try:
        hour, minute = str(value).split(":")
        return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59
    except (TypeError, ValueError):
        return False


def callback_url(settings=None):
    settings = settings or db.all_settings()
    base = (settings.get("public_base_url") or "").strip().rstrip("/")
    if not base:
        base = request.host_url.rstrip("/")
    return base + "/auth/linkedin/callback"


def next_publish_at():
    times = [parse(p["publish_at"]) for p in db.list_posts(["approved"], limit=100) if p.get("publish_at")]
    times = [t for t in times if t]
    return min(times) if times else None


def schedule_summary(settings):
    mode = settings.get("gen_mode")
    if mode == "hours":
        return "Setiap %s jam" % settings.get("gen_every_value")
    if mode == "minutes":
        return "Setiap %s menit" % settings.get("gen_every_value")
    return "Harian pukul %s WIB" % settings.get("gen_daily_time")


def publish_summary(settings):
    if settings.get("publish_mode") == "immediate":
        return "Langsung setelah disetujui"
    return "Pukul %s WIB setelah disetujui" % settings.get("publish_time")


def compute_publish_at(settings, when="schedule"):
    at = now()
    if when == "now" or settings.get("publish_mode") == "immediate":
        return at
    hour, minute = hhmm(settings.get("publish_time"), "19:30")
    target = at.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target if at < target else at


def back_to_post(post_id):
    return redirect(url_for("index") + "#post-%d" % post_id)


@app.before_request
def guard():
    if request.endpoint in ("static", "health", "linkedin_callback", "privacy", "email_action"):
        return None
    if request.method == "POST":
        token = ensure_csrf()
        if not secrets.compare_digest(token, request.form.get("csrf", "")):
            abort(400, "CSRF token tidak valid. Muat ulang halaman lalu coba lagi.")
    if request.endpoint == "login":
        return None
    if not authorized():
        return redirect(url_for("login"))
    return None


@app.context_processor
def inject_globals():
    settings = db.all_settings()
    try:
        next_gen = scheduler.next_generation_at(settings)
    except Exception:
        logger.exception("Gagal menghitung jadwal berikutnya")
        next_gen = None
    provider, key, source = db.effective_llm_key(settings)
    return {
        "csrf_token": ensure_csrf(),
        "now": now(),
        "settings": settings,
        "llm_provider": provider,
        "llm_ready": bool(key),
        "llm_name": "Claude" if provider == "anthropic" else "OpenAI",
        "llm_source": source,
        "linkedin_ready": bool(
            (settings.get("linkedin_access_token") or "").strip()
            and (settings.get("linkedin_person_sub") or "").strip()
        ),
        "linkedin_name": settings.get("linkedin_person_name") or "",
        "next_gen": next_gen,
        "next_publish": next_publish_at(),
        "gen_summary": schedule_summary(settings),
        "publish_summary": publish_summary(settings),
        "password_set": password_set(),
        "status_label": STATUS_LABEL,
    }


app.jinja_env.filters["dt"] = fmt_dt
app.jinja_env.filters["date_id"] = fmt_date
app.jinja_env.filters["status_label"] = lambda value: STATUS_LABEL.get(value, value)


@app.template_global()
def revise_link(post_id):
    return url_for(
        "email_action",
        post_id=post_id,
        action="revisi",
        t=email_preview.make_token(post_id, "revisi"),
    )


# ---------- auth ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if not password_set():
        return redirect(url_for("index"))
    if request.method == "POST":
        if verify_password(db.get_setting("dashboard_password_hash"), request.form.get("password", "")):
            session["auth_ok"] = True
            session.permanent = True
            return redirect(url_for("index"))
        flash("Kata sandi salah.", "err")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.pop("auth_ok", None)
    return redirect(url_for("login"))


@app.get("/health")
def health():
    return {"ok": True, "time": iso(now())}


@app.get("/privacy")
def privacy():
    return render_template("privacy.html")


# ---------- dashboard ----------

@app.route("/")
def index():
    return render_template(
        "index.html",
        active=db.active_posts(),
        recent=db.list_posts(["posted"], limit=5),
        max_text=MAX_TEXT,
    )


@app.post("/draft/baru")
def new_draft():
    at = now()
    post_id = db.create_post(post_date=at.strftime("%Y-%m-%d"), slot=iso(at), source="manual")
    flash("Draft manual dibuat. Tulis teksnya di bawah, lalu simpan dan setujui.", "ok")
    return back_to_post(post_id)


@app.post("/draft/generate")
def generate_now():
    post_id = scheduler.generate_draft()
    post = db.get_post(post_id)
    if post and post.get("error"):
        flash("Draft dibuat, tetapi ada masalah: %s" % post["error"], "err")
    else:
        flash("Draft baru berhasil dibuat. Periksa, edit bila perlu, lalu setujui.", "ok")
    return back_to_post(post_id)


@app.post("/draft/<int:post_id>/simpan")
def save_draft(post_id):
    post = db.get_post(post_id)
    if not post:
        abort(404)
    if post["status"] in ("posted", "publishing"):
        flash("Post ini sudah terbit/sedang diposting sehingga teksnya tidak bisa diubah.", "err")
        return back_to_post(post_id)

    text = (request.form.get("text") or "").replace("\r\n", "\n").strip()
    fields = {"text": text}
    message = "Perubahan disimpan."
    if post["status"] == "approved":
        fields.update(status="pending", approved_at="", publish_at="")
        message += " Karena teks berubah, status kembali ke Menunggu persetujuan."
    elif post["status"] == "failed":
        fields.update(status="pending", error="")
        message += " Status direset ke Menunggu persetujuan."
    db.update_post(post_id, **fields)
    flash(message, "ok")
    return back_to_post(post_id)


@app.post("/draft/<int:post_id>/setujui")
def approve_draft(post_id):
    post = db.get_post(post_id)
    if not post:
        abort(404)
    if post["status"] not in ("pending", "failed"):
        flash("Draft ini tidak bisa disetujui pada status sekarang.", "err")
        return back_to_post(post_id)

    text = (post["text"] or "").strip()
    if not text:
        flash("Teks masih kosong. Tulis dulu, simpan, baru setujui.", "err")
        return back_to_post(post_id)
    if len(post["text"]) > MAX_TEXT:
        flash("Teks %d karakter, melebihi batas LinkedIn %d. Ringkas dulu." % (len(post["text"]), MAX_TEXT), "err")
        return back_to_post(post_id)

    settings = db.all_settings()
    when = request.form.get("when", "schedule")
    publish_at = compute_publish_at(settings, when)
    db.update_post(
        post_id,
        status="approved",
        approved_at=iso(now()),
        publish_at=iso(publish_at),
        error="",
    )
    message = "Post disetujui dan dijadwalkan pada %s." % fmt_dt(publish_at)
    if publish_at <= now():
        message = "Post disetujui. Publikasi akan dicoba dalam ±10 detik."
    if not (settings.get("linkedin_access_token") and settings.get("linkedin_person_sub")):
        message += " Catatan: LinkedIn belum terhubung, jadi posting akan gagal sampai Anda menghubungkannya di Pengaturan."
    flash(message, "ok")
    return back_to_post(post_id)


@app.post("/draft/<int:post_id>/email")
def email_draft(post_id):
    post = db.get_post(post_id)
    if not post:
        abort(404)
    ok, message = email_preview.send_for_post(post_id)
    flash(("Preview email: " if ok else "Gagal mengirim preview: ") + message, "ok" if ok else "err")
    return back_to_post(post_id)


@app.post("/draft/<int:post_id>/batalkan")
def cancel_draft(post_id):
    post = db.get_post(post_id)
    if not post:
        abort(404)
    if post["status"] in ("pending", "approved", "failed"):
        db.update_post(post_id, status="cancelled", publish_at="", error="")
        flash("Draft dibatalkan dan tidak akan dipublikasikan.", "ok")
    else:
        flash("Draft ini tidak bisa dibatalkan pada status sekarang.", "err")
    return back_to_post(post_id)


@app.post("/draft/<int:post_id>/coba-lagi")
def retry_draft(post_id):
    post = db.get_post(post_id)
    if not post:
        abort(404)
    if post["status"] != "failed":
        flash("Hanya post berstatus Gagal yang bisa dicoba lagi.", "err")
        return back_to_post(post_id)
    if not (post["text"] or "").strip():
        # Gagal saat membuat teks: buat draft baru, jangan coba memposting teks kosong.
        new_id = scheduler.generate_draft()
        db.delete_post(post_id)
        new_post = db.get_post(new_id)
        if new_post and new_post.get("error"):
            flash("Draft baru dibuat, tetapi ada masalah: %s" % new_post["error"], "err")
        else:
            flash("Draft baru berhasil dibuat. Periksa, edit bila perlu, lalu setujui.", "ok")
        return back_to_post(new_id)
    db.update_post(post_id, status="approved", publish_at=iso(now()), error="")
    flash("Post dijadwalkan ulang. Publikasi akan dicoba dalam ±10 detik.", "ok")
    return back_to_post(post_id)


@app.post("/draft/<int:post_id>/hapus")
def delete_draft(post_id):
    destination = url_for("history") if request.form.get("next") == "riwayat" else url_for("index")
    if db.delete_post(post_id):
        flash("Draft dihapus.", "ok")
        return redirect(destination)
    flash("Hanya draft berstatus Gagal/Dibatalkan yang bisa dihapus.", "err")
    return back_to_post(post_id)


# ---------- aksi dari tautan email ----------

@app.route("/email/aksi/<int:post_id>/<action>", methods=["GET", "POST"])
def email_action(post_id, action):
    if action not in ("setujui", "batalkan", "revisi"):
        abort(404)
    token = request.values.get("t", "")
    if not email_preview.verify_token(post_id, action, token):
        abort(403, "Tautan tidak valid.")
    post = db.get_post(post_id)
    if not post:
        abort(404)
    result = None
    if request.method == "POST" and action == "setujui":
        if post["status"] not in ("pending", "failed") or not (post["text"] or "").strip():
            result = ("err", "Draft ini tidak bisa disetujui pada status sekarang.")
        else:
            settings = db.all_settings()
            publish_at = compute_publish_at(settings, "schedule")
            db.update_post(
                post_id,
                status="approved",
                approved_at=iso(now()),
                publish_at=iso(publish_at),
                error="",
            )
            if publish_at <= now():
                result = ("ok", "Post disetujui. Publikasi akan dicoba dalam ±10 detik.")
            else:
                result = ("ok", "Post disetujui dan dijadwalkan %s." % fmt_dt(publish_at))
        post = db.get_post(post_id)
    elif request.method == "POST" and action == "batalkan":
        if post["status"] in ("pending", "approved", "failed"):
            db.update_post(post_id, status="cancelled", publish_at="", error="")
            result = ("ok", "Post dibatalkan dan tidak akan terbit.")
        else:
            result = ("err", "Post tidak bisa dibatalkan pada status sekarang.")
        post = db.get_post(post_id)
    elif request.method == "POST" and action == "revisi":
        if post["status"] not in ("pending", "approved", "failed"):
            result = ("err", "Draft ini tidak bisa direvisi pada status sekarang.")
        else:
            try:
                scheduler.revise_draft(post_id, request.form.get("instruction") or "")
                result = ("ok", "Draft ditulis ulang dan preview baru sudah dikirim ke email Anda.")
            except Exception as exc:
                result = ("err", "Revisi gagal: %s" % exc)
        post = db.get_post(post_id)
    return render_template(
        "email_action.html",
        post=post,
        action=action,
        token=token,
        revise_token=email_preview.make_token(post_id, "revisi"),
        result=result,
    )


# ---------- history ----------

@app.route("/riwayat")
def history():
    return render_template("history.html", posts=db.list_posts(None, limit=200))


# ---------- settings ----------

@app.route("/pengaturan")
def settings_page():
    settings = db.all_settings()
    provider, active_key, active_source = db.effective_llm_key(settings)
    openai_key, openai_source = db.effective_openai_key(settings)
    anthropic_key, anthropic_source = db.effective_anthropic_key(settings)
    resend_key, resend_source = db.effective_resend_key(settings)
    return render_template(
        "settings.html",
        s=settings,
        callback_url=callback_url(settings),
        has_secret=bool((settings.get("linkedin_client_secret") or "").strip()),
        has_key=bool((settings.get("openai_api_key") or "").strip()),
        has_anthropic_key=bool((settings.get("anthropic_api_key") or "").strip()),
        key_ready=bool(active_key),
        key_source=active_source,
        openai_ready=bool(openai_key),
        openai_source=openai_source,
        anthropic_ready=bool(anthropic_key),
        anthropic_source=anthropic_source,
        key_file=str(db.KEY_FILE),
        anthropic_key_file=str(db.ANTHROPIC_KEY_FILE),
        has_resend_key=bool((settings.get("resend_api_key") or "").strip()),
        resend_ready=bool(resend_key),
        resend_source=resend_source,
        resend_key_file=str(db.RESEND_KEY_FILE),
        token_expires=settings.get("linkedin_expires_at"),
    )


@app.post("/pengaturan/profil")
def save_profile():
    profile = (request.form.get("profile_summary") or "").strip()
    provider = request.form.get("llm_provider", "openai")
    if provider not in ("openai", "anthropic"):
        provider = "openai"
    openai_model = (request.form.get("openai_model") or "").strip() or "gpt-5-mini"
    anthropic_model = (request.form.get("anthropic_model") or "").strip() or "claude-sonnet-5-5"
    openai_key = (request.form.get("openai_api_key") or "").strip()
    anthropic_key = (request.form.get("anthropic_api_key") or "").strip()
    if not profile:
        flash("Ringkasan profil tidak boleh kosong.", "err")
        return redirect(url_for("settings_page") + "#profil")
    values = {
        "profile_summary": profile,
        "llm_provider": provider,
        "openai_model": openai_model,
        "anthropic_model": anthropic_model,
    }
    if request.form.get("clear_api_key") == "1":
        values["openai_api_key"] = ""
    elif openai_key:
        values["openai_api_key"] = openai_key
    if request.form.get("clear_anthropic_key") == "1":
        values["anthropic_api_key"] = ""
    elif anthropic_key:
        values["anthropic_api_key"] = anthropic_key
    db.set_settings(values)
    flash("Profil dan penyedia AI disimpan (%s)." % ("Claude" if provider == "anthropic" else "OpenAI"), "ok")
    return redirect(url_for("settings_page") + "#profil")


@app.post("/pengaturan/email")
def save_email():
    settings = db.all_settings()
    action = request.form.get("action", "save")
    sender = (request.form.get("resend_from") or "").strip()
    recipients = (request.form.get("resend_to") or "").strip()
    key = (request.form.get("resend_api_key") or "").strip()
    if "@" not in sender:
        flash("Alamat pengirim tidak valid. Contoh: LinkedIn Bot <nama@domain-anda.com>.", "err")
        return redirect(url_for("settings_page") + "#email")
    if not recipients or any("@" not in part for part in recipients.split(",")):
        flash("Alamat email tujuan tidak valid.", "err")
        return redirect(url_for("settings_page") + "#email")
    values = {
        "email_preview_enabled": "1" if request.form.get("email_preview_enabled") == "1" else "0",
        "resend_from": sender,
        "resend_to": recipients,
    }
    if request.form.get("clear_resend_key") == "1":
        values["resend_api_key"] = ""
    elif key:
        values["resend_api_key"] = key
    db.set_settings(values)
    if action == "test":
        ok, message = email_preview.send_test(db.all_settings())
        flash(("Email uji: " if ok else "Gagal mengirim email uji: ") + message, "ok" if ok else "err")
    else:
        flash("Pengaturan email preview disimpan.", "ok")
    return redirect(url_for("settings_page") + "#email")


@app.post("/pengaturan/jadwal")
def save_schedule():
    mode = request.form.get("gen_mode", "daily")
    if mode not in ("daily", "hours", "minutes"):
        mode = "daily"
    daily_time = request.form.get("gen_daily_time", "18:30")
    publish_time = request.form.get("publish_time", "19:30")
    publish_mode = request.form.get("publish_mode", "at_time")
    if publish_mode not in ("at_time", "immediate"):
        publish_mode = "at_time"
    if not valid_hhmm(daily_time) or not valid_hhmm(publish_time):
        flash("Format jam harus HH:MM, contoh 18:30.", "err")
        return redirect(url_for("settings_page") + "#jadwal")
    try:
        every = int(request.form.get("gen_every_value") or 1)
    except ValueError:
        every = 1
    every = min(max(every, 1), 10080)
    db.set_settings({
        "gen_mode": mode,
        "gen_daily_time": daily_time,
        "gen_every_value": str(every),
        "publish_mode": publish_mode,
        "publish_time": publish_time,
    })
    flash("Jadwal disimpan. Berlaku untuk draft berikutnya.", "ok")
    return redirect(url_for("settings_page") + "#jadwal")


@app.post("/pengaturan/linkedin")
def save_linkedin():
    client_id = (request.form.get("linkedin_client_id") or "").strip()
    secret = (request.form.get("linkedin_client_secret") or "").strip()
    version = (request.form.get("linkedin_version") or "").strip() or "202601"
    base = (request.form.get("public_base_url") or "").strip().rstrip("/")
    if base and not base.startswith("https://"):
        flash("Public base URL harus diawali https:// (syarat callback LinkedIn).", "err")
        return redirect(url_for("settings_page") + "#linkedin")
    values = {
        "linkedin_client_id": client_id,
        "linkedin_version": version,
        "public_base_url": base,
    }
    if secret:
        values["linkedin_client_secret"] = secret
    db.set_settings(values)
    flash("Kredensial LinkedIn disimpan.", "ok")
    return redirect(url_for("settings_page") + "#linkedin")


@app.post("/pengaturan/linkedin/token")
def save_linkedin_token():
    token = (request.form.get("access_token") or "").strip()
    if not token:
        flash("Access token kosong.", "err")
        return redirect(url_for("settings_page") + "#linkedin")
    try:
        info = linkedin_client.fetch_userinfo(token)
    except Exception as exc:
        flash("Token ditolak LinkedIn: %s" % exc, "err")
        return redirect(url_for("settings_page") + "#linkedin")
    db.set_settings({
        "linkedin_access_token": token,
        "linkedin_person_sub": info.get("sub", ""),
        "linkedin_person_name": info.get("name") or info.get("given_name") or "",
        "linkedin_expires_at": iso(now() + timedelta(days=59)),
    })
    flash("Token LinkedIn tersimpan. Terhubung sebagai %s." % (info.get("name") or "akun Anda"), "ok")
    return redirect(url_for("settings_page") + "#linkedin")


@app.post("/pengaturan/linkedin/putuskan")
def disconnect_linkedin():
    db.set_settings({
        "linkedin_access_token": "",
        "linkedin_refresh_token": "",
        "linkedin_expires_at": "",
        "linkedin_person_sub": "",
        "linkedin_person_name": "",
    })
    flash("Koneksi LinkedIn diputus. Post yang disetujui akan gagal sampai dihubungkan lagi.", "ok")
    return redirect(url_for("settings_page") + "#linkedin")


@app.post("/pengaturan/keamanan")
def save_security():
    remove = request.form.get("remove_password") == "1"
    new_password = request.form.get("new_password") or ""
    if remove:
        db.set_setting("dashboard_password_hash", "")
        session.pop("auth_ok", None)
        flash("Kata sandi dashboard dihapus. Dashboard hanya bisa diakses dari komputer ini.", "ok")
        return redirect(url_for("settings_page") + "#keamanan")
    if new_password:
        if len(new_password) < 6:
            flash("Kata sandi minimal 6 karakter.", "err")
            return redirect(url_for("settings_page") + "#keamanan")
        if new_password != (request.form.get("confirm_password") or ""):
            flash("Konfirmasi kata sandi tidak sama.", "err")
            return redirect(url_for("settings_page") + "#keamanan")
        db.set_setting("dashboard_password_hash", hash_password(new_password))
        session["auth_ok"] = True
        session.permanent = True
        flash("Kata sandi dashboard disimpan.", "ok")
    else:
        flash("Tidak ada perubahan kata sandi.", "ok")
    return redirect(url_for("settings_page") + "#keamanan")


# ---------- LinkedIn OAuth ----------

@app.route("/auth/linkedin/start")
def linkedin_start():
    settings = db.all_settings()
    client_id = (settings.get("linkedin_client_id") or "").strip()
    secret = (settings.get("linkedin_client_secret") or "").strip()
    base = (settings.get("public_base_url") or "").strip().rstrip("/")
    if not client_id or not secret:
        flash("Isi Client ID dan Client Secret LinkedIn terlebih dahulu.", "err")
        return redirect(url_for("settings_page") + "#linkedin")
    if not base.startswith("https://"):
        flash(
            "Untuk menghubungkan LinkedIn, isi Public base URL HTTPS (tunnel) dan buka dashboard lewat URL tunnel tersebut. Lihat README bagian LinkedIn.",
            "err",
        )
        return redirect(url_for("settings_page") + "#linkedin")

    state = secrets.token_urlsafe(24)
    db.set_settings({
        "oauth_state": state,
        "oauth_state_expires": iso(now() + timedelta(minutes=15)),
    })
    return redirect(linkedin_client.authorize_url(client_id, base + "/auth/linkedin/callback", state))


@app.route("/auth/linkedin/callback")
def linkedin_callback():
    settings = db.all_settings()
    error = request.args.get("error_description") or request.args.get("error")
    if error:
        flash("LinkedIn menolak otorisasi: %s" % error, "err")
        return redirect(url_for("settings_page") + "#linkedin")

    code = request.args.get("code", "")
    state = request.args.get("state", "")
    expected = settings.get("oauth_state") or ""
    expires = parse(settings.get("oauth_state_expires"))
    valid = bool(code and expected and state and secrets.compare_digest(state, expected))
    if not valid or (expires and expires < now()):
        flash("Sesi OAuth tidak valid atau kedaluwarsa. Klik Hubungkan LinkedIn lagi.", "err")
        return redirect(url_for("settings_page") + "#linkedin")

    db.set_settings({"oauth_state": "", "oauth_state_expires": ""})
    base = (settings.get("public_base_url") or "").strip().rstrip("/")
    try:
        token = linkedin_client.exchange_code(
            (settings.get("linkedin_client_id") or "").strip(),
            (settings.get("linkedin_client_secret") or "").strip(),
            base + "/auth/linkedin/callback",
            code,
        )
        info = linkedin_client.fetch_userinfo(token["access_token"])
    except Exception as exc:
        logger.warning("OAuth LinkedIn gagal: %s", exc)
        flash("Gagal menghubungkan LinkedIn: %s" % exc, "err")
        return redirect(url_for("settings_page") + "#linkedin")

    expires_in = int(token.get("expires_in") or 0)
    expires_at = now() + timedelta(seconds=expires_in) if expires_in else now() + timedelta(days=59)
    db.set_settings({
        "linkedin_access_token": token["access_token"],
        "linkedin_refresh_token": token.get("refresh_token", ""),
        "linkedin_expires_at": iso(expires_at),
        "linkedin_person_sub": info.get("sub", ""),
        "linkedin_person_name": info.get("name") or info.get("given_name") or "",
    })
    flash("LinkedIn terhubung sebagai %s. Post yang disetujui akan terbit otomatis." % (info.get("name") or "akun Anda"), "ok")
    return redirect(url_for("settings_page") + "#linkedin")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    scheduler.start()
    print("LinkedIn Auto-Post berjalan di http://127.0.0.1:%d" % port)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
