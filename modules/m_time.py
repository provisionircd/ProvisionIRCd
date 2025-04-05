"""
/time command
"""

from time import strftime
from handle.core import Command, Numeric


def cmd_time(client, recv):
    info = strftime("%A %B %d %Y -- %H:%M:%S %z")
    formatted_time = info[:-2] + ":" + info[-2:]
    client.sendnumeric(Numeric.RPL_TIME, formatted_time)


def init(module):
    Command.add(module, cmd_time, "TIME")
