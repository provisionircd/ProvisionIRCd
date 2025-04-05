"""
Basic channel founder support
"""

from time import time
from handle.core import IRCD, Client, Command, Hook


class ChannelsDict(dict):
    """
    Because I cannot work with Channel objects directly due to how objects are cleaned up after quit events,
    I have to work with channel names as strings. Better make them case-insensitive.
    """

    def __setitem__(self, key, value):
        super().__setitem__(key.lower(), value)

    def __getitem__(self, key):
        return super().__getitem__(key.lower())

    def __delitem__(self, key):
        super().__delitem__(key.lower())

    def __contains__(self, key):
        # noinspection PyUnresolvedReferences
        return super().__contains__(key.lower())

    def pop(self, key, default=None):
        return super().pop(key.lower(), default)


class Founders:
    channels = ChannelsDict()

    @staticmethod
    def set(channel: str, client: Client = None):
        if client:
            Founders.channels[channel] = {
                "last_seen": int(time()),
                "fullmask": client.fullmask,
                "certfp": client.get_md_value("certfp"),
                "account": client.user.account,
                "ip": client.ip,
                "fullrealhost": client.fullrealhost
            }
        else:
            Founders.channels.pop(channel, None)

    @staticmethod
    def is_founder(channel: str, client: Client) -> bool:
        if not client.user:
            return False

        return channel in Founders.channels and (
                client.fullrealhost == Founders.channels[channel].get("fullrealhost") or
                client.get_md_value("certfp") == Founders.channels[channel].get("certfp") or
                client.user.account != '*' and client.user.account == Founders.channels[channel].get("account")
        )

    @staticmethod
    def founder_is_online(channel: str):
        """
        Checks if the channel founder is online, and then returns it.
        """

        if chan_obj := IRCD.find_channel(channel):
            founder_client = next((client for client in chan_obj.clients() if Founders.is_founder(channel, client)), 0)
            return founder_client


def expire_founder():
    for channel in list(Founders.channels):
        last_seen = Founders.channels[channel]["last_seen"]
        if int(time()) >= last_seen + 1800 and not Founders.founder_is_online(channel):
            Founders.set(channel, client=None)


def check_founder_pre_join(client, channel):
    if channel.membercount == 1 and channel.name[0] != '+' and 'P' not in channel.modes:
        if channel.name in Founders.channels:
            if not Founders.is_founder(channel.name, client):
                channel.member_take_modes(client, 'o')
        else:
            channel.member_give_modes(client, 'o')
            if not next((c for c in Founders.channels if Founders.is_founder(c, client)), 0):
                Founders.set(channel.name, client=client)


def check_founder_join(client, channel):
    if channel.name not in Founders.channels or channel.name[0] == '+' or 'r' in channel.modes:
        return

    if (founder := Founders.founder_is_online(channel.name)) and founder != client and channel.client_has_membermodes(founder, 'o'):
        """
        The current founder is not the same as joining user.
        """
        return

    if Founders.is_founder(channel.name, client) and not channel.client_has_membermodes(client, 'o'):
        Command.do(IRCD.me, "MODE", channel.name, "+o", client.name)


def founder_remove_part(client, channel, *args):
    Founders.set(channel.name, client=None)


def founder_remove_kick(client, target_client, channel, *args):
    Founders.set(channel.name, client=None)


def update_founder_timestamp(client, reason):
    for channel in (c for c in IRCD.get_channels() if c.name in Founders.channels and Founders.is_founder(c.name, client)):
        if client.is_killed():
            Founders.set(channel.name, client=None)
        elif client not in Client.table:
            Founders.channels[channel.name]["last_seen"] = int(time())


def founder_remove_sjoin(client, recv):
    """
    recv[2]:     Channel name as string.
    """

    Founders.set(recv[2], client=None)


def founder_destroy_channel(client, channel):
    Founders.set(channel.name, client=None)


def init(module):
    Hook.add(Hook.PRE_LOCAL_JOIN, check_founder_pre_join)
    Hook.add(Hook.LOCAL_JOIN, check_founder_join)
    Hook.add(Hook.LOCAL_QUIT, update_founder_timestamp)
    Hook.add(Hook.LOCAL_PART, founder_remove_part)
    Hook.add(Hook.LOCAL_KICK, founder_remove_kick)
    Hook.add(Hook.SERVER_SJOIN_IN, founder_remove_sjoin)
    # Hook.add(Hook.CHANNEL_DESTROY, founder_destroy_channel)
    Hook.add(Hook.LOOP, expire_founder)
