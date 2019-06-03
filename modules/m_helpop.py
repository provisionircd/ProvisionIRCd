#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/helpop command
"""

import ircd

import os
import sys

from handle.functions import _print

@ircd.Modules.commands('helpop', 'help', 'ircdhelp', 'hlep', 'hepl')
def help(self, localServer, recv):
    try:
        help = 1
        self.sendraw(292, ': -')
        self.sendraw(292, ': §~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§')
        self.sendraw(292, ': ~~~~~~~~~ ProvisionIRCd Help ~~~~~~~~~')
        self.sendraw(292, ': §~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§')
        self.sendraw(292, ': -')
        if len(recv) == 1:
            self.sendraw(292, ': This section shows you some information about this')
            self.sendraw(292, ': IRCd and her commands. For a more detailed description')
            self.sendraw(292, ': on a specific subject, use following commands:')
            self.sendraw(292, ': -')
            self.sendraw(292, ': /IRCDHELP UMODES - View all usermodes')
            self.sendraw(292, ': /IRCDHELP CHMODES - View all modes for your channel')
            self.sendraw(292, ': /IRCDHELP SNOMASKS - View all available snomasks')
            self.sendraw(292, ': /IRCDHELP OPERCMDS - Shows list of commands for IRC Ops')
            self.sendraw(292, ': /IRCDHELP USERCMDS - Lists all commands available for all users')
            self.sendraw(292, ': -')
            return
        if recv[1].lower() == 'umodes':
            umodes = sorted(localServer.user_modes)
            umodes.sort(key=lambda x:(not x.islower(), x))
            for m in [m for m in umodes if m.isalpha()]:
                mode = m[0]
                info = localServer.user_modes[mode]
                level = info[0]
                desc = info[1]
                self.sendraw(292, ': {} = {} ({})'.format(mode, desc, level))
            self.sendraw(292, ': -')
            return
        elif recv[1].lower() == 'chmodes':
            self.sendraw(292, ': v <nickname> - Give/take voice')
            self.sendraw(292, ': h <nickname> - Give/take halfop status')
            self.sendraw(292, ': o <nickname> - Give/take operator status')
            self.sendraw(292, ': a <nickname> - Give/take admin status')
            self.sendraw(292, ': q <nickname> - Give/take owner status')
            self.sendraw(292, ': -')

            chmodes = sorted(localServer.channel_modes[3])
            chmodes.sort(key=lambda x:(not x.islower(), x))
            for t in [t for t in localServer.channel_modes if t < 3]:
                for mode in localServer.channel_modes[t]:
                    level = ''.join([{2: '+h', 3: '+o', 4: '+a', 5: '+q', 6: 'IRCops only', 7: 'Settable by servers'}[localServer.channel_modes[t][mode][0]]])
                    info = localServer.channel_modes[t][mode]
                    desc = info[1]
                    if not desc: ### Generic mode?
                        continue
                    param_desc = None if len(info) != 3 else info[2]
                    self.sendraw(292, ': {}{} = {} [{}]'.format(mode, ' '+param_desc if param_desc else '', desc, level))
                self.sendraw(292, ': -')
            for mode in chmodes:
                level = ''.join([{2: '+h', 3: '+o', 4: '+a', 5: '+q', 6: 'IRCops only', 7: 'Settable by servers'}[localServer.channel_modes[3][mode][0]]])
                info = localServer.channel_modes[3][mode]
                desc = info[1]
                param_desc = None if len(info) != 3 else info[2]
                self.sendraw(292, ': {}{} = {} [{}]'.format(mode, ' '+param_desc if param_desc else '', desc, level))
            self.sendraw(292, ': -')
            return

        if recv[1].lower() == 'snomasks':
            snomasks = sorted(localServer.snomasks)
            snomasks.sort(key=lambda x:(not x.islower(), x))
            for sno in [sno for sno in snomasks if sno.isalpha()]:
                self.sendraw(292, ': {} = {}'.format(sno, localServer.snomasks[sno]))
            self.sendraw(292, ': -')
            return

        ### Loop over modules to check if they have a 'helpop' attr.
        for m in [m for m in localServer.modules if hasattr(m, 'helpop')]:
            if recv[1].lower() in m.helpop:
                for line in m.helpop[recv[1].lower()].split('\n'):
                    self.sendraw(292, ':'+line)
                self.sendraw(292, ':-')
                return
        self.sendraw(292, ':No help available for {}.'.format(recv[1]))
        self.sendraw(292, ':-')

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
