"""
Script untuk mengirim email pengujian (dummy OTP) ke alamat TempMail.

Anda membutuhkan akun email pengirim (misalnya Gmail) dan App Password-nya
untuk dapat mengirim email lewat script Python.
"""

import smtplib
import random
import getpass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def main() -> None:
    print("=" * 50)
    print("📬 Alat Pengirim Test OTP (Dummy Notification)")
    print("=" * 50)
    
    target_email = input("Masukkan alamat TempMail tujuan: ").strip()
    if not target_email:
        print("Alamat tujuan tidak boleh kosong.")
        return

    print("\n[Konfigurasi Pengirim]")
    print("Disarankan menggunakan Gmail. Pastikan Anda menggunakan 'App Password'")
    print("bukan password akun utama Anda.")
    
    sender_email = input("Masukkan email pengirim (misal: email.anda@gmail.com): ").strip()
    # Menggunakan getpass agar password tidak tampil di layar saat diketik
    sender_password = getpass.getpass("Masukkan App Password: ").strip()
    
    if not sender_email or not sender_password:
        print("Email dan password pengirim diperlukan.")
        return

    # Generate 6-digit random number
    otp_code = f"{random.randint(0, 999999):06d}"
    
    subject = "Verifikasi Keamanan Akun Anda"
    body = (
        f"Halo,\n\n"
        f"Terima kasih telah mendaftar. Berikut adalah kode verifikasi Anda:\n\n"
        f"Kode OTP: {otp_code}\n\n"
        f"Mohon jangan berikan kode ini kepada siapapun.\n"
        f"Jika Anda tidak merasa melakukan permintaan ini, abaikan email ini.\n"
    )
    
    msg = MIMEMultipart()
    msg['From'] = f"Sistem Dummy <{sender_email}>"
    msg['To'] = target_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    print(f"\n⏳ Mengirim email dengan OTP {otp_code} ke {target_email}...")
    try:
        # Menggunakan server SMTP Gmail secara default
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"✅ Berhasil! Email telah dikirim.")
        print(f"Silakan periksa notifikasi di bot Telegram Anda, seharusnya bot akan mendeteksi OTP {otp_code} tersebut.")
    except smtplib.SMTPAuthenticationError:
        print("❌ Gagal login: Email atau App Password salah.")
        print("   Catatan: Jika menggunakan Gmail, Anda HARUS mengaktifkan 2FA dan membuat 'App Password'.")
    except Exception as e:
        print(f"❌ Terjadi kesalahan saat mengirim email: {e}")

if __name__ == "__main__":
    main()
