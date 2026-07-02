"""
API Explorer for CleanTempMail - Analisa semua endpoint & response yang tersedia.
Jalankan: python api_explorer.py
"""

import json
import requests
import time

BASE_URL = "https://cleantempmail.com"
HEADERS = {
    "Origin": "https://cleantempmail.com",
    "Referer": "https://cleantempmail.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
}

session = requests.Session()
session.headers.update(HEADERS)

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def pretty(data):
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))

def test_endpoint(method, path, params=None, json_body=None, label=""):
    url = BASE_URL + path
    print(f"\n[{method}] {url}")
    if params:
        print(f"  params: {params}")
    if json_body:
        print(f"  body: {json_body}")
    try:
        resp = session.request(method, url, params=params, json=json_body, timeout=15)
        print(f"  STATUS: {resp.status_code}")
        print(f"  Headers: {dict(resp.headers)}")
        try:
            data = resp.json()
            print("  RESPONSE:")
            pretty(data)
            return data, resp.status_code
        except Exception:
            print(f"  RAW: {resp.text[:500]}")
            return resp.text, resp.status_code
    except Exception as e:
        print(f"  ERROR: {e}")
        return None, None

# ──────────────────────────────────────────────
print_section("1. GET /api/domains  (berbagai limit)")
for limit in [5, 10, 50]:
    test_endpoint("GET", "/api/domains", params={"limit": limit}, label=f"limit={limit}")
    time.sleep(0.5)

# Coba tanpa limit
test_endpoint("GET", "/api/domains", label="tanpa limit")

# ──────────────────────────────────────────────
print_section("2. POST /api/generate-email  (random)")
gen_result, _ = test_endpoint("POST", "/api/generate-email", json_body={})
time.sleep(1)

# Coba dengan custom username & domain
print("\n-- Coba custom username --")
test_endpoint("POST", "/api/generate-email", json_body={"username": "valtest123"})
time.sleep(0.5)

# Coba dengan domain tertentu
print("\n-- Coba dengan domain --")
domains_resp, _ = test_endpoint("GET", "/api/domains", params={"limit": 3})
available_domains = []
if isinstance(domains_resp, dict):
    data = domains_resp.get("data", {})
    available_domains = data.get("domains", [])
    
if available_domains:
    first_domain = available_domains[0]
    print(f"\n-- Coba generate dengan domain={first_domain} --")
    test_endpoint("POST", "/api/generate-email", json_body={"domain": first_domain})
    time.sleep(0.5)
    
    print(f"\n-- Coba generate dengan username+domain --")
    test_endpoint("POST", "/api/generate-email", json_body={"username": "valtesting", "domain": first_domain})
    time.sleep(0.5)

# ──────────────────────────────────────────────
# Ambil email dari generate tadi
generated_email = None
if isinstance(gen_result, dict):
    data = gen_result.get("data", gen_result)
    generated_email = data.get("email") or data.get("address")

print_section(f"3. GET /api/emails  (inbox untuk: {generated_email})")
if generated_email:
    inbox_result, _ = test_endpoint("GET", "/api/emails", params={"email": generated_email})
    time.sleep(0.5)
    
    # Coba query param lain
    print("\n-- Coba dengan param 'page' --")
    test_endpoint("GET", "/api/emails", params={"email": generated_email, "page": 1})
    time.sleep(0.5)
    
    print("\n-- Coba dengan param 'limit' --")
    test_endpoint("GET", "/api/emails", params={"email": generated_email, "limit": 5})
    time.sleep(0.5)

# ──────────────────────────────────────────────
print_section("4. GET /api/email/<id>  (baca pesan tertentu)")
print("  (skip - tidak ada pesan masuk saat ini, tapi test endpoint 404)")
test_endpoint("GET", "/api/email/fake_id_test_12345")
time.sleep(0.5)

# ──────────────────────────────────────────────
print_section("5. DELETE /api/email/<id>")
print("  (skip - tidak ada pesan, test endpoint 404)")
test_endpoint("DELETE", "/api/email/fake_id_test_12345")
time.sleep(0.5)

# ──────────────────────────────────────────────
print_section("6. Probe endpoint LAIN yang mungkin ada")

# Endpoint-endpoint umum yang sering ada di API tempmail
extra_endpoints = [
    ("GET",    "/api/mailbox",          None),
    ("GET",    "/api/inbox",            {"email": generated_email} if generated_email else None),
    ("POST",   "/api/mailbox/create",   {}),
    ("DELETE", "/api/emails",           None),
    ("DELETE", "/api/mailbox",          None),
    ("GET",    "/api/attachments",      None),
    ("GET",    "/api/attachment",       None),
    ("GET",    "/api/status",           None),
    ("GET",    "/api/health",           None),
    ("GET",    "/api/",                 None),
    ("GET",    "/api",                  None),
    ("GET",    "/api/docs",             None),
    ("GET",    "/api/stats",            None),
    ("GET",    "/api/email",            None),
    ("POST",   "/api/email/delete",     {"id": "test"}),
    ("GET",    "/api/version",          None),
    ("GET",    "/api/ping",             None),
    ("DELETE", f"/api/emails/{generated_email}" if generated_email else "/api/emails/test@test.com", None),
    ("GET",    "/api/email/search",     {"q": "test"}),
    ("POST",   "/api/generate",         {}),
    ("POST",   "/api/create",           {}),
    ("POST",   "/api/mailbox/generate", {}),
]

for method, path, params_or_body in extra_endpoints:
    is_post = method == "POST"
    result, status = test_endpoint(
        method, path,
        params=params_or_body if not is_post else None,
        json_body=params_or_body if is_post else None,
    )
    time.sleep(0.3)

# ──────────────────────────────────────────────
print_section("7. GET /api/events  (cek header SSE)")
print("  (hanya cek response headers, tidak streaming)")
url = BASE_URL + "/api/events"
try:
    resp = session.get(url, params={"email": generated_email or "test@test.com"}, 
                       timeout=5, stream=True)
    print(f"  STATUS: {resp.status_code}")
    print(f"  Content-Type: {resp.headers.get('Content-Type')}")
    print(f"  Headers: {dict(resp.headers)}")
    # Baca beberapa byte pertama saja
    raw = next(resp.iter_content(chunk_size=512), b"")
    print(f"  RAW (first 512 bytes): {raw.decode('utf-8', errors='replace')}")
    resp.close()
except Exception as e:
    print(f"  ERROR: {e}")

print_section("SELESAI - Analisa API Lengkap")
print(f"  Email yang digunakan untuk test: {generated_email}")
