"""
/time command
"""

from time import strftime
from handle.core import Command, Numeric


def cmd_time(client, recv):
    info = strftime("%A %B %d %Y -- %H:%M:%S %z UTC")
    client.sendnumeric(Numeric.RPL_TIME, info)


def init(module):
    Command.add(module, cmd_time, "TIME")
