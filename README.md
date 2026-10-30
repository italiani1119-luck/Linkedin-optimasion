# Linkedin-optimasion

Configuration snapshot, source code, and architecture diagrams for the LinkedIn personal-branding
automation of Ita Liani.

## Aplikasi lokal (versi aktif)

`app/` berisi aplikasi Python/Flask yang menggantikan routine Lindy/n8n. Draft dibuat terjadwal
oleh AI (Claude, fallback OpenAI), dikirim ke email untuk ditinjau, boleh **diminta revisi langsung
dari email**, dan **hanya terbit ke LinkedIn setelah disetujui**.

```
Jadwal tiba ──> Draft dibuat (Claude) ──> Email preview (Resend)
                                            │
                          revisi ◄──────────┤
                                            ▼
                                   Setujui ──> 19:30 WIB ──> LinkedIn API (ugcPosts)
                                   Batalkan ─> tidak pernah terbit
```

- Panduan pemasangan dan pemakaian lengkap: [`app/README.md`](app/README.md)
- Diagram arsitektur + alur status: [`docs/diagrams/local-app-architecture.md`](docs/diagrams/local-app-architecture.md)
  (versi gambar: [`local-app-architecture.svg`](docs/diagrams/local-app-architecture.svg))

## Isi repo

| Path | Keterangan |
|---|---|
| `app/` | Aplikasi lokal: Flask, SQLite, scheduler, klien Claude/OpenAI/Resend/LinkedIn, template dashboard |
| `docs/diagrams/` | Diagram arsitektur aplikasi lokal (Mermaid + SVG) |
| `workflows/` | Arsip konfigurasi Lindy routines v3 (2026-10-27) dan ringkasan alur lama |

## Prinsip

- Post tidak pernah terbit tanpa persetujuan eksplisit.
- Konten berbahasa Inggris, berbasis pengalaman kerja offline (executive support, procurement,
  vendor coordination), tanpa klaim pengalaman remote atau angka yang dibuat-buat.
- Kredensial (API key, token LinkedIn) tidak disimpan di repo: hanya di database lokal komputer
  atau file `*_key.txt` yang di-ignore oleh git.
