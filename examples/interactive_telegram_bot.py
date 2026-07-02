"""
Example: Interactive Telegram Bot for CleanTempMail.

This script uses `python-telegram-bot` to create a fully interactive bot.
Features:
- /start: Help menu
- /generate: Create a new temp email and auto-monitor it
- /list: List your active monitored emails
- /stop <email>: Stop monitoring an email

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

# Global State
user_emails: dict[int, list[str]] = defaultdict(list)
monitoring_tasks: dict[str, asyncio.Task[Any]] = {}
seen_messages: set[str] = set()
auto_monitor_state: dict[int, bool] = defaultdict(lambda: True)


def format_email_message(message: EmailMessage) -> str:
    lines = [
        "📬 *New Email Received*",
        f"*Subject:* {message.subject or '(no subject)'}",
        f"*From:* `{message.sender}`",
    ]
    if message.date:
        lines.append(f"*Date:* {message.date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
    otp = extract_otp(message.text, message.html)
    if otp:
        lines.append(f"\n🔑 *OTP Code:* `{otp}`")
        
    verify_links = extract_verification_urls(message.html, message.text)
    if verify_links:
        lines.append("\n🔗 *Verification Link:*")
        for link in verify_links[:3]:
            lines.append(link)
            
    return "\n".join(lines)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /start command."""
    if not update.effective_chat:
        return
        
    text = (
        "🤖 *Welcome to TempMail Bot!*\n\n"
        "I can generate and monitor temporary emails for you.\n\n"
        "*Commands:*\n"
        "`/generate` - Create a new email and start monitoring\n"
        "`/check` - Manually check all active emails for new messages\n"
        "`/list` - Show your active emails\n"
        "`/stop <email>` - Stop monitoring an email\n"
        "`/autocheck` - Manage auto-monitoring settings\n"
        "`/help` - Show this message"
    )
    await update.effective_chat.send_message(text, parse_mode="Markdown")


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /generate command."""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not chat_id:
        return

    msg = await update.effective_chat.send_message("⏳ Generating new email...")
    
    # Run synchronous generate_email in a thread
    loop = asyncio.get_running_loop()
    with TempMailClient() as client:
        try:
            email = await loop.run_in_executor(None, client.generate_email)
        except Exception as e:
            await msg.edit_text(f"❌ Failed to generate email: {e}")
            return

    user_emails[chat_id].append(email.address)
    
    # Check if auto-monitoring is enabled for this chat
    if auto_monitor_state[chat_id]:
        await msg.edit_text(
            f"✅ *New Email Generated!*\n\n"
            f"📧 Address: `{email.address}`\n\n"
            f"_Monitoring started automatically. I will notify you when new emails arrive._",
            parse_mode="Markdown"
        )
        
        # Create the callback
        async def on_new_email(message: EmailMessage) -> None:
            if message.id in seen_messages:
                return
            seen_messages.add(message.id)
            
            # SSE events often only contain metadata. Fetch the full body if missing.
            if not message.text and not message.html:
                try:
                    loop = asyncio.get_running_loop()
                    def fetch_full():
                        with TempMailClient() as client:
                            return client.read_message(message.id)
                    message = await loop.run_in_executor(None, fetch_full)
                except Exception as e:
                    logger.error("Failed to fetch full message body for %s: %s", message.id, e)
                    
            text = format_email_message(message)
            try:
                await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            except Exception as e:
                logger.error("Failed to send telegram notification: %s", e)
                
        # Start background task
        task = asyncio.create_task(
            monitor_async(email.address, callback=on_new_email)
        )
        monitoring_tasks[email.address] = task
    else:
        await msg.edit_text(
            f"✅ *New Email Generated!*\n\n"
            f"📧 Address: `{email.address}`\n\n"
            f"_Auto-check is OFF. Use /check to view your inbox manually._",
            parse_mode="Markdown"
        )


async def autocheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /autocheck command with inline keyboards."""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not chat_id:
        return
        
    current_state = "ON 🟢" if auto_monitor_state[chat_id] else "OFF 🛑"
    
    keyboard = [
        [
            InlineKeyboardButton("🟢 Enable", callback_data="autocheck:on"),
            InlineKeyboardButton("🛑 Disable", callback_data="autocheck:off")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_chat.send_message(
        f"⚙️ *Auto-check Settings*\n\n"
        f"Current status: *{current_state}*\n\n"
        "_Disabling auto-check will stop background connections and save server resources. "
        "You can still pull emails manually using /check._\n\n"
        "Select an option below:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /check command to manually poll for new messages."""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    emails = user_emails.get(chat_id, [])
    
    if not emails:
        await update.effective_chat.send_message("Tidak ada email yang sedang aktif untuk di-check.")
        return
        
    msg = await update.effective_chat.send_message(f"🔄 Mengecek manual inbox untuk {len(emails)} email...")
    
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
                    logger.error(f"Failed to check {em}: {e}")
        return results
        
    all_messages = await loop.run_in_executor(None, fetch_all, emails)
    
    for message in all_messages:
        if message.id not in seen_messages:
            seen_messages.add(message.id)
            new_found += 1
            text = format_email_message(message)
            await update.effective_chat.send_message(text, parse_mode="Markdown")
            
    if new_found == 0:
        await msg.edit_text("✅ Check manual selesai. Tidak ada pesan baru.")
    else:
        await msg.edit_text(f"✅ Check manual selesai. Menemukan {new_found} pesan baru!")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /list command."""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    emails = user_emails.get(chat_id, [])
    
    if not emails:
        await update.effective_chat.send_message("You don't have any active emails. Use /generate to create one.")
        return
        
    text = "📋 *Your Active Emails:*\n\n"
    for idx, em in enumerate(emails, 1):
        status = "🟢 Monitoring" if em in monitoring_tasks and not monitoring_tasks[em].done() else "🔴 Stopped"
        text += f"{idx}. `{em}` - {status}\n"
        
    await update.effective_chat.send_message(text, parse_mode="Markdown")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /stop command."""
    chat_id = update.effective_chat.id if update.effective_chat else 0
    args = context.args
    emails = user_emails.get(chat_id, [])
    
    # If user provided an email argument
    if args:
        email_to_stop = args[0]
        if email_to_stop not in emails:
            await update.effective_chat.send_message("❌ This email is not in your list.")
            return
            
        task = monitoring_tasks.pop(email_to_stop, None)
        if task and not task.done():
            task.cancel()
            if email_to_stop in emails:
                emails.remove(email_to_stop)
            await update.effective_chat.send_message(f"⏹️ Stopped monitoring `{email_to_stop}`. Email removed from list.", parse_mode="Markdown")
        else:
            await update.effective_chat.send_message("⚠️ This email is not currently being monitored.")
        return

    # If no argument, show inline keyboard for active emails
    active_emails = [em for em in emails if em in monitoring_tasks and not monitoring_tasks[em].done()]
    
    if not active_emails:
        await update.effective_chat.send_message("Tidak ada email yang sedang dipantau saat ini.")
        return
        
    keyboard = []
    for em in active_emails:
        keyboard.append([InlineKeyboardButton(em, callback_data=f"stop:{em}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_chat.send_message(
        "Pilih email yang ingin dihentikan pemantauannya:", 
        reply_markup=reply_markup
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for inline button clicks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data and data.startswith("autocheck:"):
        mode = data.split(":", 1)[1]
        chat_id = update.effective_chat.id if update.effective_chat else 0
        
        if mode == 'off':
            auto_monitor_state[chat_id] = False
            
            # Cancel all active monitoring tasks for this user
            canceled_count = 0
            for email in user_emails.get(chat_id, []):
                task = monitoring_tasks.pop(email, None)
                if task and not task.done():
                    task.cancel()
                    canceled_count += 1
                    
            await query.edit_message_text(
                f"🛑 *Auto-check Disabled.*\n\n"
                f"Closed {canceled_count} active background connection(s).\n"
                f"Use `/check` to manually refresh your inbox.",
                parse_mode="Markdown"
            )
        else:
            auto_monitor_state[chat_id] = True
            await query.edit_message_text(
                "🟢 *Auto-check Enabled.*\n\n"
                "Emails generated from now on will be monitored in real-time.",
                parse_mode="Markdown"
            )
        return

    if data and data.startswith("stop:"):
        email_to_stop = data.split(":", 1)[1]
        
        task = monitoring_tasks.pop(email_to_stop, None)
        if task and not task.done():
            task.cancel()
            chat_id = update.effective_chat.id if update.effective_chat else 0
            if chat_id in user_emails and email_to_stop in user_emails[chat_id]:
                user_emails[chat_id].remove(email_to_stop)
            await query.edit_message_text(f"⏹️ Stopped monitoring `{email_to_stop}`. Email removed from list.", parse_mode="Markdown")
        else:
            await query.edit_message_text("⚠️ This email is not currently being monitored.")


def main() -> None:
    setup_logging(level=logging.INFO)
    
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is not set.")
        return

    print("Starting Interactive TempMail Bot...")
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("generate", generate_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("autocheck", autocheck_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("Bot is polling... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
