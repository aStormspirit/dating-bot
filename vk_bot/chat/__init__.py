"""Публичный фасад анонимного чата: поиск живого собеседника и пересылка реплик."""

from vk_bot.chat.session import (
    FOUND_TEXT,
    SEARCHING_TEXT,
    adopt_legacy_vk,
    begin_search,
    format_partner,
    is_chatting,
    is_searching,
    pair_searcher,
    partner_of,
    remember_visitor,
    stop_chat,
)

__all__ = (
    "FOUND_TEXT",
    "SEARCHING_TEXT",
    "adopt_legacy_vk",
    "begin_search",
    "format_partner",
    "is_chatting",
    "is_searching",
    "pair_searcher",
    "partner_of",
    "remember_visitor",
    "stop_chat",
)
