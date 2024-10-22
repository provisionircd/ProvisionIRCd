"""
channel mode +P (permanent channel)
"""

from handle.core import IRCD, Channel, Channelmode, Hook

ChannelData = {}


def permanent_channel_destroy(client, channel):
    if 'P' in channel.modes:
        IRCD.channel_count += 1
        Channel.table.append(channel)


def permanent_channel_join(client, channel):
    if 'P' in channel.modes and channel.membercount == 1:
        channel.member_take_modes(client, 'o')


def save_channel(client, channel, *args):
    """ Save channel info to json """
    if 'P' not in channel.modes:
        return

    ChannelData[channel.name] = {
        "params": {mode: channel.get_param(mode) for mode in channel.modes if channel.get_param(mode)},
        "listmodes": {
            mode: [[le.mask, le.set_by, le.set_time] for le in channel.List[mode]]
            for mode in [m.flag for m in Channelmode.table if m.type == Channelmode.LISTMODE]
            if channel.List[mode]
        },
        "topic": (channel.topic, channel.topic_time, channel.topic_author),
        "modes": channel.modes,
        "creation": channel.creationtime
    }

    IRCD.write_data_file(ChannelData, "channels.db")


def restore_channel():
    """ Restore channel from json """
    if ChannelData := IRCD.read_data_file("channels.db"):
        for chan, data in ChannelData.items():
            channel = IRCD.create_channel(IRCD.me, chan)
            channel.creationtime = data["creation"]
            channel.modes = data["modes"]

            for mode, param in data["params"].items():
                channel.add_param(mode, param)

            for listmode, entries in data["listmodes"].items():
                for mask, setter, timestamp in entries:
                    channel.add_to_list(client=IRCD.me, mask=mask, _list=channel.List[listmode], setter=setter, timestamp=timestamp)

            if "topic" in data:
                channel.topic, channel.topic_time, channel.topic_author = data["topic"]


def save_channel_mode(client, channel, modebuf, parambuf):
    if 'P' in modebuf:
        ChannelData = IRCD.read_data_file("channels.db")
        if 'P' not in channel.modes and channel.name in ChannelData:
            del ChannelData[channel.name]
            if channel.membercount == 0:
                IRCD.destroy_channel(IRCD.me, channel)
            IRCD.write_data_file(ChannelData, "channels.db")

    save_channel(client, channel)


def init(module):
    Cmode_P = Channelmode()
    Cmode_P.flag = 'P'
    Cmode_P.is_ok = Channelmode.allow_opers
    Cmode_P.desc = "Channel is permanent. All data will be restored on server restart"
    Channelmode.add(module, Cmode_P)
    Hook.add(Hook.LOCAL_CHANNEL_MODE, save_channel_mode)
    Hook.add(Hook.TOPIC, save_channel)
    Hook.add(Hook.BOOT, restore_channel)
    Hook.add(Hook.CHANNEL_DESTROY, permanent_channel_destroy)
    Hook.add(Hook.PRE_LOCAL_JOIN, permanent_channel_join)
