"""
provides channel settings with /chanset command
for now, this only works locally
"""

import time
from datetime import datetime

from handle.core import IRCD, Hook, Command, Flag, Channel, Client, Numeric
from handle.logger import logging


class Activities:
    kicks = {}
    joins = {}

    @staticmethod
    def add_kick(target_client, channel):
        Activities.kicks[channel][target_client] = int(time.time())


class Chanset:
    # Dictionary of channels as key, and list of Chanset objects as value.
    channels = {}

    def __init__(self, client: Client, name: str, param: str, set_by: str, set_time: int):
        self.name = name
        self.param = param
        self.set_by = set_by  # full realhost
        self.set_time = set_time

    def __repr__(self):
        return f"<Chanset '{self.name}:{self.param}'>"

    @staticmethod
    def add(client, chanset, channel: Channel):
        if existing_chanset := Chanset.get_setting(channel, chanset.name):
            Chanset.channels[channel].remove(existing_chanset)
        Chanset.channels[channel].append(chanset)
        IRCD.server_notice(client, f"Channel setting active for channel {channel.name} on {IRCD.me.name}: {chanset.name}:{chanset.param}")

    @staticmethod
    def remove(client, chanset, channel: Channel):
        Chanset.channels[channel].remove(chanset)
        IRCD.server_notice(client, f"Channel setting removed from {channel.name} on {IRCD.me.name}: {chanset.name}:{chanset.param}")

    @staticmethod
    def get_setting(channel: Channel, name: str):
        channel_settings = Chanset.channels.get(channel, [])
        return next((p for p in channel_settings if p.name == name), None)

    @staticmethod
    def get_settings(channel: Channel) -> list:
        return [p for p in Chanset.channels.get(channel, [])]


