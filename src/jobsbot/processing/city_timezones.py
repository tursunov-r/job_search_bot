"""Maps common RU/CIS city names (as a subscriber might type them into the
"🏙 Города" filter) to an IANA timezone — used only to interpret "🌙 Тихие
часы" without making the subscriber pick a timezone themselves (see
push.py::_resolve_timezone). Not exhaustive: Telegram's Bot API doesn't
expose a client timezone at all, so this is a best-effort lookup from data
already on hand, not a surveyed/precise source. Unmatched or missing city
falls back to settings.bot_timezone.
"""

CITY_TIMEZONES: dict[str, str] = {
    # Europe/Kaliningrad (UTC+2)
    "калининград": "Europe/Kaliningrad",
    # Europe/Moscow (UTC+3)
    "москва": "Europe/Moscow",
    "санкт-петербург": "Europe/Moscow",
    "петербург": "Europe/Moscow",
    "спб": "Europe/Moscow",
    "воронеж": "Europe/Moscow",
    "краснодар": "Europe/Moscow",
    "сочи": "Europe/Moscow",
    "ростов-на-дону": "Europe/Moscow",
    "нижний новгород": "Europe/Moscow",
    "казань": "Europe/Moscow",
    "ярославль": "Europe/Moscow",
    "минск": "Europe/Minsk",
    "киев": "Europe/Kyiv",
    # Europe/Samara (UTC+4)
    "самара": "Europe/Samara",
    "ижевск": "Europe/Samara",
    "ульяновск": "Europe/Samara",
    "баку": "Asia/Baku",
    "ереван": "Asia/Yerevan",
    "тбилиси": "Asia/Tbilisi",
    # Asia/Yekaterinburg (UTC+5)
    "екатеринбург": "Asia/Yekaterinburg",
    "пермь": "Asia/Yekaterinburg",
    "челябинск": "Asia/Yekaterinburg",
    "уфа": "Asia/Yekaterinburg",
    "тюмень": "Asia/Yekaterinburg",
    "алматы": "Asia/Almaty",
    "астана": "Asia/Almaty",
    "нур-султан": "Asia/Almaty",
    "шымкент": "Asia/Almaty",
    "ташкент": "Asia/Tashkent",
    "душанбе": "Asia/Dushanbe",
    # Asia/Omsk (UTC+6)
    "омск": "Asia/Omsk",
    "бишкек": "Asia/Bishkek",
    # Asia/Novosibirsk / Asia/Krasnoyarsk (UTC+7)
    "новосибирск": "Asia/Novosibirsk",
    "барнаул": "Asia/Novosibirsk",
    "томск": "Asia/Novosibirsk",
    "кемерово": "Asia/Novosibirsk",
    "красноярск": "Asia/Krasnoyarsk",
    # Asia/Irkutsk (UTC+8)
    "иркутск": "Asia/Irkutsk",
    "улан-удэ": "Asia/Irkutsk",
    # Asia/Yakutsk (UTC+9)
    "якутск": "Asia/Yakutsk",
    # Asia/Vladivostok (UTC+10)
    "владивосток": "Asia/Vladivostok",
    "хабаровск": "Asia/Vladivostok",
    # Asia/Magadan (UTC+11)
    "магадан": "Asia/Magadan",
    # Asia/Kamchatka (UTC+12)
    "петропавловск-камчатский": "Asia/Kamchatka",
}


def resolve_city_timezone(cities: list[str]) -> str | None:
    """Returns the first match's IANA tz name, or None if no city in the
    list is recognized — caller decides the fallback."""
    for city in cities:
        tz_name = CITY_TIMEZONES.get(city.strip().lower())
        if tz_name:
            return tz_name
    return None
