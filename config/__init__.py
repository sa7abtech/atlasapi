"""
ATLAS Configuration Package
"""

from .settings import settings, Settings, get_log_config
from .prompts import (
    ATLAS_SYSTEM_PROMPT,
    build_context_prompt,
    get_greeting,
    format_response_template,
    calculate_aws_savings_estimate,
    MOROCCO_BUSINESS_CONTEXT,
)

__all__ = [
    "settings",
    "Settings",
    "get_log_config",
    "ATLAS_SYSTEM_PROMPT",
    "build_context_prompt",
    "get_greeting",
    "format_response_template",
    "calculate_aws_savings_estimate",
    "MOROCCO_BUSINESS_CONTEXT",
]
