# 📬 TempMail — Python Temporary Email Client

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A clean, modular Python library for interacting with the **CleanTempMail** API.  
Generate disposable email addresses, monitor inboxes in real-time, extract OTPs, and more — without any web scraping.
fix webhooks
---

## ✨ Features

- ✅ Generate random temporary email addresses
- ✅ List available email domains
- ✅ Fetch inbox messages
- ✅ Read individual emails
- ✅ Delete emails
- ✅ Real-time inbox monitoring via **Server-Sent Events (SSE)**
- ✅ Extract **OTP codes** (4, 5, 6, 8 digits)
- ✅ Extract **verification / confirmation links**
- ✅ Automatic retry with exponential backoff
- ✅ Async support via `asyncio`
- ✅ Fully typed with Pydantic models
- ✅ Clean exception hierarchy

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourname/tempmail-generator.git
cd tempmail-generator
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **Requires:** Python 3.11+

---

## 🚀 Quick Start

```python
from tempmail import TempMailClient

with TempMailClient() as client:
    # Generate a temporary email address
    email = client.generate_email()
    print(email.address)   # e.g. user123@example.com

    # Check the inbox
    messages = client.get_messages(email.address)
    for msg in messages:
        print(msg.subject, msg.sender)
```

---

## 📖 Usage Guide

### Generate an Email

```python
from tempmail import TempMailClient

client = TempMailClient()
email = client.generate_email()

print(email.address)    # full address: user@domain.com
print(email.username)   # user
print(email.domain)     # domain.com
print(email.created_at) # datetime object
```

---

### List Available Domains

```python
domains = client.get_domains(limit=10)
# ['example.com', 'tempmail.io', ...]
```

---

### Read Inbox

```python
messages = client.get_messages("user@domain.com")

for msg in messages:
    print(f"[{msg.id}] {msg.subject} — from {msg.sender}")
```

---

### Read a Specific Email

```python
from tempmail import EmailNotFound

try:
    msg = client.read_message("abc123")
    print(msg.subject)
    print(msg.text)
    print(msg.html)
except EmailNotFound:
    print("Email not found!")
```

---

### Delete an Email

```python
from tempmail import EmailNotFound

try:
    success = client.delete_message("abc123")
    print("Deleted!" if success else "Could not delete.")
except EmailNotFound:
    print("Email already gone.")
```

---

### Real-time Monitoring

The `monitor()` method uses **Server-Sent Events** for live inbox watching.

#### Option 1 — Blocking Iterator

```python
for msg in client.monitor("user@domain.com"):
    print(f"New email: {msg.subject}")
```

#### Option 2 — Callback

```python
def on_email(msg):
    print(f"Received: {msg.subject}")

client.monitor("user@domain.com", callback=on_email)
```

#### Option 3 — Async

```python
import asyncio
from tempmail import monitor_async

async def handler(msg):
    print(f"Async: {msg.subject}")

asyncio.run(monitor_async("user@domain.com", callback=handler))
```

---

### Extract OTP

Automatically detects OTP codes of 4, 5, 6, or 8 digits.

```python
from tempmail import extract_otp

otp = extract_otp(msg.text, msg.html)
if otp:
    print(f"OTP: {otp}")   # e.g. "847291"
```

---

### Extract Links

```python
from tempmail import extract_links, extract_verification_urls

# All hyperlinks from HTML
all_links = extract_links(msg.html)

# Only verification/confirmation links
verify_links = extract_verification_urls(msg.html, msg.text)
for link in verify_links:
    print(link)
```

---

## ⚙️ Configuration

Customize the client behavior by passing a `TempMailConfig`:

```python
from tempmail import TempMailClient, TempMailConfig

config = TempMailConfig(
    timeout=60,                  # HTTP timeout in seconds
    retry_max_attempts=5,        # Max retries on failure
    retry_base_delay=2.0,        # Initial backoff delay
    retry_exponential_base=2,    # Exponential multiplier
    default_domains_limit=50,    # Default domain list size
    verify_ssl=True,             # SSL certificate verification
)

client = TempMailClient(config=config)
```

---

## 🚦 Retry Policy

