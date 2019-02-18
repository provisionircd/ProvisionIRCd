#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides usermodes +R, +Z, and +D to block private messages
"""

import ircd
import re

@ircd.Modules.user_modes('R', 0, 'Only users with a registered nickname can private message you') ### ('mode', 0, 1 or 2 for normal user, oper or server, 'Mode description')
@ircd.Modules.user_modes('Z', 0, 'Only users on a secure connection can private message you') ### ('mode', 0, 1 or 2 for normal user, oper or server, 'Mode description')
@ircd.Modules.user_modes('D', 0, 'No-one can private message you') ### ('mode', 0, 1 or 2 for normal user, oper or server, 'Mode description')
@ircd.Modules.events('privmsg')
def blockmsg_RZD(self, localServer, target, msg, module=None):
    if type(target).__name__ != 'User' or 'o' in self.modes: ### Opers can bypass.
        return True
    if 'R' in target.modes and 'r' not in self.modes:
        self.sendraw(477, '{} :You need a registered nickname to talk privately to this user'.format(target.nickname))
        return False
    if 'Z' in target.modes and 'z' not in self.modes:
        self.sendraw(477, '{} :You need to be on a secure connection to talk privately to this user'.format(target.nickname))
        return False
    if 'D' in target.modes:
        self.sendraw(477, '{} :This user does not accept private messages'.format(target.nickname))
        return False
    return True

@ircd.Modules.events('mode')
def setmode(*args): ### Params: self, localServer, recv, tmodes, param, commandQueue
    ### If +D is set, remove R and Z.
    self = args[0]
    if type(self).__name__ == 'Server':
        return
    localServer = args[1]
    recv = args[2]
    if recv[1] == self.nickname:
        pass
