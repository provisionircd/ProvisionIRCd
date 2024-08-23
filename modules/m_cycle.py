"""
/cycle command
"""

from handle.core import IRCD, Command, Numeric, Flag
from handle.logger import logging


def cmd_cycle(client, recv):
    for chan in recv[1].split(','):
        chan = IRCD.strip_format(chan)
        if not (channel := IRCD.find_channel(chan)):
            client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, chan)
            continue

        if not client.channels:
            client.sendnumeric(Numeric.ERR_NOTONCHANNEL, chan)
            continue

        Command.do(client, "PART", channel.name, "Cycling")
        Command.do(client, "JOIN", channel.name)


def init(module):
    Command.add(module, cmd_cycle, "CYCLE", 1, Flag.CMD_USER)
