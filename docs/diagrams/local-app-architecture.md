# Arsitektur aplikasi lokal (LinkedIn Auto-Post)

Aplikasi Python/Flask yang berjalan di komputer sendiri. Draft dibuat terjadwal oleh AI,
dikirim ke email untuk ditinjau, boleh direvisi, dan **hanya terbit ke LinkedIn setelah disetujui**.

```mermaid
flowchart TD
  subgraph LOCAL["Komputer lokal (Windows)"]
    UI["Dashboard Flask<br/>127.0.0.1:8080<br/>login + CSRF"]
    SCH["Scheduler thread<br/>tick 10 detik"]
    DB[("SQLite data/app.db<br/>settings · posts · status")]
  end

  BROWSER["Browser user"] -->|"localhost atau tunnel"| UI
  CF["Cloudflare quick tunnel<br/>HTTPS publik"] --> UI
  UI <--> DB
  SCH <--> DB

  subgraph GEN["1. Pembuatan draft"]
    SCH -->|"jadwal generate (mis. 18:30)"| PROMPT["Prompt pillar harian<br/>pengalaman kerja offline"]
    PROMPT --> AI["Claude Messages API<br/>fallback: OpenAI Responses"]
    AI --> DRAFT["Draft teks<br/>status: pending"]
  end
  DRAFT --> DB

  subgraph REVIEW["2. Preview, revisi, persetujuan"]
    DB --> MAIL["Resend API<br/>email preview"]
    MAIL --> ACT{"Aksi dari email"}
    ACT -->|Setujui| APPR["status: approved<br/>publish_at 19:30 WIB"]
    ACT -->|Minta revisi| REV["Tulis ulang via AI<br/>status: pending"]
    ACT -->|Batalkan| CANC["status: cancelled"]
    REV --> MAIL
  end
  APPR --> DB
  CANC --> DB

  subgraph PUB["3. Publikasi otomatis"]
    SCH -->|"publish_at <= sekarang"| CLAIM["Klaim atomik<br/>status: publishing"]
    CLAIM --> LI["LinkedIn REST API<br/>POST /rest/posts"]
    LI -->|"x-restli-id"| POSTED["status: posted<br/>+ linkedin_urn"]
  end
  POSTED --> DB

  UI -->|"OAuth 2.0 + PKCE state<br/>scope openid profile w_member_social"| OAUTH["LinkedIn authorization<br/>callback via HTTPS tunnel"]
  OAUTH -->|"access token + sub"| DB
```

## Alur status draft

```mermaid
stateDiagram-v2
  [*] --> pending: draft dibuat
  pending --> pending: minta revisi
  pending --> approved: setujui
  approved --> pending: minta revisi
  approved --> publishing: publish_at tercapai
  publishing --> posted: LinkedIn menerima
  publishing --> failed: error API
  pending --> cancelled: batalkan
  approved --> cancelled: batalkan
  failed --> pending: revisi / buat ulang
  posted --> [*]
  cancelled --> [*]
```

## Catatan

- Semua jadwal memakai WIB (UTC+7), tanpa DST.
- Tidak ada draft yang terbit tanpa status `approved`; scheduler mengklaim draft secara atomik
  agar tidak ada post ganda.
- Kredensial (API key, access token) disimpan di database lokal atau file `*_key.txt` yang
  tidak ikut di-commit.
