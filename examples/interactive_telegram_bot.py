"""
Example: Interactive Telegram Bot for CleanTempMail.

This script uses `python-telegram-bot` to create a fully interactive bot.
Features:
- /start: Tampilkan menu bantuan
- /generate: Buat email baru dan pantau secara otomatis (domain acak)
- /choose: Buat email dengan memilih domain sendiri (dengan paginasi)
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
import socket
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

# Configuration
DOMAINS_PER_PAGE: int = 8  # Jumlah domain yang ditampilkan per halaman

# Global States
user_emails: dict[int, list[str]] = defaultdict(list)
monitoring_tasks: dict[str, asyncio.Task[Any]] = {}

# Fix Kelemahan #2: seen_messages diisolasi per-user (chat_id) agar tidak bocor antar pengguna
seen_messages: dict[int, set[str]] = defaultdict(set)
auto_monitor_state: dict[int, bool] = defaultdict(lambda: True)

# Default domain per-user: jika diset, /generate akan selalu menggunakan domain ini
user_default_domain: dict[int, str] = {}

# Cache domain list agar tidak perlu memanggil API berulang kali
_domain_cache: list[str] = []


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


async def _get_domains(loop: asyncio.AbstractEventLoop) -> list[str]:
    """Ambil daftar domain dari API, gunakan cache jika sudah tersedia."""
    global _domain_cache
    if _domain_cache:
        return _domain_cache

    def fetch() -> list[str]:
        with TempMailClient() as client:
            # Ambil semua domain sekaligus (total ~958)
            return client.get_domains(limit=1000)

    try:
        _domain_cache = await loop.run_in_executor(None, fetch)
        logger.info("Domain cache diperbarui: %d domain tersedia.", len(_domain_cache))
    except Exception as e:
        logger.error("Gagal mengambil daftar domain: %s", e)
        _domain_cache = []
    return _domain_cache


def _build_domain_keyboard(
    domains: list[str], page: int, mode: str = "choose"
) -> InlineKeyboardMarkup:
    """
    Buat inline keyboard berisi daftar domain untuk halaman tertentu.

    Args:
        domains: Daftar semua domain yang tersedia.
        page: Nomor halaman saat ini (0-indexed).
        mode: "choose" untuk /choose (langsung generate email),
              "setdomain" untuk /setdomain (simpan sebagai default).
    """
    total_pages = max(1, (len(domains) + DOMAINS_PER_PAGE - 1) // DOMAINS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))  # clamp ke range yang valid

    start = page * DOMAINS_PER_PAGE
    end = start + DOMAINS_PER_PAGE
    page_domains = domains[start:end]

    # Prefix callback_data berbeda tergantung mode
    domain_cb = "choose_domain" if mode == "choose" else "setdomain_domain"
    page_cb   = "choose_page"   if mode == "choose" else "setdomain_page"
    noop_cb   = "choose_noop"   if mode == "choose" else "setdomain_noop"

    keyboard: list[list[InlineKeyboardButton]] = []

    # Tombol domain (2 kolom agar lebih ringkas)
    for i in range(0, len(page_domains), 2):
        row = [InlineKeyboardButton(
            f"📧 {page_domains[i]}", callback_data=f"{domain_cb}:{page_domains[i]}"
        )]
        if i + 1 < len(page_domains):
            row.append(InlineKeyboardButton(
                f"📧 {page_domains[i + 1]}", callback_data=f"{domain_cb}:{page_domains[i + 1]}"
            ))
        keyboard.append(row)

    # Baris navigasi paginasi
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{page_cb}:{page - 1}"))
    nav_row.append(InlineKeyboardButton(
        f"📄 {page + 1}/{total_pages}", callback_data=noop_cb
    ))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"{page_cb}:{page + 1}"))
    keyboard.append(nav_row)

    # Tombol reset khusus untuk mode setdomain
    if mode == "setdomain":
        keyboard.append([
            InlineKeyboardButton("🎲 Reset ke Domain Acak", callback_data="setdomain_reset")
        ])

    return InlineKeyboardMarkup(keyboard)



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
        "`/generate` - Buat email baru (gunakan domain default jika sudah diatur)\n"
        "`/choose` - Pilih domain sendiri sekali pakai dari daftar\n"
        "`/setdomain` - Atur domain default untuk /generate\n"
        "`/check` - Cek inbox semua email secara manual\n"
        "`/list` - Tampilkan daftar email Anda\n"
        "`/stop` - Hentikan monitoring dan hapus email dari daftar\n"
        "`/autocheck` - Kelola pengaturan auto-monitoring\n"
        "`/help` - Tampilkan pesan ini"
    )
    await update.effective_chat.send_message(text, parse_mode="Markdown")


async def choose_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /choose — pilih domain lalu generate email (sekali pakai)."""
    if not update.effective_chat:
        return

    msg = await update.effective_chat.send_message("⏳ Memuat daftar domain...")

    loop = asyncio.get_running_loop()
    domains = await _get_domains(loop)

    if not domains:
        await msg.edit_text("❌ Gagal memuat daftar domain. Silakan coba lagi nanti.")
        return

    total_pages = max(1, (len(domains) + DOMAINS_PER_PAGE - 1) // DOMAINS_PER_PAGE)
    reply_markup = _build_domain_keyboard(domains, page=0, mode="choose")

    await msg.edit_text(
        f"🌐 *Pilih Domain Email (Sekali Pakai)*\n\n"
        f"Tersedia *{len(domains)} domain* di *{total_pages} halaman*.\n"
        f"Ketuk salah satu domain untuk langsung membuat email:\n"
        f"_Gunakan /setdomain jika ingin menyimpan domain sebagai default._",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def setdomain_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /setdomain — simpan domain default untuk /generate."""
    if not update.effective_chat:
        return
    chat_id = update.effective_chat.id

    current = user_default_domain.get(chat_id)
    current_info = (
        f"Domain default saat ini: `{current}`\n"
        if current
        else "Saat ini belum ada domain default (email dibuat secara acak).\n"
    )

    msg = await update.effective_chat.send_message("⏳ Memuat daftar domain...")

    loop = asyncio.get_running_loop()
    domains = await _get_domains(loop)

    if not domains:
        await msg.edit_text("❌ Gagal memuat daftar domain. Silakan coba lagi nanti.")
        return

    total_pages = max(1, (len(domains) + DOMAINS_PER_PAGE - 1) // DOMAINS_PER_PAGE)
    reply_markup = _build_domain_keyboard(domains, page=0, mode="setdomain")

    await msg.edit_text(
        f"⚙️ *Atur Domain Default untuk /generate*\n\n"
        f"{current_info}"
        f"Tersedia *{len(domains)} domain* di *{total_pages} halaman*.\n"
        f"Pilih domain yang ingin dijadikan default:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /generate."""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not chat_id:
        return

    # Ambil domain default user jika sudah diatur
    default_domain = user_default_domain.get(chat_id)
    if default_domain:
        loading_text = f"⏳ Membuat email baru dengan domain `{default_domain}`..."
    else:
        loading_text = "⏳ Membuat email baru..."

    msg = await update.effective_chat.send_message(loading_text, parse_mode="Markdown")

    loop = asyncio.get_running_loop()
    with TempMailClient() as client:
        try:
            email = await loop.run_in_executor(
                None, lambda: client.generate_email(domain=default_domain)
            )
        except Exception as e:
            await msg.edit_text(f"❌ Gagal membuat email: {e}")
            return

    user_emails[chat_id].append(email.address)

    domain_info = f"\n🌐 Domain: `{default_domain}`" if default_domain else ""

    if auto_monitor_state[chat_id]:
        _start_monitoring(email.address, chat_id, context)
        await msg.edit_text(
            f"✅ *Email Baru Berhasil Dibuat!*\n\n"
            f"📧 Alamat: `{email.address}`{domain_info}\n\n"
            f"_Monitoring dimulai secara otomatis. Anda akan diberi tahu saat ada email masuk._",
            parse_mode="Markdown",
        )
    else:
        await msg.edit_text(
            f"✅ *Email Baru Berhasil Dibuat!*\n\n"
            f"📧 Alamat: `{email.address}`{domain_info}\n\n"
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
    chat_id = update.effective_chat.id if update.effective_chat else 0

    # --- Tombol no-op (indikator halaman, tidak melakukan apa-apa) ---
    if data == "choose_noop":
        return

    # --- Navigasi halaman pada /choose ---
    if data and data.startswith("choose_page:"):
        try:
            page = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            return

        loop = asyncio.get_running_loop()
        domains = await _get_domains(loop)
        if not domains:
            await query.edit_message_text("❌ Gagal memuat daftar domain.")
            return

        total_pages = max(1, (len(domains) + DOMAINS_PER_PAGE - 1) // DOMAINS_PER_PAGE)
        reply_markup = _build_domain_keyboard(domains, page)
        await query.edit_message_text(
            f"🌐 *Pilih Domain Email Anda*\n\n"
            f"Tersedia *{len(domains)} domain* di *{total_pages} halaman*.\n"
            f"Ketuk salah satu domain di bawah untuk membuat email dengan domain tersebut:",
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
        return

    # --- User memilih domain dari /choose (sekali pakai) ---
    if data and data.startswith("choose_domain:"):
        chosen_domain = data.split(":", 1)[1]

        await query.edit_message_text(
            f"⏳ Membuat email baru dengan domain `{chosen_domain}`...",
            parse_mode="Markdown",
        )

        loop = asyncio.get_running_loop()

        try:
            def _generate() -> str:
                with TempMailClient() as c:
                    return c.generate_email(domain=chosen_domain).address

            email_address = await loop.run_in_executor(None, _generate)
        except Exception as e:
            logger.error("Gagal generate email dengan domain %s: %s", chosen_domain, e)
            await query.edit_message_text(
                f"❌ Gagal membuat email dengan domain `{chosen_domain}`.\n"
                f"Error: `{e}`",
                parse_mode="Markdown",
            )
            return

        user_emails[chat_id].append(email_address)

        if auto_monitor_state[chat_id]:
            _start_monitoring(email_address, chat_id, context)
            await query.edit_message_text(
                f"✅ *Email Baru Berhasil Dibuat!*\n\n"
                f"📧 Alamat: `{email_address}`\n"
                f"🌐 Domain: `{chosen_domain}`\n\n"
                f"_Monitoring dimulai secara otomatis. Anda akan diberi tahu saat ada email masuk._",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                f"✅ *Email Baru Berhasil Dibuat!*\n\n"
                f"📧 Alamat: `{email_address}`\n"
                f"🌐 Domain: `{chosen_domain}`\n\n"
                f"_Auto-check sedang MATI. Gunakan /check untuk mengecek inbox secara manual._",
                parse_mode="Markdown",
            )
        return

    # --- Navigasi halaman pada /setdomain ---
    if data and data.startswith("setdomain_page:"):
        try:
            page = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            return

        loop = asyncio.get_running_loop()
        domains = await _get_domains(loop)
        if not domains:
            await query.edit_message_text("❌ Gagal memuat daftar domain.")
            return

        current = user_default_domain.get(chat_id)
        current_info = (
            f"Domain default saat ini: `{current}`\n"
            if current
            else "Saat ini belum ada domain default (email dibuat secara acak).\n"
        )
        total_pages = max(1, (len(domains) + DOMAINS_PER_PAGE - 1) // DOMAINS_PER_PAGE)
        reply_markup = _build_domain_keyboard(domains, page, mode="setdomain")
        await query.edit_message_text(
            f"⚙️ *Atur Domain Default untuk /generate*\n\n"
            f"{current_info}"
            f"Tersedia *{len(domains)} domain* di *{total_pages} halaman*.\n"
            f"Pilih domain yang ingin dijadikan default:",
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
        return

    # --- no-op untuk setdomain (indikator halaman) ---
    if data == "setdomain_noop":
        return

    # --- User memilih domain dari /setdomain (simpan sebagai default) ---
    if data and data.startswith("setdomain_domain:"):
        chosen_domain = data.split(":", 1)[1]
        user_default_domain[chat_id] = chosen_domain
        await query.edit_message_text(
            f"✅ *Domain Default Berhasil Diatur!*\n\n"
            f"🌐 Domain: `{chosen_domain}`\n\n"
            f"Mulai sekarang, perintah /generate akan selalu menggunakan domain ini.\n"
            f"Ketuk /setdomain kapan saja untuk menggantinya.",
            parse_mode="Markdown",
        )
        return

    # --- User memilih reset domain ke acak ---
    if data == "setdomain_reset":
        user_default_domain.pop(chat_id, None)
        await query.edit_message_text(
            "🎲 *Domain Default Dihapus.*\n\n"
            "Perintah /generate sekarang akan membuat email dengan domain acak dari server.",
            parse_mode="Markdown",
        )
        return

    # --- Handler autocheck ---
    if data and data.startswith("autocheck:"):
        mode = data.split(":", 1)[1]

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

    # --- Handler stop ---
    if data and data.startswith("stop:"):
        email_to_stop = data.split(":", 1)[1]

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

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("generate", generate_command))
    app.add_handler(CommandHandler("choose", choose_command))
    app.add_handler(CommandHandler("setdomain", setdomain_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("autocheck", autocheck_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot berjalan... Tekan Ctrl+C untuk berhenti.")
    app.run_polling()


if __name__ == "__main__":
    main()
