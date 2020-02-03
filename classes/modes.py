# User mode class.

import re

from handle.functions import logging

class UserModeError(Exception):
    pass

class ChannelModeError(Exception):
    pass


class UserMode:
    ircd = None
    mode = ''
    req_flag = 0
    desc = ''
    support = ()
    server_supprt = 0
    registered = 0


    def validate(self):
        # Remove duplicate instances of the same class.
        for c in self.ircd.user_mode_class:
            if (type(c).__name__ == type(self).__name__ and c != self):
                c.unload()

        if not self.ircd:
            self.error("Missing server class reference")

        if not self.mode:
            self.error("Missing or invalid modebar")

        if self.mode in self.ircd.user_modes: # and self not in self.ircd.user_mode_class:
            self.error(f"Mode '{self.mode}' is already in use.")

        if not self.desc:
            self.error(f"Mode '{self.mode}' is missing a description.")

        if self.support:
            if self.support[0] in self.ircd.support:
                self.error("Support is conflicting with another module")
            if type(self.support) != list:
                self.error("Invalid SUPPORT type: must be a list containing one or more tuples")
            for s in [s for s in self.support if type(s) != tuple]:
                self.error("Invalid SUPPORT entry: {}\nMust be a tuple".format(s))


    def register(self):
        if not self.registered:
            self.validate()
            if self not in self.ircd.user_mode_class:
                self.ircd.user_mode_class.append(self)
            self.ircd.user_modes[self.mode] = (self.req_flag, self.desc)
            logging.debug('Usermode registered: {}'.format(self))
            #logging.debug('Permission flag: {}'.format(self.req_flag))
            #logging.debug('Description: {}'.format(self.desc))
            self.registered = 1


    def error(self, error):
        self.unload()
        raise UserModeError(error)


    def give_mode(self, user):
        if self.mode in user.modes:
            logging.error(f'Usermode {self.mode} is already active on user {user.nickname}')
            return 0

        if self.req_flag == 1 and 'o' not in user.modes:
            logging.error('User {} is not allowed to set this mode: {}'.format(self.req_flag))
            return 0

        user.modes += self.mode
        self.modebuf.append(self.mode)
        logging.debug('Usermode of {} is now: {}'.format(user.nickname, user.modes))
        return 1


    def take_mode(self, user):
        if self.mode not in user.modes:
            logging.debug('Failed attempt at removing non-active usermode "{}" from {}'.format(self.mode, user.nickname))
            return 0
        user.modes = user.modes.replace(self.mode, '')
        self.modebuf.append(self.mode)
        logging.debug('Usermode "{}" removed from {} usermodes. Now: {}'.format(self.mode, user.nickname, user.modes))
        return 1


    def unload(self):
        self.ircd.user_mode_class.remove(self)
        del self.ircd.user_modes[self.mode]
        logging.debug('{} successfully unhooked'.format(self))


    def __repr__(self):
        return f"<UserMode '{self.mode}'>"





