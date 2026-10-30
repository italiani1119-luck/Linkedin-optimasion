# LinkedIn Auto-Post (lokal)

Otomasi lokal untuk membuat draft post LinkedIn secara berkala, **meninjau/mengedit draft di dashboard**, menyetujuinya, lalu **menerbitkan otomatis** ke LinkedIn pada jam yang ditentukan. Dibangun dari logika workflow n8n di [github.com/italiani1119-luck/n8n-linkedin](https://github.com/italiani1119-luck/n8n-linkedin).

**Aturan utama: post tidak akan pernah terbit tanpa persetujuan Anda.**

```
Jadwal tiba ──> Draft dibuat (OpenAI atau Claude) ──> Antrean review
                                            │  edit / pratinjau
                                            ▼
                                   Setujui ──> dijadwalkan ──> Posting ke LinkedIn
                                   Batalkan ─> tidak pernah terbit
```

Yang diadaptasi dari repo: prompt + pillar konten harian, jadwal preview/publish, alur status `pending → approved → posted` (plus `cancelled`/`failed`), dan syarat persetujuan.
Yang diganti: n8n Data Table → SQLite lokal; email preview Resend → dashboard lokal (bisa edit, bukan hanya setuju/batal); node LinkedIn n8n → LinkedIn REST API langsung.

---

## Prasyarat

- Windows 10/11 (di mesin ini sudah ada **Python 3.10.11**).
- Koneksi internet.
- **OpenAI API key** atau **Claude (Anthropic) API key** (untuk membuat draft otomatis; pilih salah satu).
- **Resend API key** + domain terverifikasi (opsional, untuk email preview sebelum post).
- Akun LinkedIn + **LinkedIn Page** (dibutuhkan LinkedIn untuk membuat aplikasi API). Untuk auto-post, perlu membuat aplikasi LinkedIn sekali saja (± 30–60 menit).

---

## A. Instalasi (sekali saja)

1. Buka folder `linkedin-automation`.
2. Klik dua kali **`setup.bat`**. Tunggu sampai muncul `[OK] Setup selesai`. Script ini membuat `.venv` dan memasang dependensi. Jika pemasangan normal gagal karena antivirus/proxy memeriksa SSL, script otomatis mencoba ulang dengan `--trusted-host`.
3. Klik dua kali **`run.bat`**. Jendela hitam harus tetap terbuka selama otomasi berjalan (itu servernya). Jangan tutup jendela ini.
4. Buka **http://127.0.0.1:8080** di browser. Dashboard akan tampil.

> Ingin otomatis jalan saat login Windows? Klik kanan `run.bat` → *Send to* → *Desktop (create shortcut)*, lalu pindahkan shortcut itu ke folder `shell:startup` (ketik di Run). Jendela tetap harus terbuka.

## B. Penyedia AI & profil

5. Buka **Pengaturan → Profil & Penyedia AI**. Pilih **Penyedia AI**:
   - **OpenAI**: isi key `sk-...`, model default `gpt-5-mini`.
   - **Claude (Anthropic)**: isi key `sk-ant-...`, model default `claude-sonnet-5-5` (bisa diganti, mis. `claude-haiku-5-5` untuk lebih murah). Nama model harus yang tersedia di akun Anda.
   - Centang **Tampilkan** di samping kolom key jika ingin melihat teksnya saat menempel.
   - Jika kolom tidak bisa di-paste, key dibaca otomatis dengan urutan: isian dashboard → environment → file:
     1. OpenAI: simpan ke `openai_key.txt`, atau set `OPENAI_API_KEY`.
     2. Claude: simpan ke `anthropic_key.txt`, atau set `ANTHROPIC_API_KEY`.
     3. File berisi satu baris key saja di folder `linkedin-automation`.
6. Klik **Simpan profil & penyedia AI**. Pill kanan atas menjadi **OpenAI siap** atau **Claude siap**, dan badge di Pengaturan menunjukkan sumber key.
7. (Opsional) Sunting **Ringkasan profil** agar nada dan konteks post sesuai. Konten post ditulis dalam bahasa Inggris (mengikuti prompt repo).
8. Untuk menguji tanpa menunggu jadwal: klik **Jalankan sekarang** di Dashboard. Draft akan muncul di Antrean review.

### Email preview via Resend

- Buat API key di https://resend.com/api-keys, lalu verifikasi domain di menu **Domains**.
- Buka **Pengaturan → Email preview (Resend)**: isi **Pengirim** memakai domain terverifikasi (mis. `LinkedIn Bot <bot@domain-anda.com>`), **Email tujuan**, dan **Resend API key**. Klik **Simpan pengaturan email**, lalu **Kirim email uji**.
- Jika kolom key tidak bisa di-paste: simpan key ke `resend_key.txt` (satu baris) atau set `RESEND_API_KEY`, lalu jalankan ulang `run.bat`.
- Preview dikirim otomatis setiap draft baru selesai dibuat (termasuk dari **Jalankan sekarang** dan jadwal harian). Tombol **Kirim preview ke email** di dashboard mengirim ulang kapan saja.
- Email berisi teks post + tombol **Setujui & jadwalkan** dan **Batalkan**. Post tetap tidak terbit tanpa persetujuan; tombol setujui menjadwalkan post pada jam publikasi.
- Tautan di email memakai **Public base URL** bila diisi (bisa dibuka dari HP); jika kosong, tautan memakai `http://127.0.0.1:8080` dan hanya berfungsi di komputer ini.
- `onboarding@resend.dev` hanya bisa mengirim ke email pemilik akun Resend; untuk alamat lain gunakan domain terverifikasi.

## C. Jadwal

9. Buka **Pengaturan → Jadwal otomatisasi**.
10. Pilih **interval pembuatan draft**:
    - Setiap hari pada jam tertentu (default 18:30), atau
    - Setiap N jam, atau
    - Setiap N menit.
11. Pilih **waktu publikasi**:
    - *Pada jam tertentu* (default 19:30): disetujui sebelum jam itu → terbit pada jam tersebut; disetujui setelahnya → langsung dicoba terbit; atau
    - *Langsung setelah disetujui*.
12. Klik **Simpan jadwal**. Dashboard menampilkan **Draft berikutnya** dan **Posting berikutnya** dalam WIB.

Semua jam memakai **WIB (UTC+7)**. Jam publikasi hanya dipakai untuk mode "Pada jam tertentu".

## D. Menghubungkan LinkedIn (sekali, lalu perpanjang ±60 hari)

LinkedIn mewajibkan redirect URL **HTTPS**, sehingga OAuth butuh tunnel HTTPS sementara. Posting tetap dilakukan dari server lokal.

13. Jika belum punya, buat **LinkedIn Page** gratis di `linkedin.com/pages/create`. LinkedIn mewajibkan Page untuk membuat aplikasi.
14. Buka **developer.linkedin.com → My apps → Create app**. Isi nama, pilih Page tadi, setujui terms.
15. Buka tab **Products** dan tambahkan:
    - **Share on LinkedIn** → memberi scope `w_member_social` (wajib untuk posting).
    - **Sign In with LinkedIn using OpenID Connect** → memberi scope `openid` dan `profile`.
16. Pasang Cloudflare Tunnel sekali: buka CMD/PowerShell baru, jalankan
    ```
    winget install --id Cloudflare.cloudflared
    ```
    Tutup dan buka lagi terminalnya.
17. Jalankan tunnel:
    ```
    cloudflared tunnel --url http://localhost:8080
    ```
    Catat URL yang muncul, misalnya `https://kata-kata-acak.trycloudflare.com` (berubah setiap tunnel dijalankan ulang).
18. Di **Pengaturan → LinkedIn**, isi **Client ID**, **Client Secret** (dari tab *Auth* aplikasi LinkedIn), dan **Public base URL** = URL tunnel tadi (tanpa garis miring di akhir). Klik **Simpan kredensial LinkedIn**. Perhatikan baris **Redirect URL** yang ditampilkan.
19. Di tab **Auth** aplikasi LinkedIn, tambahkan **Authorized redirect URL** yang **persis sama**, mis.:
    ```
    https://kata-kata-acak.trycloudflare.com/auth/linkedin/callback
    ```
20. Buka dashboard **lewat URL tunnel** (bukan `127.0.0.1`), mis. `https://kata-kata-acak.trycloudflare.com/pengaturan#linkedin`. Klik **Hubungkan LinkedIn (OAuth)** → izinkan akses → kembali ke Pengaturan, status **Terhubung sebagai ...**.
21. Tutup tunnel (**Ctrl+C**) setelah terhubung. Dashboard dan posting tetap berjalan dari `http://127.0.0.1:8080`.
22. **Alternatif tanpa tunnel:** gunakan tool pembuat token OAuth di portal developer LinkedIn untuk aplikasi Anda, pilih scope `openid profile w_member_social`, lalu tempel tokennya di **Pengaturan → LinkedIn → Alternatif: tempel access token manual**. Token biasanya berlaku ±60 hari.

> URL tunnel berubah setiap dijalankan ulang. Jika perlu menghubungkan ulang (token kedaluwarsa), jalankan tunnel lagi, perbarui **Public base URL** dan redirect URL di aplikasi LinkedIn, lalu ulangi langkah 20. Untuk domain tetap, buat *named tunnel* Cloudflare (perlu akun Cloudflare).

## E. Pemakaian harian

23. Saat jadwal tiba, draft baru muncul di **Antrean review** (status *Menunggu persetujuan*). Anda juga bisa membuat draft kapan saja dengan **Jalankan sekarang** atau **Buat draft manual**.
24. Edit teks di kolom kiri. Pratinjau tampilan LinkedIn di kolom kanan dan penghitung karakter (maks. 3.000) ikut berubah. Klik **Simpan perubahan**.
25. Klik **Setujui & jadwalkan** untuk mengikuti jam publikasi, atau **Setujui + posting sekarang** untuk segera menerbitkan (diproses dalam ±10 detik).
26. Jika teks diedit setelah disetujui, status otomatis kembali ke *Menunggu persetujuan* — setujui lagi. Ini disengaja: yang terbit selalu versi terakhir yang Anda setujui.
27. Pantau status: *Disetujui* → *Terbit* (URN LinkedIn tampil di Riwayat). Bila gagal, pesan error tampil; perbaiki penyebabnya lalu klik **Coba posting lagi**.
28. **Batalkan** mencegah post terbit. Draft *Gagal*/*Dibatalkan* bisa dihapus dari Riwayat.

Catatan jam: scheduler hanya berjalan selama `run.bat` terbuka. Jika laptop tidur/mati saat jam draft, aplikasi membuat satu draft susulan begitu dinyalakan lagi (mode harian), dan post yang telat akan dicoba terbit saat aplikasi hidup kembali.

## F. Keamanan & data

29. Dashboard hanya mendengarkan di `127.0.0.1` sehingga tidak bisa diakses dari jaringan lain. Saat tunnel aktif, URL tunnel **bisa diakses publik** — pasang **kata sandi dashboard** dulu (Pengaturan → Keamanan), dan tutup tunnel setelah OAuth selesai.
30. API key dan token LinkedIn tersimpan di `data/app.db` (lokal, tidak terenkripsi). Jika memakai `openai_key.txt` / `anthropic_key.txt` / `resend_key.txt`, file itu juga berisi key apa adanya di folder aplikasi (sudah masuk `.gitignore`). Jangan bagikan file-file tersebut; backup = salin `data/app.db`.
31. Jangan pernah menempelkan API key/token ke chat, screenshot, atau commit Git.

## G. Troubleshooting

| Gejala | Penyebab & solusi |
|---|---|
| `setup.bat` gagal SSL | Antivirus/proxy memeriksa TLS. Script sudah mencoba `--trusted-host`; pastikan internet stabil. |
| OpenAI 401 / "Incorrect API key" | Key salah/kosong. Perbaiki di Pengaturan. |
| OpenAI 429 / "no credits remaining" | Kredit API habis. Isi saldo di platform.openai.com → Billing, atau ganti ke Claude. |
| Claude 401 / "invalid x-api-key" | Key Claude salah/kosong. Perbaiki di Pengaturan. |
| Claude 404 / model tidak dikenal | Nama model tidak tersedia di akun Anda. Cek daftar model lewat `GET https://api.anthropic.com/v1/models`, lalu samakan isian **Model Claude**. |
| Claude 429 / "credit balance is too low" | Kredit Anthropic habis. Isi saldo di console.anthropic.com → Plans & Billing. |
| Resend 401 / "API key is invalid" | Key Resend salah/kosong. Perbaiki di Pengaturan → Email preview. |
| Resend 403 "domain is not verified" | Domain pengirim belum diverifikasi di Resend → Domains. Atau pakai `onboarding@resend.dev` hanya untuk email pemilik akun. |
| Resend 422 "Invalid `from`" | Format pengirim salah. Gunakan `Nama <alamat@domain-terverifikasi.com>`. |
| Email preview tidak masuk | Cek Resend → Logs, folder spam, dan pastikan **Kirim preview otomatis** dicentang. Status terakhir tampil di halaman Pengaturan. |
| Kolom API key tidak bisa di-paste | Centang **Tampilkan** lalu coba Ctrl+V; jika tetap gagal, simpan key ke `openai_key.txt` / `anthropic_key.txt` atau set environment (lihat bagian B). |
| OpenAI 404 model | Model tidak tersedia untuk akun Anda. Ganti model (mis. `gpt-5-mini` → `gpt-4.1-mini`). |
| Post gagal: "LinkedIn belum terhubung" | Hubungkan LinkedIn (bagian D) atau tempel token manual. |
| LinkedIn 401 saat posting | Token kedaluwarsa/tidak valid. Hubungkan ulang. |
| LinkedIn 403 | Scope kurang. Pastikan produk **Share on LinkedIn** + **Sign In with LinkedIn using OpenID Connect** aktif dan OAuth diulang. |
| LinkedIn `INVALID_VERSION` | Header versi API tidak diterima. Samakan **Versi API LinkedIn** dengan versi rilis terbaru (`YYYYMM`, mis. `202601`). |
| "Redirect URI mismatch" di LinkedIn | Redirect URL di aplikasi LinkedIn harus sama persis (https, domain tunnel, path `/auth/linkedin/callback`). |
| OAuth "state tidak valid/kedaluwarsa" | Mulai lagi dari URL tunnel di browser yang sama, selesaikan < 15 menit. |
| Port 8080 dipakai | Jalankan `set PORT=8090` lalu `run.bat`, atau ubah port di `run.bat`/`app.py`. |
| Tidak ada draft otomatis | Cek jam & interval, pastikan `run.bat` terbuka, dan OpenAI key terisi. |
| Pratinjau/karakter tidak berubah | Muat ulang halaman (JS `static/app.js`). |

## H. Struktur proyek

```
linkedin-automation/
├─ app.py               # dashboard Flask, route, OAuth callback, password & CSRF
├─ db.py                # SQLite: settings, posts (status, jadwal, URN)
├─ scheduler.py         # ticker: buat draft berkala + publikasikan yang disetujui
├─ prompts.py           # prompt & pillar harian dari repo n8n
├─ openai_client.py     # OpenAI Responses API
├─ anthropic_client.py  # Claude Messages API
├─ resend_client.py     # Resend email API
├─ email_preview.py     # render + kirim preview, token setujui/batalkan
├─ linkedin_client.py   # OAuth 2.0 + POST /v2/ugcPosts (REST /rest/posts memotong teks)
├─ tls.py               # pakai trust store OS (antivirus/proxy TLS)
├─ templates/ static/   # UI dashboard (bahasa Indonesia)
├─ data/app.db          # dibuat saat pertama jalan (jangan di-commit)
├─ openai_key.txt       # opsional: key OpenAI jika tidak bisa paste (jangan di-commit)
├─ anthropic_key.txt    # opsional: key Claude jika tidak bisa paste (jangan di-commit)
├─ resend_key.txt       # opsional: key Resend jika tidak bisa paste (jangan di-commit)
├─ setup.bat run.bat
```

Data post: `post_date`, `text`, `status`, `publish_at`, `posted_at`, `linkedin_urn`, `error` — mirip Data Table `linkedin_posts` di repo.

## I. Status pengujian

Sudah diuji di mesin ini (browser, tanpa kredensial asli): pembuatan draft manual dan otomatis (jalur error API), edit + pratinjau langsung, penolakan persetujuan untuk teks kosong, persetujuan terjadwal vs langsung, gate persetujuan (tanpa setujui tidak ada publikasi), publikasi gagal dengan pesan jelas, retry, batal, hapus, Riwayat, pengaturan jadwal (harian/N jam/N menit), kunci kata sandi + login, CSRF, OAuth URL & gate, validasi token LinkedIn (401 asli dari LinkedIn), dan logika waktu scheduler. Batas 3.000 karakter divalidasi di server dan UI, tetapi belum diuji dengan teks sepanjang itu.

Sudah diuji dengan kredensial asli: generate nyata via Claude, publish nyata ke LinkedIn lewat OAuth akun pemilik, dan email preview via Resend. Dari uji publish nyata ditemukan bahwa `POST /rest/posts` menyimpan hanya sebagian teks panjang (898 karakter terkirim, 397 karakter tersimpan dan terpotong di tengah kalimat), sedangkan `POST /v2/ugcPosts` menyimpan teks utuh (terverifikasi 907 karakter tampil di permalink). Karena itu publisher memakai `ugcPosts`. API tidak bisa membaca ulang post dengan scope `w_member_social` (`/rest/posts`, `/v2/ugcPosts`, `/v2/shares` GET → 403), jadi verifikasi dilakukan dengan membuka permalink publik, dan post yang salah dihapus lewat `DELETE /rest/posts/{urn}`.

Sudah diuji end-to-end oleh pemilik akun: draft dibuat Claude, email preview terkirim, disetujui dari email, lalu terbit di LinkedIn. Tampilan visual tidak dapat di-screenshot di lingkungan pengembangan, tetapi struktur DOM dan CSS sudah diperiksa.