def cmd_chanset(client, recv):
    """
    Maintain local channel settings to expand functionality.
    CHANSET <channel>                        - View active settings.
    CHANSET <channel> <setting> :[param]     - Add or remove channel settings.
    -                                          To remove a setting, dismiss the param value.
    -                                          Example: CHANSET #Home rejoindelay :

    Current supported settings:
    rejoindelay <int(1-60)>        - Blocks immediate rejoins after kick for <int> seconds.
    nomasshighlight <int(>3)>      - Blocks mass highlights in the channel with more than <int> nicknames.
    -
    CHANSET settings are local. Meaning that they do not sync across the network,
    and they only affect local users.
    """

    if not (channel := IRCD.find_channel(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, recv[1])

    override = 0
    if client not in channel.clients():
        if not client.has_permission("channel:override:chanset"):
            return client.sendnumeric(Numeric.ERR_NOTONCHANNEL, channel.name)
        else:
            override = 1

    if not channel.client_has_membermodes(client, "aq"):
        if not client.has_permission("channel:override:chanset"):
            return client.sendnumeric(Numeric.ERR_CHANOPRIVSNEEDED, channel.name)
        override = 1

    if len(recv) == 2:
        """ List active settings for channel """
        if not (settings := Chanset.get_settings(channel)):
            return IRCD.server_notice(client, f"No settings active on channel {channel.name} on {IRCD.me.name}")

        IRCD.server_notice(client, f"Active settings on channel {channel.name} on {IRCD.me.name}:")
        for chanset in settings:
            dt_object = datetime.fromtimestamp(chanset.set_time)
            formatted_date = dt_object.strftime("%Y-%m-%d %H:%M:%S")
            IRCD.server_notice(client, f"{chanset.name}:{chanset.param} - set by {chanset.set_by} on {formatted_date}")
        return

    chansetting = recv[2].lower()
    if len(recv) < 4:
        return IRCD.server_notice(client, f"Missing parameter for channel setting '{chansetting}'")

    param = recv[3]

    match chansetting:
        case "rejoindelay":
            if param == ':':
                if not (chanset := Chanset.get_setting(channel, "rejoindelay")):
                    return IRCD.server_notice(client, f"No such channel setting active on channel {channel.name} on {IRCD.me.name}")

                Chanset.remove(client, chanset, channel)
                if override:
                    override_string = f"*** OperOverride by {client.name} ({client.user.username}@{client.user.realhost}) with CHANSET {channel.name} {chansetting} {param}"
                    IRCD.log(client, "info", "oper", "OPER_OVERRIDE", override_string, sync=1)
                return

            if not param.isdigit() or not 1 <= int(param) <= 60:
                return IRCD.server_notice(client, f"Rejoin delay must be an integer between 1 and 60 seconds.")

            chanset = Chanset(client=client, name="rejoindelay", param=str(param), set_by=client.fullrealhost, set_time=int(time.time()))
            Chanset.add(client, chanset, channel)
            if override:
                override_string = f"*** OperOverride by {client.name} ({client.user.username}@{client.user.realhost}) with CHANSET {channel.name} {chansetting} {param}"
                IRCD.log(client, "info", "oper", "OPER_OVERRIDE", override_string, sync=1)

        case "nomasshighlight":
            if param == ':':
                if not (chanset := Chanset.get_setting(channel, "nomasshighlight")):
                    return IRCD.server_notice(client, f"No such channel setting active on channel {channel.name} on {IRCD.me.name}")

                Chanset.remove(client, chanset, channel)
                if override:
                    override_string = f"*** OperOverride by {client.name} ({client.user.username}@{client.user.realhost}) with CHANSET {channel.name} {chansetting} {param}"
                    IRCD.log(client, "info", "oper", "OPER_OVERRIDE", override_string, sync=1)
                return

            if not param.isdigit() or not 3 <= int(param):
                return IRCD.server_notice(client, f"Nomasshighlight value must be an integer higher than 3.")

            chanset = Chanset(client=client, name="nomasshighlight", param=str(param), set_by=client.fullrealhost, set_time=int(time.time()))
            Chanset.add(client, chanset, channel)
            if override:
                override_string = f"*** OperOverride by {client.name} ({client.user.username}@{client.user.realhost}) with CHANSET {channel.name} {chansetting} {param}"
                IRCD.log(client, "info", "oper", "OPER_OVERRIDE", override_string, sync=1)

        case _:
            return IRCD.server_notice(client, f"Channel setting '{chansetting}' not supported.")


def chanset_register_kick(client, target_client, channel, reason):
    if not Chanset.get_setting(channel, "rejoindelay"):
        """ No need to register this activity. """
        return
    Activities.add_kick(target_client, channel)


def chanset_rejoindelay_can_join(client, channel, key):
    chanset = Chanset.get_setting(channel, "rejoindelay")
    if not chanset or client not in Activities.kicks.get(channel, {}):
        return 0

    if int(time.time()) - Activities.kicks[channel][client] <= int(chanset.param):
        return IRCD.server_notice(client, f"Wait a while before joining {channel.name} after a kick.")
    return 0


def expire_activities():
    current_time = int(time.time())
    for channel in (c for c in Channel.table if Chanset.get_setting(c, "rejoindelay")):
        if channel in Activities.kicks:
            chanset_param = int(Chanset.get_setting(channel, "rejoindelay").param)
            Activities.kicks[channel] = {client: kick_time for client, kick_time in Activities.kicks[channel].items()
                                         if kick_time + chanset_param > current_time}


def chanset_nomasshighlight_can_send(client, channel, message, sendtype):
    if not (chanset := Chanset.get_setting(channel, "nomasshighlight")):
        return Hook.CONTINUE

    msg_lower = set(IRCD.strip_format(message).lower().split())
    client_names = {c.name.lower() for c in channel.clients()}

    if len(client_names & msg_lower) >= int(chanset.param):
        client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, f"Message blocked: Mass highlighting is not allowed")
        return Hook.DENY

    return Hook.CONTINUE


def chanset_create_channel(client, channel):
    Chanset.channels[channel] = []
    Activities.kicks[channel] = {}


def chanset_create_all_channels():
    for channel in Channel.table:
        Chanset.channels[channel] = []
        Activities.kicks[channel] = {}


def chanset_cleanup_channel(client, channel):
    Chanset.channels.pop(channel, None)
    Activities.kicks.pop(channel, None)


def init(module):
    chanset_create_all_channels()
    Command.add(module, cmd_chanset, "CHANSET", 1, Flag.CMD_USER)
    Hook.add(Hook.LOCAL_KICK, chanset_register_kick)
    Hook.add(Hook.CAN_JOIN, chanset_rejoindelay_can_join)
    Hook.add(Hook.CAN_SEND_TO_CHANNEL, chanset_nomasshighlight_can_send)
    Hook.add(Hook.CHANNEL_CREATE, chanset_create_channel)
    Hook.add(Hook.CHANNEL_DESTROY, chanset_cleanup_channel)
    Hook.add(Hook.LOOP, expire_activities)
