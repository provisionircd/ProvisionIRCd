#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides usermodes +R, +Z, and +D to block private messages
"""

import ircd

@ircd.Modules.user_modes('R', 0, 'Only users with a registered nickname can private message you') ### ('mode', 0, 1 or 2 for normal user, oper or server, 'Mode description')
@ircd.Modules.user_modes('Z', 0, 'Only users on a secure connection can private message you') ### ('mode', 0, 1 or 2 for normal user, oper or server, 'Mode description')
@ircd.Modules.user_modes('D', 0, 'No-one can private message you') ### ('mode', 0, 1 or 2 for normal user, oper or server, 'Mode description')
@ircd.Modules.hooks.pre_usermsg()
def blockmsg_RZD(self, localServer, target, msg, module=None):
    if 'o' in self.modes:
        return msg
    if 'R' in target.modes and 'r' not in self.modes:
        self.sendraw(477, '{} :You need a registered nickname to talk privately to this user'.format(target.nickname))
        return 0
    if 'Z' in target.modes and 'z' not in self.modes:
        self.sendraw(477, '{} :You need to be on a secure connection to talk privately to this user'.format(target.nickname))
        return 0
    if 'D' in target.modes:
        self.sendraw(477, '{} :This user does not accept private messages'.format(target.nickname))
        return 0
    return msg

@ircd.Modules.events('umode')
def setmode(self, localServer, modes): ### Params: self, localServer, recv, tmodes, param, commandQueue
    ### If +D is set, remove R and Z.
    pass
