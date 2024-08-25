"""
channel mode +P (permanent channel)
"""

from handle.core import IRCD, Channelmode, Hook

ChannelData = {}


def save_channel(*args):
    """ Save channel info to json """
    for channel in [c for c in IRCD.get_channels() if 'P' in c.modes]:
        ChannelData.setdefault(channel.name, {})
        ChannelData[channel.name].setdefault("params", {})
        ChannelData[channel.name].setdefault("listmodes", {})
        ChannelData[channel.name]["topic"] = channel.topic, channel.topic_time, channel.topic_author
        ChannelData[channel.name]["modes"] = channel.modes
        ChannelData[channel.name]["creation"] = channel.creationtime
        for mode in channel.modes:
            if param := channel.get_param(mode):
                ChannelData[channel.name]["params"][mode] = param

        """ Saving list modes """
        for mode in [m.flag for m in Channelmode.table if m.type == Channelmode.LISTMODE]:
            if channel.List[mode]:
                ChannelData[channel.name]["listmodes"][mode] = [[le.mask, le.set_by, le.set_time] for le in channel.List[mode]]

    IRCD.write_data_file(ChannelData, "channels.db")


def restore_channel():
    """ Restore channel from json """
    if ChannelData := IRCD.read_data_file("channels.db"):
        for chan in ChannelData:
            if channel := IRCD.create_channel(IRCD.me, chan):
                channel.creationtime = ChannelData[chan]["creation"]
                channel.modes = ChannelData[chan]["modes"]
                for pmode in ChannelData[chan]["params"]:
                    mode, param = pmode, ChannelData[chan]["params"][pmode]
                    channel.add_param(mode, param)
                for listmode in ChannelData[chan]["listmodes"]:
                    for entry in ChannelData[chan]["listmodes"][listmode]:
                        mask, setter, timestamp = entry
                        channel.add_to_list(client=IRCD.me, mask=mask, _list=channel.List[listmode], setter=setter, timestamp=timestamp)

                if "topic" in ChannelData[chan]:
                    channel.topic, channel.topic_time, channel.topic_author = ChannelData[chan]["topic"]


def save_channel_mode(client, channel, modebuf, parambuf):
    if 'P' in modebuf and 'P' not in channel.modes and channel.name in ChannelData:
        del ChannelData[channel.name]
    save_channel()


def init(module):
    Cmode_P = Channelmode()
    Cmode_P.flag = 'P'
    Cmode_P.is_ok = Channelmode.allow_opers
    Cmode_P.desc = "Channel is permanent. All data will be restored on server restart"
    Channelmode.add(module, Cmode_P)
    Hook.add(Hook.LOCAL_CHANNEL_MODE, save_channel_mode)
    Hook.add(Hook.REMOTE_CHANNEL_MODE, save_channel_mode)
    Hook.add(Hook.TOPIC, save_channel)
    Hook.add(Hook.BOOT, restore_channel)
