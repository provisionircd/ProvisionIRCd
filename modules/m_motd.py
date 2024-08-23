"""
/motd and /rules commands
"""

import os

from handle.core import Numeric, IRCD, Command


def cmd_motd(client, recv):
    """
    Displays the message of the day.
    This does usually not change every day,
    but it can still contain useful information.
    """

    if client.local:
        client.local.flood_penalty += 50_000
    if len(recv) == 1:
        file = IRCD.confdir + "ircd.motd"
        if not os.path.isfile(file):
            return client.sendnumeric(Numeric.ERR_NOMOTD)
        client.sendnumeric(Numeric.RPL_MOTDSTART, IRCD.me.name)
        try:
            with open(file) as f:
                for line in f.read().split('\n'):
                    client.sendnumeric(Numeric.RPL_MOTD, line.rstrip())
        except:
            pass
        client.sendnumeric(Numeric.RPL_ENDOFMOTD)


def cmd_rules(client, recv):
    if client.local:
        client.local.flood_penalty += 50_000
    if len(recv) == 1:
        file = IRCD.confdir + "ircd.rules"
        if not os.path.isfile(file):
            return client.sendnumeric(Numeric.ERR_NORULES)
        client.sendnumeric(Numeric.RPL_RULESSTART, IRCD.me.name)
        try:
            with open(file) as f:
                for line in f.read().split('\n'):
                    client.sendnumeric(Numeric.RPL_RULES, line.rstrip())
        except:
            pass
        client.sendnumeric(Numeric.RPL_ENDOFRULES)


def init(module):
    Command.add(module, cmd_motd, "MOTD")
    Command.add(module, cmd_rules, "RULES")
