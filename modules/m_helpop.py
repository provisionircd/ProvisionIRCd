"""
/helpop command
"""

import ircd


@ircd.Modules.command
class Ircdhelp(ircd.Command):
    def __init__(self):
        self.command = ['helpop', 'help', 'ircdhelp', 'hlep', 'hepl']

    def execute(self, client, recv):
        is_help = 1
        help_cmds = [c for c in self.ircd.command_class if c.help]
        client.sendraw(292, ': -')
        client.sendraw(292, ': §~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§')
        client.sendraw(292, ': ~~~~~~~~~ ProvisionIRCd Help ~~~~~~~~~')
        client.sendraw(292, ': §~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§')
        client.sendraw(292, ': -')
        if len(recv) == 1:
            client.sendraw(292, ': This section shows you some information about this')
            client.sendraw(292, ': IRCd and her commands. For a more detailed description')
            client.sendraw(292, ': on a specific subject, use following commands:')
            client.sendraw(292, ': -')
            client.sendraw(292, ': /IRCDHELP UMODES - View all usermodes')
            client.sendraw(292, ': /IRCDHELP CHMODES - View all modes for your channel')
            client.sendraw(292, ': /IRCDHELP SNOMASKS - View all available snomasks')
            client.sendraw(292, ': /IRCDHELP OPERCMDS - Shows list of commands for IRC Ops')
            client.sendraw(292, ': /IRCDHELP USERCMDS - Lists all commands available for all users')
            client.sendraw(292, ': -')
            return

        if recv[1].lower() == 'umodes':
            umodes = sorted(self.ircd.user_modes)
            umodes.sort(key=lambda x: (not x.islower(), x))
            for m in [m for m in umodes if m.isalpha()]:
                mode = m[0]
                info = self.ircd.user_modes[mode]
                level = info[0]
                desc = info[1]
                client.sendraw(292, ': {} = {} ({})'.format(mode, desc, level))
            client.sendraw(292, ': -')
            return

        elif recv[1].lower() == 'chmodes':
            client.sendraw(292, ': v <nickname> - Give/take voice')
            client.sendraw(292, ': h <nickname> - Give/take halfop status')
            client.sendraw(292, ': o <nickname> - Give/take operator status')
            client.sendraw(292, ': a <nickname> - Give/take admin status')
            client.sendraw(292, ': q <nickname> - Give/take owner status')
            client.sendraw(292, ': -')

            chmodes = sorted(self.ircd.channel_modes[3])
            chmodes.sort(key=lambda x: (not x.islower(), x))
            for t in [t for t in self.ircd.channel_modes if t < 3]:
                for mode in self.ircd.channel_modes[t]:
                    level = ''.join([{2: '+h', 3: '+o', 4: '+a', 5: '+q', 6: 'IRCops only', 7: 'Settable by servers'}[self.ircd.channel_modes[t][mode][0]]])
                    info = self.ircd.channel_modes[t][mode]
                    desc = info[1]
                    if not desc:  ### Generic mode?
                        continue
                    param_desc = None if len(info) != 3 else info[2]
                    client.sendraw(292, ': {}{} = {} [{}]'.format(mode, ' ' + param_desc if param_desc else '', desc, level))
                client.sendraw(292, ': -')
            for mode in chmodes:
                level = ''.join([{2: '+h', 3: '+o', 4: '+a', 5: '+q', 6: 'IRCops only', 7: 'Settable by servers'}[self.ircd.channel_modes[3][mode][0]]])
                info = self.ircd.channel_modes[3][mode]
                desc = info[1]
                param_desc = None if len(info) != 3 else info[2]
                client.sendraw(292, ': {}{} = {} [{}]'.format(mode, ' ' + param_desc if param_desc else '', desc, level))
            client.sendraw(292, ': -')
            return

        if recv[1].lower() == 'snomasks':
            snomasks = sorted(self.ircd.snomasks)
            snomasks.sort(key=lambda x: (not x.islower(), x))
            for sno in [sno for sno in snomasks if sno.isalpha()]:
                client.sendraw(292, ': {} = {}'.format(sno, self.ircd.snomasks[sno]))
            client.sendraw(292, ': -')
            return

        if recv[1].lower() == 'usercmds':
            cmd_list = [cmd for cmd in help_cmds if ('o' not in cmd.req_modes and not cmd.req_flags) and cmd.req_class == 'User']
            line_queue = []
            for cmd_class in cmd_list:
                for cmd_name in cmd_class.command:
                    line_queue.append(cmd_name)
                    if len(line_queue) == 4:
                        client.sendraw(292, ':' + '          '.join(line_queue))
                        line_queue = []
                        continue
            if line_queue:
                client.sendraw(292, ':' + '          '.join(line_queue))
            client.sendraw(292, ': -')
            return

        if recv[1].lower() == 'opercmds':
            cmd_list = [cmd for cmd in help_cmds if ('o' in cmd.req_modes or cmd.req_flags) and cmd.req_class == 'User']
            line_queue = []
            for cmd_class in cmd_list:
                for cmd_name in cmd_class.command:
                    line_queue.append(cmd_name)
                    if len(line_queue) == 4:
                        client.sendraw(292, ':' + '          '.join(line_queue))
                        line_queue = []
                        continue
            if line_queue:
                client.sendraw(292, ':' + '          '.join(line_queue))
            client.sendraw(292, ': -')
            return

        ### Check if user did a /helpop <cmd>
        # cmd_match = [cmd for cmd in self.ircd.commands if cmd[0].lower() == recv[1].lower() and cmd[1].__doc__]
        cmd_match = [cmd for cmd in help_cmds if recv[1].upper() in cmd.command]
        if cmd_match:
            h = cmd_match[0].help.split('\n')
            for line in h:
                client.sendraw(292, ':' + line)
            # client.sendraw(292, ':-')
            return

        # New method.
        if recv[1].upper() in self.ircd.command_class:
            c = self.ircd.command_class[recv[1].upper()]
            info = c.__doc__.split('\n')
            for line in info:
                client.sendraw(292, ':' + line)
            client.sendraw(292, ':-')
            return

        ### Loop over modules to check if they have a 'helpop' attr.
        for m in [m for m in self.ircd.modules if hasattr(m, 'helpop')]:
            if recv[1].lower() in m.helpop:
                for line in m.helpop[recv[1].lower()].split('\n'):
                    client.sendraw(292, ':' + line)
                client.sendraw(292, ':-')
                return
        client.sendraw(292, ':No help available for {}.'.format(recv[1]))
        client.sendraw(292, ':-')
