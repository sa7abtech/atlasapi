"""
Bot Utilities
Helper functions for the Telegram bot
"""

import logging
import re
from typing import Optional

logger = logging.getLogger("atlas.bot.utils")


def detect_language(text: str) -> str:
    """
    Detect language from text
    Supports: English (en), French (fr), Arabic (ar)

    Args:
        text: Text to analyze

    Returns:
        Language code (en, fr, or ar)
    """
    # Arabic unicode ranges
    arabic_pattern = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+")

    # French common words and patterns
    french_words = [
        "bonjour",
        "merci",
        "comment",
        "pourquoi",
        "je",
        "tu",
        "il",
        "nous",
        "vous",
        "sont",
        "suis",
        "êtes",
        "avez",
    ]

    text_lower = text.lower()

    # Check for Arabic
    if arabic_pattern.search(text):
        return "ar"

    # Check for French
    if any(word in text_lower for word in french_words):
        return "fr"

    # Default to English
    return "en"


def format_response_for_telegram(text: str, max_length: int = 4096) -> list[str]:
    """
    Format response for Telegram (max message length is 4096 characters)
    Split long messages into multiple parts if needed

    Args:
        text: Response text
        max_length: Maximum length per message

    Returns:
        List of message chunks
    """
    if len(text) <= max_length:
        return [text]

    # Split by paragraphs first
    paragraphs = text.split("\n\n")
    messages = []
    current_message = ""

    for para in paragraphs:
        if len(current_message) + len(para) + 2 <= max_length:
            current_message += para + "\n\n"
        else:
            if current_message:
                messages.append(current_message.strip())
            current_message = para + "\n\n"

    if current_message:
        messages.append(current_message.strip())

    return messages


def escape_markdown(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]

    for char in special_chars:
        text = text.replace(char, f"\\{char}")

    return text


def format_greeting(language: str = "en") -> str:
    """
    Get greeting message in specified language

    Args:
        language: Language code (en, fr, ar)

    Returns:
        Greeting message
    """
    greetings = {
        "en": (
            "Hey! ATLAS here 👋\n\n"
            "Your AWS cloud partner based in Morocco. Here's what we can tackle:\n\n"
            "💰 *Cut your cloud costs* (we're talking 40-60% savings)\n"
            "☁️ *AWS migrations* that actually work\n"
            "🔧 *Odoo/Sage to cloud* - done it dozens of times\n"
            "🔥 *Fix what's broken* in your infrastructure\n"
            "🇲🇦 *Morocco-specific* solutions (we get it)\n\n"
            "I remember everything we discuss, so no need to repeat yourself.\n"
            "What are we working on?"
        ),
        "fr": (
            "Salut! C'est ATLAS 👋\n\n"
            "Ton partenaire AWS cloud basé au Maroc. Voilà ce qu'on peut faire:\n\n"
            "💰 *Réduire tes coûts cloud* (on parle de 40-60% d'économies)\n"
            "☁️ *Migrations AWS* qui marchent vraiment\n"
            "🔧 *Odoo/Sage vers le cloud* - fait ça des dizaines de fois\n"
            "🔥 *Réparer ce qui déconne* dans ton infra\n"
            "🇲🇦 *Solutions Maroc* (on connaît le terrain)\n\n"
            "Je me souviens de tout ce qu'on discute, pas besoin de répéter.\n"
            "On bosse sur quoi?"
        ),
        "ar": (
            "مرحباً! أنا ATLAS 👋\n\n"
            "شريكك في AWS السحابي في المغرب. هاشنو نقدر نديروا:\n\n"
            "💰 *تخفيض التكاليف* (كنتكلموا على 40-60% اقتصاد)\n"
            "☁️ *الهجرة ل AWS* اللي كتخدم مزيان\n"
            "🔧 *Odoo/Sage للسحابة* - درناها عشرات المرات\n"
            "🔥 *إصلاح المشاكل* في البنية التحتية\n"
            "🇲🇦 *حلول خاصة بالمغرب* (كنعرفوا السوق)\n\n"
            "كنتفكر كلشي كنتناقشو فيه، مابغيناش التكرار.\n"
            "شنو خدامين عليه؟"
        ),
    }

    return greetings.get(language, greetings["en"])


