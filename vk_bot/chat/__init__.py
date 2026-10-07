"""Публичный фасад анонимного чата: поиск, остановка и ответ собеседника."""

from vk_bot.chat.openers import pick_opener
from vk_bot.chat.replies import partner_reply
from vk_bot.chat.session import (
    SEARCHING_TEXT,
    begin_search,
    complete_search,
    format_partner,
    is_chatting,
    is_searching,
    opener_pending,
    remember_visitor,
    set_partner_gender,
    stop_chat,
)

__all__ = (
    "SEARCHING_TEXT",
    "begin_search",
    "complete_search",
    "format_partner",
    "is_chatting",
    "is_searching",
    "opener_pending",
    "partner_reply",
    "pick_opener",
    "remember_visitor",
    "set_partner_gender",
    "stop_chat",
)
