# Command class.

from handle.functions import logging

from classes.rpl import RPL, ERR

class CommandError(Exception):
    pass

class Command:
    ircd = None
    command = []
    params = 0
    req_modes = ''
    req_flags = None
    req_class = 'User'
    support = ()
    cap = []
    server_support = 0
    help = None
    RPL, ERR = RPL, ERR
    registered = 0


    def validate(self):
        # Remove duplicate instances of the same class.
        for c in self.ircd.command_class:
            if (type(c).__name__ == type(self).__name__ and c != self):
                c.unload()

        if not self.ircd:
            self.error("Missing server class reference")

        if not self.command:
            self.error("Missing command trigger")

        if type(self.command) != list:
            pass

        exists = 0
        for c in self.ircd.command_class:
            if [m for m in list(c.command) if m in self.command]:
                #logging.debug('Apparently, {} is equal to {}'.format(c.command, self.command))
                self.error("Command {} already exists".format(m))
                break

        if self.support:
            if self.support[0] in self.ircd.support:
                self.error("Support is conflicting with another module")
            if type(self.support) != list:
                self.error("Invalid SUPPORT type: must be a list containing one or more tuples")
            for s in [s for s in self.support if type(s) != tuple]:
                self.error("Invalid SUPPORT entry: {} must be a tuple".format(s))

        if self.cap:
            if type(self.cap) == str:
                self.cap = [self.cap]
            self.ircd.caps.extend(self.cap)


        #in_use = [cmd for cmd in self.ircd.commands if cmd[0].upper() == self.command]
        #if in_use:
        #    self.error(f'Command "{self.command}" already in use by: {in_use[0]}')

        if self.req_flags and 'o' not in self.req_modes:
            self.req_modes += 'o'


    def error(self, error):
        self.unload()
        raise CommandError(error)


    def check(self, client, recv):
        cmd = recv[0].upper()
        if type(client).__name__ != self.req_class and self.req_class == 'Server':
            client.sendraw(ERR.SERVERONLY, ':{} is a server only command'.format(cmd))
            return 0
        received_params = len(recv) - 1
        if received_params < self.params:
            client.sendraw(ERR.NEEDMOREPARAMS, ':{} Not enough parameters. Required: {}'.format(cmd, self.params))
            return 0

        if self.req_modes and type(client).__name__ != 'Server':
            req_modes = ' '.join(self.req_modes)
            if 'o' in req_modes and 'o' not in client.modes:
                client.sendraw(ERR.NOPRIVILEGES, ':Permission denied - You are not an IRC Operator')
                return 0

            forbid = set(req_modes).difference(set(client.modes))
            if forbid:
                client.sendraw(ERR.NOPRIVILEGES, ':Permission denied - Required mode not set')
                return 0

            if self.req_flags:
                forbid = 1
                if '|' in self.req_flags:
                    if list(filter(lambda f: f in client.operflags, self.req_flags.split('|'))):
                        forbid = False
                        logging.debug('You have one of the required flags. Allowing command.')
                else:
                    forbid = set([self.req_flags]).difference(set(client.operflags))
                if forbid:
                    client.sendraw(ERR.NOPRIVILEGES, ':Permission denied - You do not have the correct IRC Operator privileges')
                    return 0
        return 1


    def register(self, **kwargs):
        if not self.registered:
            if type(self.command) == str:
                self.command = [self.command.upper()]
            else:
                self.command = [x.upper() for x in self.command]
            self.help = self.__doc__
            self.validate()

            self.ircd.command_class.append(self)
            logging.debug('Command registered: {}'.format(self))
            self.registered = 1


    def add_support(self):
        # Add support data.
        if not self.support:
            return


    def unload(self):
        if self in self.ircd.command_class:
            self.ircd.command_class.remove(self)

        if self.support and self.support[0] in self.ircd.support:
            logging.debug('Removed support data')
            del self.ircd.support[self.support[0]]
        logging.debug('{} successfully unhooked'.format(self))


    def __repr__(self):
        return f"<Command '{self.command}'>"