def format_help_message(language: str = "en") -> str:
    """
    Get help message in specified language

    Args:
        language: Language code

    Returns:
        Help message
    """
    help_messages = {
        "en": (
            "🤖 *ATLAS Help*\n\n"
            "*Available Commands:*\n"
            "/start - Start conversation and see greeting\n"
            "/help - Show this help message\n"
            "/stats - View your usage statistics\n"
            "/clear - Clear conversation history (start fresh)\n"
            "/language - Change language preference\n\n"
            "*What I Can Do:*\n"
            "• Answer questions about AWS cloud solutions\n"
            "• Provide cost optimization strategies\n"
            "• Help with Odoo/Sage migration\n"
            "• Troubleshoot infrastructure issues\n"
            "• Remember your business context\n\n"
            "*Tips:*\n"
            "• I remember all our conversations\n"
            "• Be specific for better answers\n"
            "• I can switch languages automatically\n"
            "• Ask follow-up questions anytime"
        ),
        "fr": (
            "🤖 *Aide ATLAS*\n\n"
            "*Commandes Disponibles:*\n"
            "/start - Démarrer la conversation\n"
            "/help - Afficher ce message d'aide\n"
            "/stats - Voir vos statistiques d'utilisation\n"
            "/clear - Effacer l'historique des conversations\n"
            "/language - Changer la langue\n\n"
            "*Ce Que Je Peux Faire:*\n"
            "• Répondre aux questions sur AWS cloud\n"
            "• Fournir des stratégies d'optimisation des coûts\n"
            "• Aider à la migration Odoo/Sage\n"
            "• Dépanner les problèmes d'infrastructure\n"
            "• Me souvenir de votre contexte commercial\n\n"
            "*Conseils:*\n"
            "• Je me souviens de toutes nos conversations\n"
            "• Soyez précis pour de meilleures réponses\n"
            "• Je peux changer de langue automatiquement\n"
            "• Posez des questions de suivi à tout moment"
        ),
        "ar": (
            "🤖 *مساعدة ATLAS*\n\n"
            "*الأوامر المتاحة:*\n"
            "/start - بدء المحادثة\n"
            "/help - عرض رسالة المساعدة هذه\n"
            "/stats - عرض إحصائيات الاستخدام\n"
            "/clear - مسح سجل المحادثات\n"
            "/language - تغيير اللغة\n\n"
            "*ما يمكنني فعله:*\n"
            "• الإجابة على أسئلة حول حلول AWS السحابية\n"
            "• توفير استراتيجيات تحسين التكلفة\n"
            "• المساعدة في ترحيل Odoo/Sage\n"
            "• استكشاف مشاكل البنية التحتية\n"
            "• تذكر سياق عملك\n\n"
            "*نصائح:*\n"
            "• أتذكر جميع محادثاتنا\n"
            "• كن محددًا للحصول على إجابات أفضل\n"
            "• يمكنني تبديل اللغات تلقائيًا\n"
            "• اطرح أسئلة متابعة في أي وقت"
        ),
    }

    return help_messages.get(language, help_messages["en"])


def format_stats_message(stats: dict, language: str = "en") -> str:
    """
    Format user statistics message

    Args:
        stats: User statistics dictionary
        language: Language code

    Returns:
        Formatted stats message
    """
    if language == "fr":
        return (
            f"📊 *Vos Statistiques*\n\n"
            f"💬 Conversations totales: {stats.get('total_conversations', 0)}\n"
            f"🎯 Tokens utilisés: {stats.get('total_tokens_used', 0):,}\n"
            f"💰 Tokens économisés: {stats.get('total_tokens_saved', 0):,}\n"
            f"🌍 Langue préférée: {stats.get('preferred_language', 'en').upper()}\n\n"
            f"Continuez à poser des questions pour économiser encore plus de tokens grâce au cache!"
        )
    elif language == "ar":
        return (
            f"📊 *إحصائياتك*\n\n"
            f"💬 إجمالي المحادثات: {stats.get('total_conversations', 0)}\n"
            f"🎯 الرموز المستخدمة: {stats.get('total_tokens_used', 0):,}\n"
            f"💰 الرموز المحفوظة: {stats.get('total_tokens_saved', 0):,}\n"
            f"🌍 اللغة المفضلة: {stats.get('preferred_language', 'en').upper()}\n\n"
            f"استمر في طرح الأسئلة لتوفير المزيد من الرموز من خلال التخزين المؤقت!"
        )
    else:  # English
        return (
            f"📊 *Your Statistics*\n\n"
            f"💬 Total conversations: {stats.get('total_conversations', 0)}\n"
            f"🎯 Tokens used: {stats.get('total_tokens_used', 0):,}\n"
            f"💰 Tokens saved: {stats.get('total_tokens_saved', 0):,}\n"
            f"🌍 Preferred language: {stats.get('preferred_language', 'en').upper()}\n\n"
            f"Keep asking questions to save even more tokens through caching!"
        )


def format_error_message(language: str = "en") -> str:
    """
    Get error message in specified language

    Args:
        language: Language code

    Returns:
        Error message
    """
    error_messages = {
        "en": (
            "❌ Sorry, I encountered an error processing your request.\n\n"
            "Please try again in a moment. If the problem persists, contact support."
        ),
        "fr": (
            "❌ Désolé, j'ai rencontré une erreur lors du traitement de votre demande.\n\n"
            "Veuillez réessayer dans un instant. Si le problème persiste, contactez le support."
        ),
        "ar": (
            "❌ عذرًا، واجهت خطأ في معالجة طلبك.\n\n"
            "يرجى المحاولة مرة أخرى بعد لحظة. إذا استمرت المشكلة، اتصل بالدعم."
        ),
    }

    return error_messages.get(language, error_messages["en"])


def is_greeting(text: str) -> bool:
    """
    Check if message is a greeting

    Args:
        text: Message text

    Returns:
        True if greeting detected
    """
    greetings = [
        "hello",
        "hi",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "bonjour",
        "salut",
        "bonsoir",
        "مرحبا",
        "السلام عليكم",
        "صباح الخير",
    ]

    text_lower = text.lower().strip()

    return any(greeting in text_lower for greeting in greetings)


def extract_command_args(text: str) -> Optional[str]:
    """
    Extract arguments from a command message

    Args:
        text: Message text (e.g., "/command arg1 arg2")

    Returns:
        Arguments string or None
    """
    parts = text.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else None
