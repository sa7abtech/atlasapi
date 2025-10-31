"""
Telegram Bot Handlers
Command and message handlers for the ATLAS bot
"""

import logging
import asyncio
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction, ParseMode
import httpx
import sys
sys.path.append("..")

from config import settings, get_greeting
from bot.utils import (
    detect_language,
    format_response_for_telegram,
    format_greeting,
    format_help_message,
    format_stats_message,
    format_error_message,
    is_greeting,
)

logger = logging.getLogger("atlas.bot.handlers")

# API client
api_client = httpx.AsyncClient(timeout=30.0)
API_BASE_URL = settings.API_URL  # FastAPI backend


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /start command

    Args:
        update: Telegram update
        context: Bot context
    """
    try:
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) started bot")

        # Detect language from user's Telegram settings if available
        language_code = user.language_code if user.language_code in ["en", "fr", "ar"] else "en"

        # Store user language preference in context
        context.user_data["language"] = language_code

        # Get greeting message
        greeting = format_greeting(language_code)

        await update.message.reply_text(greeting, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text(
            "Sorry, I encountered an error. Please try again."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    try:
        language = context.user_data.get("language", "en")
        help_message = format_help_message(language)

        await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        await update.message.reply_text(format_error_message())


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - show user statistics"""
    try:
        user = update.effective_user
        language = context.user_data.get("language", "en")

        # Show typing indicator
        await update.message.chat.send_action(ChatAction.TYPING)

        # Fetch user stats from API
        response = await api_client.get(f"{API_BASE_URL}/users/{user.id}/stats")

        if response.status_code == 200:
            stats = response.json()
            stats_message = format_stats_message(stats, language)
            await update.message.reply_text(stats_message, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(
                "No statistics available yet. Start chatting with me!"
            )

    except Exception as e:
        logger.error(f"Error in stats_command: {e}")
        await update.message.reply_text(format_error_message())


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /language command - change language preference"""
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [
            [
                InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
                InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
            ],
            [
                InlineKeyboardButton("🇲🇦 العربية", callback_data="lang_ar"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Choose your preferred language / Choisissez votre langue / اختر لغتك:",
            reply_markup=reply_markup,
        )

    except Exception as e:
        logger.error(f"Error in language_command: {e}")
        await update.message.reply_text(format_error_message())


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection callback"""
    try:
        query = update.callback_query
        await query.answer()

        language_map = {
            "lang_en": "en",
            "lang_fr": "fr",
            "lang_ar": "ar",
        }

        selected_language = language_map.get(query.data, "en")
        context.user_data["language"] = selected_language

        confirmation_messages = {
            "en": "✅ Language set to English",
            "fr": "✅ Langue définie sur Français",
            "ar": "✅ تم تعيين اللغة إلى العربية",
        }

        await query.edit_message_text(confirmation_messages[selected_language])

    except Exception as e:
        logger.error(f"Error in language_callback: {e}")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command - clear conversation history"""
    try:
        language = context.user_data.get("language", "en")

        # Clear user context
        context.user_data.clear()
        context.user_data["language"] = language

        messages = {
            "en": "✅ Conversation history cleared! Let's start fresh.",
            "fr": "✅ Historique de conversation effacé! Recommençons.",
            "ar": "✅ تم مسح سجل المحادثات! لنبدأ من جديد.",
        }

        await update.message.reply_text(messages[language])

    except Exception as e:
        logger.error(f"Error in clear_command: {e}")
        await update.message.reply_text(format_error_message())


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle regular text messages
    Main handler that processes user queries
    """
    try:
        user = update.effective_user
        message_text = update.message.text

        if not message_text:
            return

        logger.info(f"User {user.id} sent: {message_text[:100]}")

        # Show typing indicator
        await update.message.chat.send_action(ChatAction.TYPING)

        # Detect language if not set
        if "language" not in context.user_data:
            detected_lang = detect_language(message_text)
            context.user_data["language"] = detected_lang
        else:
            # Update language based on current message
            detected_lang = detect_language(message_text)
            if detected_lang != context.user_data["language"]:
                context.user_data["language"] = detected_lang

        language = context.user_data["language"]

        # Only handle standalone greetings with canned response (not "hey pal" or other variations)
        if is_greeting(message_text) and len(message_text.strip().split()) <= 2:
            # Check if it's JUST a greeting (like "hey" or "hello there")
            # Let the AI handle more complex greetings naturally
            if message_text.strip().lower() in ["hey", "hi", "hello", "bonjour", "salut", "مرحبا", "مرحباً"]:
                greeting = get_greeting(language)
                await update.message.reply_text(greeting)
                return

        # Call FastAPI backend for chat response
        payload = {
            "user_id": user.id,
            "message": message_text,
            "username": user.username,
            "full_name": user.full_name,
            "language": language,
        }

        response = await api_client.post(
            f"{API_BASE_URL}/chat",
            json=payload,
            timeout=60.0,
        )

        if response.status_code == 200:
            chat_response = response.json()
            response_text = chat_response["response"]

            # Format response for Telegram (handle long messages)
            messages = format_response_for_telegram(response_text)

            # Send response(s)
            for msg in messages:
                await update.message.reply_text(msg)

            # Log response metadata
            logger.info(
                f"Response sent to user {user.id}: "
                f"model={chat_response['model_used']}, "
                f"tokens={chat_response['tokens_used']}, "
                f"time={chat_response['response_time_ms']}ms, "
                f"cached={chat_response['from_cache']}"
            )

        else:
            logger.error(f"API error: {response.status_code} - {response.text}")
            await update.message.reply_text(format_error_message(language))

    except httpx.TimeoutException:
        logger.error("API request timeout")
        await update.message.reply_text(
            "⏱️ Request timed out. Please try again or simplify your question."
        )

    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        language = context.user_data.get("language", "en")
        await update.message.reply_text(format_error_message(language))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle errors in the bot

    Args:
        update: Telegram update
        context: Bot context
    """
    logger.error(f"Exception while handling an update: {context.error}")

    # Try to send error message to user if possible
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An unexpected error occurred. Please try again later."
            )
    except Exception as e:
        logger.error(f"Error sending error message: {e}")


# Analytics command (admin only - optional)
async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /analytics command - show system analytics (admin only)"""
    try:
        # Check if user is admin (you can configure this)
        ADMIN_USER_IDS = []  # Add admin user IDs here

        user = update.effective_user
        if user.id not in ADMIN_USER_IDS and ADMIN_USER_IDS:
            await update.message.reply_text("⛔ This command is for administrators only.")
            return

        await update.message.chat.send_action(ChatAction.TYPING)

        # Fetch analytics from API
        response = await api_client.get(f"{API_BASE_URL}/analytics?days=7")

        if response.status_code == 200:
            analytics = response.json()

            message = (
                f"📊 *ATLAS Analytics (Last 7 Days)*\n\n"
                f"💬 Total conversations: {analytics.get('total_conversations', 0)}\n"
                f"👥 Unique users: {analytics.get('unique_users', 0)}\n"
                f"🎯 Total tokens used: {analytics.get('total_tokens_used', 0):,}\n"
                f"📊 Avg tokens/conversation: {analytics.get('avg_tokens_per_conversation', 0):.1f}\n"
                f"⏱️ Avg response time: {analytics.get('avg_response_time_ms', 0):.0f}ms\n\n"
                f"*Model Usage:*\n"
                f"GPT-4: {analytics.get('gpt4_usage', 0)}\n"
                f"GPT-3.5: {analytics.get('gpt35_usage', 0)}"
            )

            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("Failed to fetch analytics.")

    except Exception as e:
        logger.error(f"Error in analytics_command: {e}")
        await update.message.reply_text(format_error_message())
