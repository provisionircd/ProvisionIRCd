"""
no-implicit-names capability (draft)
https://ircv3.net/specs/extensions/no-implicit-names

Do not send NAMES messages to users joining channels.
"""

from handle.core import Capability


def init(module):
    Capability.add("draft/no-implicit-names")
