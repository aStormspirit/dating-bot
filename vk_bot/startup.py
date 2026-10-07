"""Проверка доступа к Long Poll и совместимость ответов VK с Pydantic."""

import requests

from vk_bot.config import API_VERSION


def rebuild_vkbottle_response_models() -> None:
    """Дособирает модели ответов VK, которые Pydantic 2.13 не собирает на Python 3.10.

    Иначе messages.send падает с ошибкой: MessagesSendPeerIdsResponse is not fully defined.
    """
    import vkbottle_types.objects as objects
    import vkbottle_types.responses as responses
    from vkbottle_types.base_model import BaseModel

    types_namespace = vars(objects)
    for model in vars(responses).values():
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            continue
        if model is BaseModel or model.__pydantic_complete__:
            continue
        if model.__module__.startswith("vkbottle_types.codegen"):
            continue
        model.model_rebuild(_types_namespace=types_namespace)


def preflight_check(token: str) -> int:
    """Проверяет доступ к Long Poll до запуска бота. Возвращает group_id."""
    response = requests.get(
        "https://api.vk.com/method/groups.getById",
        params={"access_token": token, "v": API_VERSION},
        timeout=15,
    ).json()

    if "error" in response:
        err = response["error"]
        raise SystemExit(
            f"Токен невалиден или это не ключ сообщества.\n"
            f"VK Error [{err.get('error_code')}]: {err.get('error_msg')}\n"
            f"Возьмите ключ: Управление сообществом → Работа с API → Ключи доступа"
        )

    raw = response["response"]
    group = raw[0] if isinstance(raw, list) else raw["groups"][0]
    group_id = int(group["id"])

    lp = requests.get(
        "https://api.vk.com/method/groups.getLongPollServer",
        params={"access_token": token, "group_id": group_id, "v": API_VERSION},
        timeout=15,
    ).json()

    if "error" in lp:
        err = lp["error"]
        raise SystemExit(
            f"Нет доступа к Long Poll (это и есть Error 15 / 1133).\n"
            f"Сообщество: {group.get('name')} (id={group_id})\n"
            f"VK Error [{err.get('error_code')}] subcode={err.get('error_subcode')}: "
            f"{err.get('error_msg')}\n\n"
            f"Сделайте по шагам:\n"
            f"  1. Сообщения сообщества → включить\n"
            f"  2. Работа с API → Long Poll API → Включено\n"
            f"     + событие «Входящее сообщение» (message_new)\n"
            f"  3. Ключи доступа → НОВЫЙ ключ с правами:\n"
            f"       • Сообщения сообщества\n"
            f"       • Управление сообществом\n"
            f"  4. Вставьте новый ключ в .env без кавычек\n"
            f"  5. Для подробностей: python diagnose.py"
        )

    return group_id
