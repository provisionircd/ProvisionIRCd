"""
provides usermodes +g and /accept command (callerid)
"""

import time

import ircd


class Umode_g(ircd.UserMode):
    def __init__(self):
        self.mode = 'g'
        self.desc = "Only users in your accept-list can message you"
        self.support = [('CALLERID',)]


@ircd.Modules.hooks.pre_usermsg()
def umode_g(self, ircd, user, msg):
    if not hasattr(user, 'caller_id_accept'):
        user.caller_id_accept = []
    if not hasattr(user, 'caller_id_queue'):
        user.caller_id_queue = []
    if 'g' in user.modes and 'o' not in self.modes:
        accept_lower = [x.lower() for x in user.caller_id_accept]
        if self.nickname.lower() not in accept_lower:
            self.sendraw(716, '{} :is in +g mode'.format(user.nickname))
            self.sendraw(717, '{} :has been informed of your request, awaiting reply'.format(user.nickname))
        if not hasattr(self, 'targnotify'):
            self.targnotify = {}
        if self.nickname.lower() not in accept_lower:
            if (user in self.targnotify and int(time.time()) - self.targnotify[user] > 60) or user not in self.targnotify:
                user.sendraw(718, '{} {}@{} :is messaging you, and you have umode +g.'.format(self.nickname, self.ident, self.cloakhost if 'x' in self.modes else self.hostname))
                self.targnotify[user] = int(time.time())
            if user.server == ircd:
                queue = (self.fullmask(), time.time() * 10, msg)
                user.caller_id_queue.append(queue)
                return 0
    return msg


@ircd.Modules.command
class Callerid(ircd.Command):
    """Manipulate caller-ID list.
    -
    Example: ACCEPT CoolGuy420  (Adds to list)
             ACCEPT -lamed00d   (Removes from list)
    To view your current list:
             ACCEPT *
    """

    def __init__(self):
        self.command = 'accept'
        self.params = 1

    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            client = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], self.ircd.users))[0]
            recv = recv[1:]
        sync = False
        if not hasattr(client, 'caller_id_accept'):
            client.caller_id_accept = []
        if not hasattr(client, 'caller_id_queue'):
            client.caller_id_queue = []
        if recv[1] == '*':
            for nick in client.caller_id_accept:
                client.sendraw(281, '{}'.format(nick))
            return client.sendraw(282, 'End of /ACCEPT list')

        valid = 'abcdefghijklmnopqrstuvwxyz0123456789`^-_[]{}|\\'
        for entry in recv[1].split(','):
            continueLoop = False
            action = ''
            if entry[0] == '-':
                action = '-'
                entry = entry[1:]
            for c in entry.lower():
                if c.lower() not in valid or entry[0].isdigit():
                    continueLoop = True
                    break
            if continueLoop:
                continue

            accept_lower = [x.lower() for x in client.caller_id_accept]
            if action != '-':
                if entry.lower() in accept_lower:
                    client.sendraw(457, '{} :does already exist on your ACCEPT list.'.format(entry))
                    continue
            if action == '-':
                if entry.lower() not in accept_lower:
                    client.sendraw(458, '{} :is not found on your ACCEPT list.'.format(entry))
                    continue
                match = list(filter(lambda a: a.lower() == entry.lower(), client.caller_id_accept))[0]
                client.caller_id_accept.remove(match)
                sync = True
                for user in [user for user in self.ircd.users if user.nickname.lower() == entry.lower()]:
                    del user.targnotify[client]
                continue
            client.caller_id_accept.append(entry)
            sync = True
            for q in [q for q in list(client.caller_id_queue) if q[0].split('!')[0].lower() == entry.lower()]:
                p = {'safe': True}
                prefix = ''
                timestamp = int(q[1] / 10)
                if 'server-time' in client.caplist:
                    prefix = '@time={}.{}Z '.format(time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(timestamp)), round(q[1] % 1000))
                raw_string = '{}:{} PRIVMSG {} :{}'.format(prefix, q[0], client.nickname, q[2])
                client._send(raw_string)
                client.caller_id_queue.remove(q)

        if sync:
            data = ':{} {}'.format(client.uid, ' '.join(recv))
            self.ircd.new_sync(self.ircd, client.server, data)


@ircd.Modules.hooks.server_link()
def callerid_eos(client, ircd, remote_server):
    if not client.socket:
        return
    for user in [user for user in ircd.users if hasattr(user, 'caller_id_accept')]:
        data = []
        for accept in user.caller_id_accept:
            data.append(accept)
        if data:
            remote_server._send(':{} ACCEPT {}'.format(user.uid, ','.join(data)))


def unload(ircd):
    for user in [user for user in ircd.users if hasattr(user, 'caller_id_queue')]:
        user.caller_id_queue = []
    for user in [user for user in ircd.users if hasattr(user, 'caller_id_accept')]:
        user.caller_id_accept = []
    for user in [user for user in ircd.users if hasattr(user, 'targnotify')]:
        user.targnotify = {}
