"""
Example: Interactive Telegram Bot for CleanTempMail.

This script uses `python-telegram-bot` to create a fully interactive bot.
Features:
- /start: Tampilkan menu bantuan
- /generate: Buat email baru dan pantau secara otomatis
- /list: Tampilkan daftar email Anda
- /stop: Hentikan monitoring dan hapus email dari daftar
- /autocheck: Kelola pengaturan auto-monitoring
- /check: Cek manual inbox semua email

Setup:
    pip install python-telegram-bot

Usage:
    python examples/interactive_telegram_bot.py
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from tempmail import TempMailClient, extract_otp, extract_verification_urls, setup_logging
from tempmail.models import EmailMessage
from tempmail.monitor import monitor_async

logger = logging.getLogger("tempmail.examples.bot")

# Configuration
TELEGRAM_BOT_TOKEN: str = os.environ.get(
    "TELEGRAM_BOT_TOKEN", "8769394239:AAE5_wd77Rn6hOYiLKsOPZ2RjtIwvSsvOps"
)

# Global States
user_emails: dict[int, list[str]] = defaultdict(list)
monitoring_tasks: dict[str, asyncio.Task[Any]] = {}

# Fix Kelemahan #2: seen_messages diisolasi per-user (chat_id) agar tidak bocor antar pengguna
seen_messages: dict[int, set[str]] = defaultdict(set)
auto_monitor_state: dict[int, bool] = defaultdict(lambda: True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def format_email_message(message: EmailMessage) -> str:
    lines = [
        "📬 *Email Baru Diterima*",
        f"*Subjek:* {message.subject or '(tanpa subjek)'}",
        f"*Dari:* `{message.sender}`",
    ]
    if message.date:
        lines.append(f"*Tanggal:* {message.date.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    otp = extract_otp(message.text, message.html)
    if otp:
        lines.append(f"\n🔑 *Kode OTP:* `{otp}`")

    verify_links = extract_verification_urls(message.html, message.text)
    if verify_links:
        lines.append("\n🔗 *Tautan Verifikasi:*")
        for link in verify_links[:3]:
            lines.append(link)

    return "\n".join(lines)


def make_email_callback(
    chat_id: int, context: ContextTypes.DEFAULT_TYPE
) -> Callable[[EmailMessage], Coroutine[Any, Any, None]]:
    """
    Fix Kelemahan #1: Factory yang membuat callback `on_new_email` terikat ke chat_id tertentu.

    Dengan memisahkan callback dari `generate_command`, fungsi ini dapat
    di-reuse saat restart monitoring dari `autocheck:on`.
    """

    async def on_new_email(message: EmailMessage) -> None:
        # Fix Kelemahan #2: Gunakan seen_messages per-user
        if message.id in seen_messages[chat_id]:
            return
        seen_messages[chat_id].add(message.id)

        # SSE events sering hanya membawa metadata. Ambil isi penuh jika kosong.
        if not message.text and not message.html:
            try:
                loop = asyncio.get_running_loop()

                def fetch_full() -> EmailMessage:
                    with TempMailClient() as c:
                        return c.read_message(message.id)

                message = await loop.run_in_executor(None, fetch_full)
            except Exception as e:
                logger.error("Gagal mengambil isi pesan %s: %s", message.id, e)

        text = format_email_message(message)
        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error("Gagal mengirim notifikasi Telegram: %s", e)

    return on_new_email


def _start_monitoring(
    email: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE
) -> asyncio.Task[Any]:
    """
    Fix Bug #4: Buat dan daftarkan task monitoring baru.

    Task yang selesai (selesai normal, error, atau dibatalkan) akan otomatis
    dihapus dari `monitoring_tasks` via `add_done_callback`.
    """
    callback = make_email_callback(chat_id, context)
    task = asyncio.create_task(monitor_async(email, callback=callback))

    def _on_done(t: asyncio.Task[Any]) -> None:
        # Hanya hapus jika task ini masih yang terdaftar (belum digantikan yang baru)
        if monitoring_tasks.get(email) is t:
            monitoring_tasks.pop(email, None)
            logger.info("Task monitoring untuk %s selesai dan dibersihkan dari registry.", email)

    task.add_done_callback(_on_done)
    monitoring_tasks[email] = task
    return task


# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /start."""
    if not update.effective_chat:
        return

    text = (
        "🤖 *Selamat datang di TempMail Bot!*\n\n"
        "Saya bisa membuat dan memantau email sementara untuk Anda.\n\n"
        "*Perintah:*\n"
        "`/generate` - Buat email baru dan mulai monitoring\n"
        "`/check` - Cek inbox semua email secara manual\n"
        "`/list` - Tampilkan daftar email Anda\n"
        "`/stop` - Hentikan monitoring dan hapus email dari daftar\n"
        "`/autocheck` - Kelola pengaturan auto-monitoring\n"
        "`/help` - Tampilkan pesan ini"
    )
    await update.effective_chat.send_message(text, parse_mode="Markdown")


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /generate."""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not chat_id:
        return

    msg = await update.effective_chat.send_message("⏳ Membuat email baru...")

    loop = asyncio.get_running_loop()
    with TempMailClient() as client:
        try:
            email = await loop.run_in_executor(None, client.generate_email)
        except Exception as e:
            await msg.edit_text(f"❌ Gagal membuat email: {e}")
            return

    user_emails[chat_id].append(email.address)

    if auto_monitor_state[chat_id]:
        # Fix Kelemahan #1: Gunakan _start_monitoring helper (bukan inner closure)
        _start_monitoring(email.address, chat_id, context)
        await msg.edit_text(
            f"✅ *Email Baru Berhasil Dibuat!*\n\n"
            f"📧 Alamat: `{email.address}`\n\n"
            f"_Monitoring dimulai secara otomatis. Anda akan diberi tahu saat ada email masuk._",
            parse_mode="Markdown",
        )
    else:
        await msg.edit_text(
            f"✅ *Email Baru Berhasil Dibuat!*\n\n"
            f"📧 Alamat: `{email.address}`\n\n"
            f"_Auto-check sedang MATI. Gunakan /check untuk mengecek inbox secara manual._",
            parse_mode="Markdown",
        )


async def autocheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /autocheck dengan inline keyboard."""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not chat_id:
        return

    current_state = "ON 🟢" if auto_monitor_state[chat_id] else "OFF 🛑"

    keyboard = [
        [
            InlineKeyboardButton("🟢 Aktifkan", callback_data="autocheck:on"),
            InlineKeyboardButton("🛑 Nonaktifkan", callback_data="autocheck:off"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_chat.send_message(
        f"⚙️ *Pengaturan Auto-check*\n\n"
        f"Status saat ini: *{current_state}*\n\n"
        "_Menonaktifkan auto-check akan menghentikan koneksi latar belakang dan menghemat resource server. "
        "Anda masih bisa mengecek email secara manual menggunakan /check._\n\n"
        "Pilih opsi di bawah:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /check — polling manual inbox."""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    emails = user_emails.get(chat_id, [])

    if not emails:
        await update.effective_chat.send_message(
            "❌ Anda tidak memiliki email aktif. Gunakan /generate untuk membuat email baru."
        )
        return

    msg = await update.effective_chat.send_message(f"🔄 Mengecek inbox untuk {len(emails)} email...")

    loop = asyncio.get_running_loop()
    new_found = 0

    def fetch_all(emails_to_check: list[str]) -> list[EmailMessage]:
        results = []
        with TempMailClient() as client:
            for em in emails_to_check:
                try:
                    msgs = client.get_messages(em)
                    results.extend(msgs)
                except Exception as e:
                    logger.error("Gagal mengecek %s: %s", em, e)
        return results

    all_messages = await loop.run_in_executor(None, fetch_all, emails)

    for message in all_messages:
        # Fix Kelemahan #2: Gunakan seen_messages per-user
        if message.id not in seen_messages[chat_id]:
            seen_messages[chat_id].add(message.id)
            new_found += 1
            text = format_email_message(message)
            await update.effective_chat.send_message(text, parse_mode="Markdown")

    if new_found == 0:
        await msg.edit_text("✅ Pengecekan selesai. Tidak ada pesan baru.")
    else:
        await msg.edit_text(f"✅ Pengecekan selesai. Ditemukan {new_found} pesan baru!")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /list."""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    emails = user_emails.get(chat_id, [])

    if not emails:
        await update.effective_chat.send_message(
            "❌ Anda tidak memiliki email. Gunakan /generate untuk membuat email baru."
        )
        return

    text = "📋 *Daftar Email Anda:*\n\n"
    for idx, em in enumerate(emails, 1):
        is_active = em in monitoring_tasks and not monitoring_tasks[em].done()
        status = "🟢 Dipantau" if is_active else "🔴 Dihentikan"
        text += f"{idx}. `{em}` — {status}\n"

    await update.effective_chat.send_message(text, parse_mode="Markdown")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /stop."""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    args = context.args
    emails = user_emails.get(chat_id, [])

    # Jika user memberikan argumen email
    if args:
        email_to_stop = args[0]
        if email_to_stop not in emails:
            await update.effective_chat.send_message("❌ Email ini tidak ada di daftar Anda.")
            return

        # Batalkan task jika masih aktif
        task = monitoring_tasks.pop(email_to_stop, None)
        if task and not task.done():
            task.cancel()

        # Fix Bug #1: Selalu hapus dari daftar, terlepas dari status task
        emails.remove(email_to_stop)
        await update.effective_chat.send_message(
            f"⏹️ Email `{email_to_stop}` dihentikan dan dihapus dari daftar.",
            parse_mode="Markdown",
        )
        return

    # Jika tanpa argumen: Fix Bug #1 — tampilkan SEMUA email (aktif & dihentikan)
    if not emails:
        await update.effective_chat.send_message("❌ Anda tidak memiliki email di daftar.")
        return

    keyboard = []
    for em in emails:
        is_active = em in monitoring_tasks and not monitoring_tasks[em].done()
        label = f"🟢 {em}" if is_active else f"🔴 {em}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"stop:{em}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_chat.send_message(
        "Pilih email yang ingin dihentikan dan dihapus dari daftar:",
        reply_markup=reply_markup,
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk klik inline button."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data and data.startswith("autocheck:"):
        mode = data.split(":", 1)[1]
        chat_id = update.effective_chat.id if update.effective_chat else 0

        if mode == "off":
            auto_monitor_state[chat_id] = False

            # Batalkan semua task monitoring aktif untuk user ini
            canceled_count = 0
            for email in user_emails.get(chat_id, []):
                task = monitoring_tasks.pop(email, None)
                if task and not task.done():
                    task.cancel()
                    canceled_count += 1

            await query.edit_message_text(
                f"🛑 *Auto-check Dinonaktifkan.*\n\n"
                f"Menutup {canceled_count} koneksi latar belakang yang aktif.\n"
                f"Email yang ada tetap tersimpan di daftar. Gunakan `/check` untuk mengecek inbox secara manual.",
                parse_mode="Markdown",
            )
        else:
            auto_monitor_state[chat_id] = True

            # Fix Bug #2: Restart monitoring untuk semua email yang tidak memiliki task aktif
            restarted = 0
            for email in user_emails.get(chat_id, []):
                if email not in monitoring_tasks or monitoring_tasks[email].done():
                    _start_monitoring(email, chat_id, context)
                    restarted += 1

            await query.edit_message_text(
                f"🟢 *Auto-check Diaktifkan.*\n\n"
                f"Memulai ulang monitoring untuk {restarted} email yang ada.\n"
                f"Email baru yang digenerate juga akan dipantau secara otomatis.",
                parse_mode="Markdown",
            )
        return

    if data and data.startswith("stop:"):
        email_to_stop = data.split(":", 1)[1]
        chat_id = update.effective_chat.id if update.effective_chat else 0

        # Batalkan task jika masih aktif
        task = monitoring_tasks.pop(email_to_stop, None)
        if task and not task.done():
            task.cancel()

        # Fix Bug #1: Selalu hapus dari daftar, terlepas dari status task
        if chat_id in user_emails and email_to_stop in user_emails[chat_id]:
            user_emails[chat_id].remove(email_to_stop)
            await query.edit_message_text(
                f"⏹️ Email `{email_to_stop}` dihentikan dan dihapus dari daftar.",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("⚠️ Email tidak ditemukan di daftar Anda.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    setup_logging(level=logging.INFO)

    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN tidak disetel.")
        return

    print("Memulai Interactive TempMail Bot...")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("generate", generate_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("autocheck", autocheck_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot berjalan... Tekan Ctrl+C untuk berhenti.")
    app.run_polling()


if __name__ == "__main__":
    main()
