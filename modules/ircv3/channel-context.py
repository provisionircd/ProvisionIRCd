"""
Draft of +channel-context client tag.
https://ircv3.net/specs/client-tags/channel-context
"""

from handle.core import IRCD
from modules.ircv3.messagetags import MessageTag


class ChannelContextTag(MessageTag):
    name = "+draft/channel-context"
    value_required = 1

    def __init__(self, value):
        super().__init__(name=ChannelContextTag.name, value=value)

    def value_is_ok(self, value):
        return bool(IRCD.find_channel(value))

    def filter_value(self, target) -> MessageTag:
        channel_name = IRCD.find_channel(self.value).name
        return ChannelContextTag(value=channel_name)


def post_load(module):
    MessageTag.add(ChannelContextTag)
