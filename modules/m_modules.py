"""
show modules with /modules
"""

from handle.core import IRCD, Command, Flag
from handle.functions import logging


def cmd_modules(client, recv):
    logging.debug(f"Listing all {len(IRCD.configuration.modules)} loaded modules.")
    for m in IRCD.configuration.modules:
        module = m.module
        info = module.__doc__
        cmds = ''
        if info:
            info = ' '.join(module.__doc__.split('\n'))
        for c in Command.table:
            if c.module == module:
                cmds += f'{", " if cmds else ""}' + '/' + c.trigger
        try:
            msg = f'* {module.__name__}{" -- {}".format(info) if info else ""}'
            IRCD.server_notice(client, msg)
        except AttributeError as ex:
            logging.error(f"Error while listing module: {m}")
            logging.exception(ex)


def init(module):
    Command.add(module, cmd_modules, "MODULES", 0, Flag.CMD_OPER)
