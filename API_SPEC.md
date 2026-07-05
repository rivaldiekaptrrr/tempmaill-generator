# Spesifikasi API Webhook - TempMail Bot

Dokumen ini berisi detail spesifikasi API (Webhook) yang telah diimplementasikan pada sisi Bot Telegram TempMail. API ini dirancang khusus untuk memungkinkan agen otonom atau skrip otomasi (Client) memicu pembuatan email sementara dan menginstruksikan bot untuk secara otomatis mengirimkan kode OTP, baik melalui grup Telegram maupun dengan mengambilnya secara langsung.

---

## 🔗 Endpoint Detail

- **URL Endpoint**: `https://bot.valtech.my.id/generate`
- **Method**: `POST`
- **Content-Type**: `application/json`

---

## 🔒 Authentication

API ini dilindungi menggunakan token otorisasi (Bearer Token). Klien wajib mengirimkan token yang cocok dengan variabel lingkungan `API_BEARER_TOKEN` yang telah disetel di sisi server (VPS/Coolify).

**Header:**
```http
Authorization: Bearer <TOKEN_RAHASIA_ANDA>
```

---

## 📤 Request Payload (Body)

Klien harus mengirimkan data JSON yang berisi *chat_id* dari grup Telegram tempat OTP akan diteruskan.

**Contoh Payload Lengkap:**
```json
{
  "action": "generate",
  "telegram_chat_id": "-1004341867952",
  "domain": "a.xunika.uk",
  "prefix": "valtech"
}
```

*Catatan Parameter:*
- `telegram_chat_id` (Wajib): ID grup Telegram (biasanya diawali tanda minus `-`). Pastikan bot TempMail sudah ditambahkan ke dalam grup tersebut dan memiliki akses untuk mengirim pesan. 
  *(Catatan: Pengiriman OTP ke grup secara real-time hanya akan terjadi jika administrator grup telah mengaktifkan perintah `/autocheck` pada grup tersebut. Jika mati, Anda tetap bisa mengambil pesan via endpoint `GET /otp`).*
- `domain` (Opsional): Domain spesifik yang ingin digunakan (contoh: `"a.xunika.uk"`). Jika tidak diisi, bot akan mengacak domain.
- `prefix` (Opsional): Awalan/username spesifik untuk email (contoh: `"valtech"`). Jika tidak diisi, awalan akan diacak oleh server.

---

## 📥 Response Expected

Jika request berhasil, API akan otomatis membuatkan email, lalu langsung mendaftarkannya ke dalam sistem monitoring *real-time* milik bot. Respon yang dikembalikan ke Klien adalah sebagai berikut:

**Success Response (HTTP 200 OK):**
```json
{
  "success": true,
  "email": "contoh123@domainsementara.com",
  "domain": "domainsementara.com"
}
```

**Error Response (Contoh - HTTP 400/401):**
```json
{
  "success": false,
  "error": "Unauthorized" 
}
```

---

## 📩 Mendapatkan OTP (Polling Klien)

Jika klien Anda ingin mengambil OTP secara langsung tanpa melalui grup Telegram, Anda bisa menggunakan metode *polling* ke endpoint berikut.

- **URL Endpoint**: `https://bot.valtech.my.id/otp`
- **Method**: `GET`
- **Query Parameter**: `?email=<alamat_email_yang_sedang_dipantau>`
- **Header**: Sama seperti `/generate` (wajib menggunakan `Authorization: Bearer <TOKEN>`)

**Contoh URL:**
`https://bot.valtech.my.id/otp?email=valtech@a.xunika.uk`

**Success Response (HTTP 200 OK):**
```json
{
  "success": true,
  "email": "valtech@a.xunika.uk",
  "otp": "123456",
  "messages": [
    {
      "id": "abc123def",
      "sender": "no-reply@layanan.com",
      "subject": "Kode Verifikasi Anda",
      "date": "2026-07-05T12:00:00+00:00",
      "text": "Kode verifikasi Anda adalah 123456",
      "extracted_otp": "123456"
    }
  ]
}
```
*Catatan:* `otp` di *root* JSON akan bernilai `null` jika tidak ada pesan atau tidak ada OTP yang terdeteksi di dalam pesan. Klien cukup memanggil endpoint ini setiap beberapa detik hingga `otp` bernilai *string*.

---

## 🔄 Autonomous Workflow (Bagaimana Sistem Bekerja)

1. **Klien (Client/Agent)** akan menembak endpoint `POST /generate` dengan menyertakan target `telegram_chat_id`.
2. **Bot TempMail (Server)** memvalidasi token, kemudian akan membuat sebuah email *temporary* acak menggunakan *CleanTempMail API*.
3. Bot akan langsung memasukkan alamat email tersebut ke dalam daftar pantauan latar belakang (Background Monitoring Task).
4. Bot mengembalikan alamat email tersebut (`email`) ke Klien.
5. **Klien** menerima alamat email, lalu melakukan tugas utamanya (misalnya: mengisi formulir registrasi dan meminta pengiriman OTP ke alamat tersebut).
6. Saat email yang berisi OTP masuk ke inbox sementara, **Bot TempMail** akan secara otomatis mendeteksinya, mengekstrak OTP menggunakan Regex, dan langsung mem-forward (mengirimkan) keseluruhan ringkasan pesan + OTP ke grup Telegram tujuan (`telegram_chat_id`).
7. Selesai! Klien dapat membaca OTP secara otomatis via endpoint `GET /otp`, atau manusia di dalam grup Telegram bisa menggunakan OTP tersebut secara real-time.
