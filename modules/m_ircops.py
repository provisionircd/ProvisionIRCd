#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/ircops command (show online opers)
"""

import ircd

@ircd.Modules.commands('ircops')
def ircops(self, localServer, recv):
    self.sendraw(386, ':§~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§')
    self.sendraw(386, ':Nick                  Status      Server')
    self.sendraw(386, ':--------------------------------------------')
    globals, aways, opers = 0, 0, 0
    for oper in [user for user in self.server.users if 'o' in user.modes and ('H' not in user.modes or 'o' in self.modes) and 'S' not in user.modes]:
        opers += 1
        if 'o' in oper.modes:
            globals += 1
        if oper.away:
            aways += 1
        self.sendraw(386, ':{}{}{}{}{}{}'.format(oper.nickname, ' '*(22-int(len(oper.nickname))), 'Oper', ' (AWAY)' if oper.away else '', ' '*9 if not oper.away else ' '*2 , oper.server.hostname))
    self.sendraw(386, ':Total: {} IRCOP{} connected - {} Global, and {} Away'.format(opers, 's' if opers != 1 else '', globals, aways))
    self.sendraw(386, ':§~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§')
    self.sendraw(386, ':End of /IRCOPS.')
