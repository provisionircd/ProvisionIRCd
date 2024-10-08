"""
/helpop command
"""

from handle.core import IRCD, Command, Flag, Numeric, Usermode, Channelmode, Snomask


def cmd_ircdhelp(client, recv):
    client.sendnumeric(Numeric.RPL_HELPTLR, '-')
    client.sendnumeric(Numeric.RPL_HELPTLR, "§~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§")
    client.sendnumeric(Numeric.RPL_HELPTLR, "~~~~~~~~~ ProvisionIRCd Help ~~~~~~~~~")
    client.sendnumeric(Numeric.RPL_HELPTLR, "§~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§")
    client.sendnumeric(Numeric.RPL_HELPTLR, '-')
    if len(recv) == 1:
        client.sendnumeric(Numeric.RPL_HELPTLR, "This section shows you some information about this")
        client.sendnumeric(Numeric.RPL_HELPTLR, "IRCd and her commands. For a more detailed description")
        client.sendnumeric(Numeric.RPL_HELPTLR, "on a specific subject, use following commands:")
        client.sendnumeric(Numeric.RPL_HELPTLR, '-')
        client.sendnumeric(Numeric.RPL_HELPTLR, " /IRCDHELP UMODES - View all usermodes")
        client.sendnumeric(Numeric.RPL_HELPTLR, " /IRCDHELP CHMODES - View all modes for your channel")
        client.sendnumeric(Numeric.RPL_HELPTLR, " /IRCDHELP SNOMASKS - View all available snomasks")
        client.sendnumeric(Numeric.RPL_HELPTLR, " /IRCDHELP OPERCMDS - Shows list of commands for IRC Ops")
        client.sendnumeric(Numeric.RPL_HELPTLR, " /IRCDHELP USERCMDS - Lists all commands available for all users")
        client.sendnumeric(Numeric.RPL_HELPTLR, '-')
        return

    if recv[1].lower() == "umodes":
        umodes_sorted = sorted([umode for umode in Usermode.table], key=lambda u: u.flag, reverse=False)
        for m in [m for m in umodes_sorted if m.desc]:
            special_perm = f" [{m.get_level_string()}]" if m.get_level_string() else ''
            client.sendnumeric(Numeric.RPL_HELPTLR, f"{m.flag} = {m.desc}{special_perm}")
        client.sendnumeric(Numeric.RPL_HELPTLR, ' -')
        return

    elif recv[1].lower() == "chmodes":
        help_modes = []
        member_modes = sorted([m for m in Channelmode.table if m.prefix and m.rank and m.type == Channelmode.MEMBER], key=lambda c: c.rank, reverse=True)
        help_modes.extend(member_modes)
        for mode in member_modes:
            if not mode.desc:
                continue
            client.sendnumeric(Numeric.RPL_HELPTLR, f" {mode.flag} <nickname> - {mode.desc} [{mode.level_help_string()}]")

        client.sendnumeric(Numeric.RPL_HELPTLR, '-')
        list_modes = [m for m in Channelmode.table if m.type == Channelmode.LISTMODE]
        help_modes.extend(list_modes)
        for mode in list_modes:
            client.sendnumeric(Numeric.RPL_HELPTLR, f" {mode.flag} {mode.param_help} - {mode.desc} [{mode.level_help_string()}]")

        client.sendnumeric(Numeric.RPL_HELPTLR, '-')
        type1_modes = sorted([m for m in Channelmode.table if m.unset_with_param and m not in help_modes], key=lambda c: c.flag, reverse=False)
        help_modes.extend(type1_modes)

        for mode in type1_modes:
            client.sendnumeric(Numeric.RPL_HELPTLR, f" {mode.flag} {mode.param_help} - {mode.desc} [{mode.level_help_string()}]")

        client.sendnumeric(Numeric.RPL_HELPTLR, '-')
        type2_modes = sorted([m for m in Channelmode.table if m.paramcount and not m.unset_with_param and m not in help_modes], key=lambda c: c.flag, reverse=False)
        help_modes.extend(type2_modes)

        for mode in type2_modes:
            info = f"{mode.flag}" + f"{' ' + mode.param_help if mode.param_help else ''}"
            client.sendnumeric(Numeric.RPL_HELPTLR, f" {info} - {mode.desc} [{mode.level_help_string()}]")

        client.sendnumeric(Numeric.RPL_HELPTLR, '-')
        type3_modes = sorted([m for m in Channelmode.table if not m.paramcount and m not in help_modes], key=lambda c: c.flag, reverse=False)
        help_modes.extend(type3_modes)

        for mode in type3_modes:
            client.sendnumeric(Numeric.RPL_HELPTLR, f" {mode.flag} - {mode.desc} [{mode.level_help_string()}]")
        client.sendnumeric(Numeric.RPL_HELPTLR, '-')
        return

    if recv[1].lower() == "snomasks":
        snomasks = sorted([s for s in Snomask.table], key=lambda s: s.flag, reverse=False)
        for sno in snomasks:
            client.sendnumeric(Numeric.RPL_HELPTLR, f" {sno.flag} = {sno.desc}")
        client.sendnumeric(Numeric.RPL_HELPTLR, '-')
        return

    if recv[1].lower() in ["usercmds", "opercmds"]:
        seen_funcs = set()
        cmd_list = []
        for cmd in Command.table:
            if hasattr(cmd, "func") and cmd.func not in seen_funcs:
                if recv[1].lower() == "usercmds" and Flag.CMD_SERVER not in cmd.flags and Flag.CMD_OPER not in cmd.flags:
                    cmd_list.append(cmd)
                    seen_funcs.add(cmd.func)

                elif recv[1].lower() == "opercmds" and Flag.CMD_SERVER not in cmd.flags and Flag.CMD_OPER in cmd.flags:
                    cmd_list.append(cmd)
                    seen_funcs.add(cmd.func)

        line_queue = []
        width = max([len(c.trigger) for c in cmd_list]) + 2
        for cmd in cmd_list:
            line_queue.append(cmd.trigger.upper())
            if len(line_queue) == 4:
                display = ''.join([t.ljust(width) for t in line_queue])
                client.sendnumeric(Numeric.RPL_HELPTLR, display)
                line_queue = []
                continue
        if line_queue:
            display = ''.join([t.ljust(width) for t in line_queue])
            client.sendnumeric(Numeric.RPL_HELPTLR, display)
        client.sendnumeric(Numeric.RPL_HELPTLR, ' -')
        client.sendnumeric(Numeric.RPL_HELPTLR, f"Use /{recv[0].upper()} <command> for more information, if available.")
        client.sendnumeric(Numeric.RPL_HELPTLR, '-')
        return

    else:
        for cmd in [cmd for cmd in Command.table if cmd.trigger.lower() == recv[1].lower()]:
            if cmd.func.__doc__:
                for line in cmd.func.__doc__.split('\n'):
                    if not line.strip():
                        continue
                    client.sendnumeric(Numeric.RPL_HELPTLR, line.strip())
                client.sendnumeric(Numeric.RPL_HELPTLR, ' -')
                return

        for mod in [mod for mod in IRCD.configuration.modules if hasattr(mod.module, "helpop")]:
            if recv[1].lower() in list(mod.module.helpop):
                for line in mod.module.info.split('\n'):
                    if not line.strip():
                        continue
                    client.sendnumeric(Numeric.RPL_HELPTLR, line.strip())
                client.sendnumeric(Numeric.RPL_HELPTLR, ' -')
                return

    client.sendnumeric(Numeric.RPL_HELPTLR, f"No help available for {recv[1]}.")
    client.sendnumeric(Numeric.RPL_HELPTLR, '-')


def init(module):
    Command.add(module, cmd_ircdhelp, "HELPOP")
    Command.add(module, cmd_ircdhelp, "HELP")
    Command.add(module, cmd_ircdhelp, "IRCDHELP")
    Command.add(module, cmd_ircdhelp, "HLEP")
    Command.add(module, cmd_ircdhelp, "HEPL")