All API requests automatically retry up to `retry_max_attempts` times on transient errors.

| Attempt | Delay    |
|---------|----------|
| 1       | 1 second |
| 2       | 2 seconds|
| 3       | 4 seconds|

---

## 🔥 Error Handling

All exceptions derive from `TempMailException`:

```python
from tempmail import (
    TempMailException,
    APIError,
    RateLimitError,
    EmailNotFound,
    ConnectionError,
    ParsingError,
)

try:
    msg = client.read_message("xyz")
except EmailNotFound as e:
    print(f"Not found: {e.email_id}")
except RateLimitError as e:
    print(f"Rate limited. Retry after: {e.retry_after}s")
except APIError as e:
    print(f"API error {e.status_code}: {e.message}")
except ConnectionError as e:
    print(f"Network error: {e}")
except ParsingError as e:
    print(f"Parse error: {e.raw}")
except TempMailException as e:
    print(f"Generic error: {e}")
```

---

## 📊 Data Models

### `EmailAddress`

| Field       | Type       | Description                     |
|-------------|------------|---------------------------------|
| `address`   | `str`      | Full email address              |
| `username`  | `str`      | Local part (before `@`)         |
| `domain`    | `str`      | Domain part (after `@`)         |
| `created_at`| `datetime` | Generation timestamp            |

### `EmailMessage`

| Field         | Type              | Description                      |
|---------------|-------------------|----------------------------------|
| `id`          | `str`             | Unique message ID                |
| `sender`      | `str`             | Sender email address             |
| `to`          | `str`             | Recipient address                |
| `subject`     | `str`             | Email subject                    |
| `text`        | `str`             | Plain-text body                  |
| `html`        | `str`             | HTML body                        |
| `date`        | `datetime \| None`| Received timestamp               |
| `attachments` | `list[Attachment]`| File attachments                 |

---

## 🔧 Logging

```python
import logging
from tempmail import setup_logging

setup_logging(level=logging.DEBUG)
```

Supported levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`

---

## 🗂️ Project Structure

```
tempmail/
├── __init__.py      # Public API
├── client.py        # Core HTTP client
├── models.py        # Pydantic data models
├── monitor.py       # SSE real-time monitor + async wrapper
├── parser.py        # OTP & link extraction
├── exceptions.py    # Custom exception hierarchy
├── utils.py         # Retry decorator, logging helpers
├── config.py        # Runtime configuration
└── constants.py     # All hardcoded values

examples/
├── generate_email.py
├── monitor_email.py
├── read_email.py
├── delete_email.py
└── telegram_notify.py

tests/
├── test_generate.py
├── test_domains.py
├── test_monitor.py
├── test_read.py
└── test_delete.py
```

---

## 🧪 Running Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## 📡 Interactive Telegram Bot

The project includes a fully interactive Telegram bot that allows you to manage multiple temporary emails directly from your chat.

### Features
- `/generate` - Create a new email address and automatically monitor it in the background via Server-Sent Events (SSE).
- `/check` - Manually force a check for new emails on all active addresses (Fallback).
- `/list` - View all active emails currently being monitored.
- `/stop` - Stop monitoring an email via an interactive inline keyboard.
- `/autocheck` - Toggle automatic background monitoring via inline buttons.
- Automatically extracts OTP codes and verification links from incoming emails.

### Running Locally
```bash
set TELEGRAM_BOT_TOKEN=your_bot_token_here
python examples/interactive_telegram_bot.py
```
*(No Chat ID is required; the bot automatically learns your Chat ID when you interact with it).*

---

## 🐳 Deployment

Looking to deploy this bot to production (e.g. on Coolify, VPS, or Docker)?  
Read our detailed **[Deployment Guide](docs/DEPLOYMENT.md)**.

---

## 🔮 Future Features

- [x] Docker image
- [ ] Multiple inbox monitoring
- [ ] Async HTTP client (httpx)
- [ ] Proxy / SOCKS5 support
- [ ] Export email to JSON / Markdown
- [ ] Attachment downloader
- [ ] CLI interface
- [ ] FastAPI wrapper
- [ ] Redis / SQLite caching
- [ ] Web dashboard

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
