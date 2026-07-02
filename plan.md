# PLAN.md
# Python Temporary Email Client

## Project Goal

Membangun library Python yang dapat berinteraksi dengan API internal CleanTempMail tanpa menggunakan web scraping.

Library harus mampu:

- Generate temporary email
- Mengambil daftar domain
- Monitoring inbox secara real-time (Server-Sent Events)
- Membaca email
- Menghapus email
- Extract verification links
- Support async monitoring
- Mudah diintegrasikan ke project lain

---

# Requirements

Python >= 3.11

Dependencies:

- requests
- sseclient-py
- beautifulsoup4
- lxml
- pydantic
- asyncio
- typing_extensions

Semua dependency harus tercantum pada `requirements.txt`.

---

# Folder Structure

```
tempmail/
│
├── __init__.py
├── client.py
├── models.py
├── monitor.py
├── parser.py
├── exceptions.py
├── utils.py
├── config.py
└── constants.py

examples/
│
├── generate_email.py
├── monitor_email.py
├── read_email.py
├── delete_email.py
└── telegram_notify.py

tests/
│
├── test_generate.py
├── test_domains.py
├── test_monitor.py
├── test_read.py
└── test_delete.py

requirements.txt

README.md
```

---

# Base URL

```
https://cleantempmail.com
```

Default Headers

```
Origin: https://cleantempmail.com
Referer: https://cleantempmail.com/
User-Agent: modern browser user-agent
Accept: application/json
```

Header harus otomatis ditambahkan pada setiap request.

---

# API Endpoints

## Generate Email

```
GET /api/generate-email
POST /api/generate-email
```

Return:

```
Email Address
```

Method

```
client.generate_email()
```

---

## Get Domains

```
GET /api/domains?limit=N
```

Method

```
client.get_domains(limit=100)
```

Return:

```
List[str]
```

---

## Get Inbox

```
GET /api/emails?email={address}
```

Method

```
client.get_messages(email)
```

Return:

```
List[Email]
```

---

## Read Email

```
GET /api/email/{id}
```

Method

```
client.read_message(id)
```

Return

```
Email
```

---

## Delete Email

```
DELETE /api/email/{id}
```

Method

```
client.delete_message(id)
```

---

## Monitor

```
GET /api/events?email={address}
```

Menggunakan Server Sent Events.

Method

```
client.monitor(email)
```

Harus menghasilkan iterator / callback ketika email baru diterima.

---

# Models

Gunakan Pydantic.

## EmailAddress

```
address
username
domain
created_at
```

---

## EmailMessage

```
id
from
to
subject
text
html
date
attachments
```

---

# Parser Module

Parser bertugas:

## Extract Links

Input

```
HTML
```

Output

```
List[str]
```

---

## Extract OTP

Cari OTP:

- 4 digit
- 5 digit
- 6 digit
- 8 digit

Return

```
123456
```

Jika tidak ditemukan

```
None
```

---

## Extract Verification URL

Cari:

```
https://...
```

Return

```
List[str]
```

---

# Monitor Module

Harus support:

## Blocking

```
for event in monitor():
```

---

## Callback

```
monitor(callback=my_callback)
```

---

## Async

```
await monitor_async()
```

---

# Retry Policy

Untuk seluruh request

Jika gagal:

- retry 3x
- exponential backoff

Contoh

```
1 second

2 second

4 second
```

---

# Exceptions

Buat custom exception

```
TempMailException
```

Turunannya

```
APIError

RateLimitError

EmailNotFound

ConnectionError

ParsingError
```

---

# Logging

Gunakan module logging bawaan Python.

Support level

```
INFO

WARNING

ERROR

DEBUG
```

---

# Telegram Example

Contoh project

Monitor inbox

↓

Ada email baru

↓

Extract verification link

↓

Kirim ke Telegram

---

# README

README harus menjelaskan:

Install

Generate email

Read inbox

Read email

Delete email

Real-time monitoring

Extract OTP

Extract Links

Error Handling

---

# Examples

Minimal:

generate_email.py

```
client.generate_email()
```

---

monitor_email.py

```
client.monitor()
```

---

read_email.py

```
client.read_message()
```

---

delete_email.py

```
client.delete_message()
```

---

telegram_notify.py

Monitoring

↓

Extract Link

↓

Send Telegram

---

# Code Quality

Wajib:

- Type Hint
- Docstring
- Modular
- Clean Architecture
- Black formatting
- PEP8
- Tidak boleh ada hardcoded value
- Mudah diperluas

---

# Future Features (Not Implemented Yet)

- Multiple inbox monitoring
- Async HTTP client (httpx)
- Proxy support
- SOCKS5 support
- Export email ke JSON
- Export email ke Markdown
- Attachment downloader
- CLI
- Docker image
- FastAPI wrapper
- Redis cache
- SQLite cache
- Web dashboard

---

# Important

Sebelum implementasi endpoint, WAJIB melakukan validasi bahwa endpoint benar-benar merespons sesuai dokumentasi.

Jika format response berbeda, model harus menyesuaikan response asli.

Jangan mengasumsikan struktur JSON.

Semua parsing harus berdasarkan response aktual.

Apabila endpoint tertentu tidak tersedia, library harus memberikan exception yang jelas, bukan crash.