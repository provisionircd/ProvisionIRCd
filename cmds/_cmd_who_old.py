import os
import sys

from handle.functions import _print

def cmd_WHO(self, localServer, recv):
    try:
        who, modes = [], ''
        if len(recv) == 1 or recv[1] == '*': ### Need testing lol happy birthday man, glasses and 2018 is your last poor year.
            for user in localServer.users:
                chanMatch = False
                if 'i' in user.modes:
                    for c in user.channels:
                        if c in self.channels or self.ocheck('o', 'override'):
                            #_print(c)
                            chanMatch = True
                            break
                    if not chanMatch and not self.ocheck('o', 'override'):
                        continue
                modes = ''
                if user in who:
                    continue
                who.append(user)
                if not user.channels:
                    chan = '*'
                else:
                    channel = None
                    ### Assign a channel.
                    for c in user.channels:
                        if ('s' in c.modes or 'p' in c.modes) and (self not in c.users and not self.ocheck('o', 'override')):
                            continue
                        else:
                            channel = c
                    if not channel:
                        continue
                    #channel = user.channels[0]
                    chan = channel.name
                    modes = ''.join([{'q': '~', 'a': '&', 'o': '@', 'h': '%', 'v': ''}[x] for x in channel.usermodes[user]])
                if 'x' in user.modes:
                    modes += 'x'
                if user.away:
                    away = 'G'
                else:
                    away = 'H'
                if 'r' in user.modes:
                    modes += 'r'
                if 'o' in user.modes:
                    modes += '*'
                if 'H' in user.modes:
                    modes += '?'
                if user.server == localServer or user.server.socket:
                    hopcount = 0
                else:
                    hopcount = 1
                self.sendraw(352, '{} {} {} {} {} {}{} :{} {}'.format(chan, user.ident, user.cloakhost, localServer.hostname, user.nickname, away, modes, hopcount, user.realname))
            self.sendraw(315, '* :End of /WHO list.')
        else:
            channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), self.server.channels))

            if not channel:
                self.sendraw(315,'{} :End of /WHO list.'.format(recv[1]))
                return

            channel = channel[0]
            for user in channel.users:
                if 'i' in user.modes and self not in channel.users and not self.ocheck('o', 'override'):
                    continue
                modes = ''
                modes = ''.join([{'q': '~', 'a': '&', 'o': '@', 'h': '%', 'v': '+'}[x] for x in channel.usermodes[user]])
                if 'x' in user.modes:
                    modes += 'x'
                if user.away:
                    away = 'G'
                else:
                    away = 'H'
                if 'r' in user.modes:
                    modes += 'r'
                if 'H' in user.modes:
                    modes += '?'
                if 'o' in user.modes:
                    modes += '*'
                if user.server == localServer or user.server.socket:
                    hopcount = 0
                else:
                    hopcount = 1
                self.sendraw(352, '{} {} {} {} {} {}{} :{} {}'.format(channel.name, user.ident, user.cloakhost, localServer.hostname, user.nickname, away, modes, hopcount, user.realname))
            self.sendraw(315, '{} :End of /WHO list.'.format(channel.name))
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj)
        #print(e)