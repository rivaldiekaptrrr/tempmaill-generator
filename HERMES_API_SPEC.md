# Spesifikasi API Integrasi HERMES - TempMail Bot

Dokumen ini berisi detail spesifikasi API (Webhook) yang telah diimplementasikan pada sisi Bot Telegram TempMail. API ini dirancang khusus untuk memungkinkan agen otonom (seperti HERMES) memicu pembuatan email sementara dan menginstruksikan bot untuk secara otomatis mengirimkan kode OTP ke grup Telegram yang ditentukan.

---

## 🔗 Endpoint Detail

- **URL Endpoint**: `https://bot.valtech.my.id/generate`
- **Method**: `POST`
- **Content-Type**: `application/json`

---

## 🔒 Authentication

API ini dilindungi menggunakan token otorisasi (Bearer Token). Agen HERMES wajib mengirimkan token yang cocok dengan variabel lingkungan `API_BEARER_TOKEN` yang telah disetel di sisi server (VPS/Coolify).

**Header:**
```http
Authorization: Bearer <TOKEN_RAHASIA_ANDA>
```

---

## 📤 Request Payload (Body)

Agen HERMES harus mengirimkan data JSON yang berisi *chat_id* dari grup Telegram tempat OTP akan diteruskan.

**Contoh Payload:**
```json
{
  "action": "generate",
  "telegram_chat_id": "-1004341867952"
}
```

*Catatan:*
- `telegram_chat_id` (Wajib): ID grup Telegram (biasanya diawali tanda minus `-`). Pastikan bot TempMail sudah ditambahkan ke dalam grup tersebut dan memiliki akses untuk mengirim pesan.

---

## 📥 Response Expected

Jika request berhasil, API akan otomatis membuatkan email, lalu langsung mendaftarkannya ke dalam sistem monitoring *real-time* milik bot. Respon yang dikembalikan ke agen HERMES adalah sebagai berikut:

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

## 🔄 Autonomous Workflow (Bagaimana Sistem Bekerja)

1. **HERMES Agent** akan menembak endpoint `POST /generate` dengan menyertakan target `telegram_chat_id`.
2. **Bot TempMail (Server)** memvalidasi token, kemudian akan membuat sebuah email *temporary* acak menggunakan *CleanTempMail API*.
3. Bot akan langsung memasukkan alamat email tersebut ke dalam daftar pantauan latar belakang (Background Monitoring Task).
4. Bot mengembalikan alamat email tersebut (`email`) ke HERMES.
5. **HERMES Agent** menerima alamat email, lalu melakukan tugasnya (misalnya: mengisi formulir registrasi dan meminta pengiriman OTP ke alamat tersebut).
6. Saat email yang berisi OTP masuk ke inbox sementara, **Bot TempMail** akan secara otomatis mendeteksinya, mengekstrak OTP menggunakan Regex, dan langsung mem-forward (mengirimkan) keseluruhan ringkasan pesan + OTP ke grup Telegram tujuan (`telegram_chat_id`).
7. Selesai! Agen dapat membaca OTP dari grup tersebut atau manusia di dalam grup bisa menggunakan OTP tersebut secara real-time.
