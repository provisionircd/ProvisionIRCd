"""
/who command
"""

import ircd
import time

from handle.functions import match, logging

WHO_FLAGS = {
        'A': 'Account match',
        'a': 'Filters on away status',
        'h': 'Filters by hostname',
        'o': 'Show only IRC operators',
        'r': 'Filter by realname',
        's': 'Filter by server',
        'u': 'Filter by username/ident'
    }


@ircd.Modules.command
class Who(ircd.Command):
    """View information about users on the server.
    -
    Syntax: WHO <channel> [flags]
    -
    Wildcards are accepted in <channel>, so * matches all channels on the network.
    Flags are optional, and can be used to filter the output.
    They work similar to modes, + for positive and - for negative.
    -
     A <name>       = Match on account name.
     a              = Filter by away status.
     h <host>       = User has <host> in the hostname.
     o              = Show only IRC operators.
     r <realname>   = Filter by realname.
     s <server      = Filter by server.
     u <ident>      = Filter by username/ident.
    -
    """
    def __init__(self):
        self.command = 'who'
        self.support = [('WHO',)]

    def execute(self, client, recv):
        if int(time.time()) - client.signon < 10:
            client.flood_safe = True
        who = []
        if len(recv) == 1 or recv[1] == '*':
            mask = '*' ### Match all.
        else:
            mask = recv[1]
            ### This parameter contains a comma-separated list of query filters,
            ### such as nicknames, channel names or wild-card masks which are matched against all clients currently on-line.
        flags = ''
        if len(recv) > 2:
            flags = recv[2]
        params = '' if len(recv) < 3 else recv[3:]
        #logging.debug('WHO mask: {}'.format(mask))
        for user in self.ircd.users:
            continue_loop = 0
            chan = '*'
            if not [c for c in self.ircd.channels if client in c.users and user in c.users] and 'i' in client.modes and not 'o' in client.modes and user != client:
                continue
                #logging.debug('Checking mask: {}'.format(m))
            if (mask[0] not in self.ircd.chantypes+'*' or mask.lower() not in [c.name.lower() for c in self.ircd.channels]) and mask not in [user.nickname, '*']:
                continue

            if mask[0] in self.ircd.chantypes+'*':
                ### Mask is a channel.
                if mask.lower() not in [c.name.lower() for c in user.channels] and mask != '*':
                    continue
            paramcount = 0
            pos_match = []
            neg_match = []
            user_match = []
            action = ''
            for f in [f for f in flags if f in WHO_FLAGS or f in '+-']:
                if f in '+-':
                    action = f
                    continue
                if action == '+':
                    pos_match.append(f)
                else:
                    neg_match.append(f)

                if f in 'Ahrsu':
                    ## ['WHO', '#Home', '%cuhsnfdar']
                    if not params:
                        #logging.debug('Found arg flag but no params found')
                        continue
                    param = params[paramcount]
                    logging.debug('Param set: {}'.format(param))
                    paramcount += 1
                else:
                    param = None

                if f == 'A':
                    if (action == '+' and user.svid == param) or (action == '-' and not user.svid == param):
                        user_match.append(f)

                elif f == 'a':
                    if (action == '+' and user.away) or (action == '-' and not user.away):
                        user_match.append(f)

                elif f == 'h':
                    if (action == '+' and (match(param, user.fullmask()))) or (('o' in client.modes or user == client) and match(param, '{}!{}@{}'.format(user.nickname, user.ident, user.hostname))):
                        user_match.append(f)
                    if action == '-':
                        if not match(param, user.fullmask()) and (('o' in client.modes or user == client) and not match(param, '{}!{}@{}'.format(user.nickname, user.ident, user.hostname))):
                            user_match.append(f)
                        elif ('o' not in client.modes and user != client) and not match(param, user.fullmask()):
                            user_match.append(f)

                elif f == 'o':
                    if (action == '+' and 'o' in user.modes) or (action == '-' and not 'o' in user.modes):
                        user_match.append(f)

                elif f == 'r':
                    gcos_match = 0
                    for word in user.realname.split():
                        if match(param.lower(), word.lower()):
                            gcos_match = 1
                            break
                    if (action == '+' and gcos_match) or (action == '-' and not gcos_match):
                        user_match.append(f)

                elif f == 's':
                    if action == '+' and match(param, user.server.hostname) or (action == '-' and not match(param, user.server.hostname)):
                        user_match.append(f)

                elif f == 'u':
                    if (action == '+' and match(param, user.ident)) or (action == '-' and not match(param, user.ident)):
                        user_match.append(f)

            #logging.debug('User {} must match these flags: {}'.format(user.nickname, pos_match))
            #logging.debug('User {} must NOT match these flags: {}'.format(user.nickname, neg_match))
            #logging.debug('User {} has these matches: {}'.format(user.nickname, user_match))
            diff = set(pos_match+neg_match).difference(set(user_match))
            if diff or user in who:
                continue

            modes = ''
            who.append(user)
            if user.channels and chan == '*':
                channel = None
                ### Assign a channel.
                for c in user.channels:
                    if ('s' in c.modes or 'p' in c.modes) and (client not in c.users and 'o' not in client.modes):
                        continue
                    else:
                        channel = c

                    visible = 1
                    for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'visible_in_channel']:
                        try:
                            visible = callable[2](client, self.ircd, user, channel)
                        except Exception as ex:
                            logging.exception(ex)
                        if not visible:
                            break
                    if not visible and user != client:
                        channel = None
                        continue

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
            if 'o' in user.modes and 'H' not in user.modes:
                modes += '*'
            if 'H' in user.modes:
                modes += '?'
            if 'z' in user.modes:
                modes += 'z'
            if not user.server:
                continue
            hopcount = 0 if user.server == self.ircd else user.server.hopcount
            client.sendraw(self.RPL.WHOREPLY, '{} {} {} {} {} {}{} :{} {}'.format(chan, user.ident, user.cloakhost, self.ircd.hostname, user.nickname, away, modes, hopcount, user.realname))
        client.sendraw(self.RPL.ENDOFWHO, '{} :End of /WHO list.'.format(mask))
