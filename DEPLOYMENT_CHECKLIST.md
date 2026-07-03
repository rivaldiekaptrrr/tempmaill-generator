# Panduan Deployment & Persiapan Akhir (HERMES API)

Karena kode aplikasi Anda sudah 100% siap, berikut adalah *checklist* langkah-langkah administratif yang perlu Anda lakukan untuk meluncurkan fitur **Custom API (Autonomous Workflow)** ini ke server *production* Anda.

---

## ✅ Tahap 1: Simpan & Push Kode (Git)
Perubahan yang kita lakukan saat ini masih berada di komputer lokal (VS Code) Anda. Anda harus memindahkannya ke GitHub agar Coolify bisa mendeteksinya.
1. Buka Terminal di VS Code.
2. Jalankan perintah berikut secara berurutan:
   ```bash
   git add .
   git commit -m "feat: Menambahkan Custom REST API Server untuk HERMES"
   git push
   ```
*(Karena sebelumnya Anda sudah mengatur Auto-Deploy via Webhook, Coolify otomatis akan menarik kode ini dan men-deploy ulang bot Anda).*

---

## ✅ Tahap 2: Pengaturan Domain di Coolify
Agar HERMES bisa memanggil API melalui `https://bot.valtech.my.id/generate`, Anda harus memberitahu Coolify untuk menggunakan domain tersebut.
1. Buka **Dashboard Coolify**.
2. Masuk ke Project Anda, lalu klik aplikasi bot (`tempmaill-generator`).
3. Di tab **Configuration** -> **General**, temukan kolom **Domains**.
4. Masukkan URL berikut: `https://bot.valtech.my.id`.
5. Klik **Save**.
6. Pastikan Anda juga sudah mengatur *DNS Record (A Record atau CNAME)* di panel domain manager Anda (Cloudflare, Niagahoster, dll) agar subdomain `bot.valtech.my.id` mengarah ke IP VPS Tencent Anda.

---

## ✅ Tahap 3: Environment Variables di Coolify
API ini dilindungi oleh token rahasia agar tidak ada orang asing yang bisa membuat email (yang bisa membebani server/API Anda).
1. Masih di aplikasi bot pada Dashboard Coolify, pindah ke tab **Environment Variables**.
2. Tambahkan variabel baru:
   - Name: `API_BEARER_TOKEN`
   - Value: *(Tentukan sendiri password/token rahasianya, misal: `hermes-secret-key-2026`)*
3. Klik **Save**.
4. Restart aplikasi Anda dari Coolify (klik tombol **Restart** di sudut kanan atas) agar pengaturan `.env` terbaru terbaca.

---

## ✅ Tahap 4: Persiapan Grup Telegram
Agar API bisa meneruskan pesan OTP ke dalam sebuah grup, bot tersebut harus ada di dalam grupnya.
1. Buat grup baru di Telegram (atau gunakan grup yang sudah ada).
2. Tambahkan bot Anda (bot TempMail) ke dalam grup tersebut sebagai anggota (atau admin).
3. Cari tahu **Chat ID** grup tersebut:
   - Anda bisa mengundang bot `@RawDataBot` atau `@MissRose_bot` ke grup, atau menggunakan klien Telegram versi web.
   - Catat Chat ID-nya (biasanya berupa angka minus panjang, contoh: `-1002345678901`).
   - Angka inilah yang nantinya diisi oleh HERMES pada field `"telegram_chat_id"`.

---

## ✅ Tahap 5: Testing / Pengujian Akhir
Langkah terakhir, pastikan semuanya terhubung sebelum Anda menyerahkannya pada HERMES. Gunakan Terminal atau Postman:

```bash
curl -X POST https://bot.valtech.my.id/generate \
     -H "Authorization: Bearer hermes-secret-key-2026" \
     -H "Content-Type: application/json" \
     -d '{"action": "generate", "telegram_chat_id": "-1002345678901"}'
```

Jika Terminal merespons dengan JSON berisi atribut `email`, dan bot Anda tidak lama kemudian mulai mengirimi pesan OTP ke grup... **Selamat! Autonomous Workflow Anda sudah 100% Berhasil!** 🚀
