"""
Draft of +reply client tag.
https://ircv3.net/specs/client-tags/reply.html
"""

from modules.ircv3.messagetags import MessageTag


class ReplyTag(MessageTag):
    name = "+draft/reply"
    value_required = 1

    def __init__(self, value):
        super().__init__(name=ReplyTag.name, value=value)

    def is_visible_to(self, to_client):
        return super().is_visible_to(to_client) and to_client.has_capability("echo-message")


def post_load(module):
    MessageTag.add(ReplyTag)
