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

    match recv[1].lower():
        case "umodes" | "usermodes":
            for mode in sorted([m for m in Usermode.table if m.desc], key=lambda mode: mode.flag):
                level_info = f" [{mode.get_level_string()}]" if mode.get_level_string() else ''
                client.sendnumeric(Numeric.RPL_HELPTLR, f"{mode.flag} = {mode.desc}{level_info}")

            client.sendnumeric(Numeric.RPL_HELPTLR, ' -')
            return

        case "chmodes" | "channelmodes":
            processed_modes = []

            def display_mode_group(mode_filter, key=lambda m: m.flag, reverse=False, separator=1):
                modes = sorted((m for m in Channelmode.table if mode_filter(m) and m not in processed_modes), key=key, reverse=reverse)
                processed_modes.extend(modes)

                for mode in modes:
                    param_text = f" {mode.param_help}" if getattr(mode, "param_help", None) else ''
                    client.sendnumeric(Numeric.RPL_HELPTLR, f" {mode.flag}{param_text} - {mode.desc} [{mode.level_help_string()}]")

                if separator and modes:
                    client.sendnumeric(Numeric.RPL_HELPTLR, '-')

            display_mode_group(lambda m: m.prefix and m.rank and m.type == Channelmode.MEMBER, key=lambda m: m.rank, reverse=True)
            display_mode_group(lambda m: m.type == Channelmode.LISTMODE)
            display_mode_group(lambda m: m.unset_with_param)
            display_mode_group(lambda m: m.paramcount and not m.unset_with_param)
            display_mode_group(lambda m: not m.paramcount, separator=0)
            client.sendnumeric(Numeric.RPL_HELPTLR, '-')
            return

        case "snomasks":
            for sno in sorted(Snomask.table, key=lambda s: s.flag):
                client.sendnumeric(Numeric.RPL_HELPTLR, f" {sno.flag} = {sno.desc}")
            client.sendnumeric(Numeric.RPL_HELPTLR, '-')
            return

        case "usercmds" | "opercmds":
            is_oper_mode = recv[1].lower() == "opercmds"
            filtered_commands = []
            seen_functions = set()

            for cmd in Command.table:
                if (hasattr(cmd, "func") and cmd.func not in seen_functions and Flag.CMD_SERVER not in cmd.flags
                        and (Flag.CMD_OPER in cmd.flags) == is_oper_mode):
                    filtered_commands.append(cmd)
                    seen_functions.add(cmd.func)

            command_names = [cmd.trigger.upper() for cmd in filtered_commands]
            column_width = max(len(name) for name in command_names) + 2

            for i in range(0, len(command_names), 4):
                row = ''.join(name.ljust(column_width) for name in command_names[i:i + 4])
                client.sendnumeric(Numeric.RPL_HELPTLR, row)

            client.sendnumeric(Numeric.RPL_HELPTLR, ' -')
            client.sendnumeric(Numeric.RPL_HELPTLR, f"Use /{recv[0].upper()} <command> for more information, if available.")
            client.sendnumeric(Numeric.RPL_HELPTLR, '-')
            return

        case _:
            topic = recv[1].lower()

            def display_help_text(text):
                for line in [line for line in text.split('\n') if line.strip()]:
                    client.sendnumeric(Numeric.RPL_HELPTLR, line.strip())
                client.sendnumeric(Numeric.RPL_HELPTLR, ' -')

            for cmd in Command.table:
                if cmd.trigger.lower() == topic and cmd.func.__doc__:
                    display_help_text(cmd.func.__doc__)
                    return

            for mod in IRCD.configuration.modules:
                if hasattr(mod.module, "helpop") and topic in mod.module.helpop and hasattr(mod.module, "info"):
                    display_help_text(mod.module.info)
                    return

    client.sendnumeric(Numeric.RPL_HELPTLR, f"No help available for {recv[1]}.")
    client.sendnumeric(Numeric.RPL_HELPTLR, '-')


def init(module):
    Command.add(module, cmd_ircdhelp, "HELPOP")
    Command.add(module, cmd_ircdhelp, "HELP")
    Command.add(module, cmd_ircdhelp, "IRCDHELP")
    Command.add(module, cmd_ircdhelp, "HLEP")
    Command.add(module, cmd_ircdhelp, "HEPL")
