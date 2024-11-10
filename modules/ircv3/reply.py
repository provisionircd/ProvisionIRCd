"""
Draft of +reply client tag.
https://ircv3.net/specs/client-tags/reply.html
"""

from handle.core import MessageTag


class ReplyTag(MessageTag):
    name = "+draft/reply"
    value_required = 1

    def __init__(self, value):
        super().__init__(name=ReplyTag.name, value=value)


def init(module):
    MessageTag.add(ReplyTag)
