from handle.core import MessageTag


class TypingTag(MessageTag):
    name = "+draft/reply"

    def __init__(self, value):
        super().__init__(name=TypingTag.name, value=value)


def init(module):
    MessageTag.add(TypingTag)
