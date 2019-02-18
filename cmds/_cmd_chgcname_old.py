import sys
import os

def cmd_CHGCNAME(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            sourceServer = self
            self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
            ### Cut the recv to match original syntax. (there's now an extra :UID at the beginning.
            recv = recv[1:]
            override = True
        else:
            sourceServer = self.server

        if len(recv) < 3:
            self.sendraw(461, ':CHGCNAME Not enough parameters')
            return

        if 'o' not in self.modes:
            self.sendraw(481, ':Permission denied - You are not an IRC Operator')
            return

        name = recv[2]
        requested_prefix = name[0]

        channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), localServer.channels))
        if not channel:
            localServer.handle('NOTICE', '{} :That channel does not exist.'.format(self.uid))
            return

        channel = channel[0]

        original_prefix = channel.name[0]

        if requested_prefix != original_prefix:
            localServer.handle('NOTICE', '{} :Converting of channel type is not allowed.'.format(self.uid))
            return

        if name == channel.name:
            localServer.handle('NOTICE', '{} :Channel names are equal; nothing changed.'.format(self.uid))
            return

        if name.lower() != channel.name.lower():
            localServer.handle('NOTICE', '{} :Only case changing is allowed.'.format(self.uid))
            return

        localServer.handle('NOTICE', '{} :Channel {} successfully changed to {}'.format(self.uid, channel.name, name))

        msg = '*** {} ({}@{}) used CHGCNAME to change channel name {} to {}'.format(self.nickname, self.ident, self.hostname, channel.name, name)
        localServer.snotice('s', msg)

        channel.name = name

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        if not localServer.forked:
            print(e)
