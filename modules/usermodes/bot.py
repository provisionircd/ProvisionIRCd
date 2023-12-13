"""
provides usermode +B, mark the user as a bot, and adds support for "bot" message tag.
"""

from handle.core import Isupport, Numeric, Usermode, MessageTag, Hook


class BotTag(MessageTag):
    name = "bot"
    local = 1

    def __init__(self, value=None):
        super().__init__(name=BotTag.name)

    def is_visible_to(self, to_client):
        return super().is_visible_to(to_client)


def add_bot_tag(client):
    if client.user and "B" in client.user.modes:
        client.mtags.append(BotTag())
    return 0


def bot_whois(client, whois_client, lines):
    if "B" in whois_client.user.modes:
        line = (Numeric.RPL_WHOISBOT, whois_client.name, whois_client.uplink.name)
        lines.append(line)


def bot_who_flag(client, user, status):
    if "B" in user.modes:
        return "B"


def init(module):
    Usermode.add(module, "B", 1, 0, Usermode.allow_all, "Marks the user as a bot")
    Hook.add(Hook.WHOIS, bot_whois)
    Hook.add(Hook.WHO_STATUS, bot_who_flag)
    Hook.add(Hook.NEW_MESSAGE, add_bot_tag)
    Isupport.add("BOT", "B")
    MessageTag.add(BotTag)
