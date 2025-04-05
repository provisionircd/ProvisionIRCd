"""
/quit command
"""

from handle.core import IRCD, Command, Hook, Flag


def cmd_quit(client, recv):
    if len(recv) > 1:
        reason = ' '.join(recv[1:][:128]).removeprefix(':')
    else:
        reason = client.name

    if static_quit := IRCD.get_setting("static-quit"):
        reason = static_quit[:128]

    if hook := Hook.call(Hook.PRE_LOCAL_QUIT, args=(client, reason)):
        for result, _ in hook:
            if result:
                reason = result

    if not (reason := reason.strip()):
        reason = client.name

    quitprefix = IRCD.get_setting("quitprefix") or "Quit"
    prefix = f"{quitprefix}: " if client.local else ''
    client.exit(f"{prefix}{reason}")


def init(module):
    Command.add(module, cmd_quit, "QUIT", 0, Flag.CMD_USER)
