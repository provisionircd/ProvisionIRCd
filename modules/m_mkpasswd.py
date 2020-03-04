"""
/mkpasswd command
"""

import ircd
try:
    import bcrypt
except:
    pass


class Mkpasswd(ircd.Command):
    """"
    Generated a bcrypt password from a string.
    Example: /MKPASSWD hunter2
    """
    def __init__(self):
        self.command = 'mkpasswd'
        self.req_modes = 'o'
        self.params = 1


    def execute(self, client, recv):
        try:
            bcrypt
        except:
            return self.ircd.notice(client, '*** bcrypt package could not be found. Please install bcrypt with pip and rehash.')

        if len(recv[1]) < 6:
            return self.ircd.notice(client, '*** Given password is too short.')

        client.flood_penalty += 10000
        hashed = bcrypt.hashpw(recv[1].encode('utf-8'), bcrypt.gensalt(10)).decode('utf-8')
        self.ircd.notice(client, '*** Hashed ({}): {}'.format(recv[1], hashed))
