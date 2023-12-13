"""
BATCH capilities
"""

from handle.core import MessageTag, Capability

HEADER = {
    "name": "batch"
}


class BatchTag(MessageTag):
    name = "batch"
    local = 1

    def __init__(self, value):
        super().__init__(name=BatchTag.name, value=value)

    def is_visible_to(self, to_user):
        return super().is_visible_to(to_user) and to_user.has_capability("batch")


def init(module):
    Capability.add("batch")
    MessageTag.add(BatchTag)
