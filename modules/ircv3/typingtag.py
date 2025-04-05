"""
Provides +typing client tag.
https://ircv3.net/specs/client-tags/typing.html
"""

from modules.ircv3.messagetags import MessageTag


class TypingTag(MessageTag):
    name = "+typing"

    def __init__(self, value):
        super().__init__(name=TypingTag.name, value=value)


def post_load(module):
    MessageTag.add(TypingTag)