class ChannelMode:
    ircd = None
    mode = ''
    req_flag = 3 # Default.
    desc = None
    type = None
    param_regex = None
    param_format = None
    param_help = None
    type = 3
    support = ()
    server_supprt = ()
    ### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode, 5 = "list" mode

    # Type 5 ("list modes, like +beI etc) requires some additional info.
    list_name = '' # The internal "name" of the list, i.e. channel.whitelist. Used in SJOIN to check if there's a duplicate entry, or to remove all entries.
    mode_prefix = '' # This is used in SJOIN to indicate that it is a list-entry.

    registered = 0

    def validate(self):
        # Remove duplicate instances of the same class.
        for c in self.ircd.channel_mode_class:
            if (type(c).__name__ == type(self).__name__ and c != self):
                c.unload()

        if not self.ircd:
            self.error("Missing server class reference")

        if not self.mode:
            self.error("Missing or invalid modebar")

        if self.mode in self.ircd.channel_modes:
            self.error(f"Channel mode '{self.mode}' is already in use.")

        if not self.desc:
            self.error(f"Channel mode '{self.mode}' is missing a description.")

        if self.type is None:
            self.error(f"Channel mode '{self.mode}' is missing a type.")

        if self.support:
            if self.support[0] in self.ircd.support:
                self.error("Support is conflicting with another module")
            if type(self.support) != list:
                self.error("Invalid SUPPORT type: must be a list containing one or more tuples")
            for s in [s for s in self.support if type(s) != tuple]:
                self.error("Invalid SUPPORT entry: {}\nMust be a tuple".format(s))


    def register(self):
        if not self.registered:
            self.validate()
            self.ircd.channel_mode_class.append(self)

            if self.type != 3 and self.param_help:
                t = (self.req_flag, self.desc, self.param_help)
            else:
                t = (self.req_flag, self.desc)

            self.ircd.channel_modes[self.type][self.mode] = t
            logging.debug('Channelmode registered: {}'.format(self))
            #logging.debug('Permission flag: {}'.format(self.req_flag))
            self.registered = 1


    def check(self, channel, action, param=None):
        param = self.fix_param(param)
        if action == '+':
            if self.type == 3 and self.mode in channel.modes:
                logging.debug('Mode "{}" is already set on {}'.format(self.mode, channel))
                return 0

            if self.type in [1,2] and not param:
                logging.debug('Missing required param for type {} mode: {}{}'.format(self.type, action, self.mode))
                return 0

            if self.type == 2 and channel in self.ircd.chan_params and self.mode in self.ircd.chan_params[channel]:
                if param == self.ircd.chan_params[channel][self.mode]:
                    logging.debug('Igoring identical param for {}{} {}'.format(action, self.mode, param))
                    return 0

        elif action == '-':
            if self.mode not in channel.modes:
                logging.debug('Mode not found on {}: {}'.format(channel, self.mode))
                return 0

        if param and self.param_format:
            have = param.split(':')
            need = self.param_format.split(':')
            if not have[-1]:
                logging.debug('Invalid param received for "{}": need to be in format: {}'.format(self.mode, self.param_format))
                return 0

            if len(have) != len(need):
                logging.debug('Invalid param count received for "{}": {} != {}'.format(self.mode, len(have), len(need)))
                return 0
            for n,h in zip(need, have):
                if n == "<int>" and not h.isdigit():
                    logging.debug('Invalid param received for "{}": "{}" must be an integer'.format(self.mode,h))
                    return 0
        return 1


    def pre_hook(self, user, channel, param, action=''):
        if type(user).__name__ == 'User': # Servers can set modes too.
            hook = 'local_chanmode' if user.server != self.ircd else 'remote_chanmode'
        else:
            hook = 'local_chanmode' if user == self.ircd else 'remote_chanmode'
        #logging.debug('Looking for pre_* hooks for {}'.format(self))
        for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'pre_'+hook]:
            try:
                #logging.debug('Calling {} with action {}'.format(callable, action))
                ok = callable[2](user, self.ircd, channel, self.modebuf, self.parambuf, action, self.mode, param)
                if not ok and ok is not None:
                    logging.debug('Further processing halted for {}{}{}'.format(action, self.mode, ' '+param if param else ''))
                    return 0
            except Exception as ex:
                logging.exception(ex)
        return 1


    def fix_param(self, param):
        #if self.param_regex and param:
        #    r = re.findall(self.param_regex, param)
        #    if r:
        #        param = r[0]
        #        logging.debug('Fixed param: {}'.format(param))
        return param


    def set_mode(self, user, channel, param=None):
        param = self.fix_param(param)
        process = self.pre_hook(user, channel, param, action='+')
        if not process and process is not None:
            # Assume the module handled everything correctly.
            logging.debug(f'Mode "{self.mode}" processing blocked by pre_hook(). We assume the module handled everything correctly.')
            return 0

        for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'modechar_add']:
            try:
                result = callable[2](self.ircd, self, channel, self.mode)
                if not result and result is not None:
                    logging.debug('Mode set denied by module: {}'.format(callable))
                    return 0
            except Exception as ex:
                logging.exception(ex)

        if self.type in [1,2] and param:
            if self.mode in self.ircd.core_chmodes or self.type == 2:
                logging.debug('Storing param of {}: {}'.format(self.mode, param))
                self.ircd.chan_params[channel][self.mode] = param

            elif self.mode not in self.ircd.chan_params[channel]:
                logging.debug('2 Storing param of {}: {}'.format(self.mode, param))
                self.ircd.chan_params[channel][self.mode] = param

        if param:
            self.parambuf.append(param)

        self.modebuf.append(self.mode)

        if self.mode not in channel.modes:
            channel.modes += self.mode
            logging.debug('Channel mode "{}" set on {} (param: {})'.format(self.mode, channel, self.ircd.chan_params[channel][self.mode]))
        else:
            logging.debug('Channel mode "{}" updated on {} (param: {})'.format(self.mode, channel, self.ircd.chan_params[channel][self.mode]))

        return 1


    def remove_mode(self, user, channel, param=None):
        # Module hooks.
        self.pre_hook(user, channel, param, action='-')

        # This should be handled by pre_* mode hooks
        for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'modechar_del']:
            try:
                result = callable[2](self.ircd, self, channel, self.mode)
                if not result and result is not None:
                    logging.debug('Mode remove denied by module: {}'.format(callable))
                    return 0
            except Exception as ex:
                logging.exception(ex)

        if self.mode in self.ircd.chan_params[channel]:
            logging.debug(f'Forgetting param for {self.mode}: {self.ircd.chan_params[channel][self.mode]}')
            del self.ircd.chan_params[channel][self.mode]

        if self.mode not in channel.modes:
            return 0


        channel.modes = channel.modes.replace(self.mode, '')
        self.modebuf.append(self.mode)
        if param:
            self.parambuf.append(param)

        logging.debug('Channel mode "{}" removed from {} (param: {})'.format(self.mode, channel, param))
        return 1


    def error(self, error):
        self.unload()
        raise ChannelModeError(error)


    def unload(self):
        self.ircd.channel_mode_class.remove(self)
        del self.ircd.channel_modes[self.type][self.mode]
        logging.debug('{} successfully unhooked'.format(self))


    def __repr__(self):
        return f"<ChannelMode '{self.mode}'>"
