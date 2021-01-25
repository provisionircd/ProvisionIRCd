"""
provides usermodes +R, +Z, and +D to block private messages
"""

import ircd

'''
@ircd.Modules.umode_class
class mode_R(ircd.UserMode):
    def __init__(self, ircd):
        self.ircd = ircd
        self.mode = 'R'
        self.req_flag = 0
        self.desc = 'Only users with a registered nickname can private message you'
        self.register_mode()


@ircd.Modules.umode_class
class mode_Z(ircd.UserMode):
    def __init__(self, ircd):
        self.ircd = ircd
        self.mode = 'Z'
        self.req_flag = 0
        self.desc = 'Only users on a secure connection can private message you'
        self.register_mode()


@ircd.Modules.umode_class
class mode_D(ircd.UserMode):
    def __init__(self, ircd):
        self.ircd = ircd
        self.mode = 'D'
        self.req_flag = 0
        self.desc = 'No-one can private message you'
        self.register_mode()
'''


class Umode_R(ircd.UserMode):
    def __init__(self):
        self.mode = 'R'
        self.desc = 'Only users with a registered nickname can private message you'
        self.req_flag = 0


class Umode_Z(ircd.UserMode):
    def __init__(self):
        self.mode = 'Z'
        self.desc = 'Only users on a secure connection can private message you'
        self.req_flag = 0


class Umode_D(ircd.UserMode):
    def __init__(self):
        self.mode = 'D'
        self.desc = 'No-one can private message you'
        self.req_flag = 0


@ircd.Modules.hooks.pre_usermsg()
def blockmsg_RZD(self, ircd, target, msg, module=None):
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
