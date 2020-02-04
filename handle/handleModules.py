import os
import sys
import importlib

from classes.modes import UserMode, ChannelMode
from classes.commands import Command
from handle.functions import update_support, logging

def ListModules(self):
    modules = {}

    for file in [file for file in os.listdir(self.modules_dir) if not file.startswith('__') and file.startswith('m_')]:
        path = os.path.join(self.modules_dir, file)
        file = 'modules.'+file.split('.py')[:1][0]
        modules[file] = path

    import ntpath
    bla = os.walk(self.modules_dir)
    for x in bla:
        fullpath = x[0]
        dir = ntpath.basename(x[0])
        if not dir or dir.startswith('__'):
            continue
        for file in [file for file in os.listdir(fullpath) if not file.startswith('__') and file.startswith('m_')]:
            path = os.path.join(fullpath, file)
            folder = os.path.basename(os.path.dirname(path))
            file = 'modules.{}.{}'.format(folder, file.split('.py')[:1][0])
            modules[file] = path
            folder = ''
    return modules


def LoadModules(self):
    mods = ListModules(self)
    for m in [m for m in self.conf['modules'] if m in mods]:
        LoadModule(self, m, mods[m])
    update_support(self)


def HookToCore(self, callables, reload=False):
    try:
        ### Tuple: callables, commands, user_modes, channel_modes, hooks, support, api, module
        hooks = []
        commands = callables[0]
        user_modes = callables[1]
        channel_modes = callables[2]
        module_hooks = callables[3]
        support = callables[4]
        api = callables[5]
        module = callables[6]

        for c in commands+user_modes+channel_modes:
            m = c()
            m.module = module
            m.ircd = self
            m.register()

        if hasattr(module, 'init'):
            module.init(self)

        for callable in [callable for callable in api if callable not in hooks]:
            hooks.append(callable)
            for a in [a for a in callable.api if a not in self.api]:
                api_cmd = a[0]
                api_host = None if len(a) < 2 else a[1]
                api_password = None if len(a) < 3 else a[2]
                info = (api_cmd, callable, api_host, api_password, module)
                self.api.append(info) ### (cmd, callable, params, req_modes, req_flags, req_class, module)
                #logging.info('Hooked API "{}" (host: {}, password: {}) to function {}'.format(api_cmd, api_host, api_password, callable))

        hooks = []
        for callable in [callable for callable in module_hooks if callable not in hooks]:
            hooks.append(callable)
            for h in [h for h in callable.hooks if h]:
                #print(callable)
                info = (h[0], h[1], callable, module)
                self.hooks.append(info)
                #logging.info('Hooked {}'.format(info))

        update_support(self)

    except Exception as ex:
        logging.exception(ex)
        return ex


def LoadModule(self, name, path, reload=False, module=None):
    package = name.replace('/', '.')
    try:
        error = 0
        with open(path) as mod:
            if reload:
                module = importlib.reload(module)
                logging.debug('Requesting reload from importlib')
            else:
                module = importlib.import_module(package)
                importlib.reload(module)
            if not module.__doc__:
                logging.info('Invalid module.')
                return 'Invalid module'
            callables = FindCallables(self, module)
            hook_fail = HookToCore(self, callables, reload=reload) ### If None is returned, assume success.
            if hook_fail:
                logging.debug('Hook failed: {}'.format(hook_fail))
                UnloadModule(self, name)

                return hook_fail
            self.modules[module] = callables
            name = module.__name__
            update_support(self)
            logging.info('Loaded: {}'.format(name))
    except FileNotFoundError as ex:
        return ex
    except Exception as ex:
        logging.exception(ex)
        UnloadModule(self, name)
        #if not reload:
        if not self.running:
            print('Server could not be started due to an error in {}: {}'.format(name, ex))
            sys.exit()
        raise
        return ex


def UnloadModule(self, name):
    try:
        for module in [module for module in list(self.modules) if module.__name__ == name]:
            ### Tuple: commands, user_modes, channel_modes, hooks, support, api, module
            m = module.__name__
            if m == name:
                '''
                logging.debug('Module info:')
                info = ''
                for count,mod in enumerate(self.modules[module]):
                    logging.debug(count)
                    if count == 0:
                        info = 'commands'
                    if count == 1:
                        info = 'user_modes'
                    if count == 2:
                        info = 'channel_modes'
                    if count == 3:
                        info = 'hooks'
                    if count == 4:
                        info = 'support'
                    if count == 5:
                        info = 'api'
                    if count == 6:
                        info = 'module'
                    print(info)
                    logging.debug(self.modules[module][count])
                    logging.debug('-')
                '''
                core_classes = self.user_mode_class + self.channel_mode_class + self.command_class
                for m in [m for m in core_classes if m.module == module]:
                    print('unload 1')
                    m.unload()

                if hasattr(module, 'unload'):
                    try:
                        module.unload(self)
                    except Excption as ex:
                        logging.exception(ex)

                for function in [function for function in self.modules[module][3] if hasattr(function, 'hooks')]:
                    for h in list(function.hooks):
                        info = (h[0], h[1], function, module)
                        function.hooks.remove(h)
                        if info in self.hooks:
                            self.hooks.remove(info)
                            #logging.info('Unhooked {}'.format(info))
                        else:
                            logging.error('Unable to remove hook {}: not found in hooks list'.format(info))

                for function in [function for function in self.modules[module][5] if hasattr(function, 'api')]:
                    for a in list(function.api):
                        function.api.remove(a)
                        api_cmd = a[0]
                        api_host = None if len(a) < 2 else a[1]
                        api_password = None if len(a) < 3 else a[2]
                        info = (api_cmd, function, api_host, api_password, module)
                        try:
                            self.api.remove(info)
                        except ValueError:
                            logging.error('Callable {} not found in API list.'.format(a))

                ### Leftover hooks.
                for h in [h for h in list(self.hooks) if h[2] == module]:
                   logging.error('Hook {} was not properly removed (or added double). Removing now.'.format(h))
                   self.hooks.remove(h)

                del self.modules[module]

                logging.info('Unloaded: {}'.format(m))
                update_support(self)
                return 1

    except Exception as ex:
        logging.exception(ex)
        return str(ex)

def FindCallables(self, module):
    itervalues = dict.values
    commands = []
    user_modes = []
    channel_modes = []
    hooks = []
    api = []
    support = []

    for i in itervalues(vars(module)):
        if callable(i):
            if hasattr(i, 'mro') and i.mro()[1].__name__ == "Command":
                commands.append(i)

            if hasattr(i, 'mro') and i.mro()[1].__name__ == "UserMode":
                user_modes.append(i)

            if hasattr(i, 'mro') and i.mro()[1].__name__ == "ChannelMode":
                channel_modes.append(i)

            if hasattr(i, 'hooks'):
                hooks.append(i)

            if hasattr(i, 'support'):
                support.append(i)

            if hasattr(i, 'api'):
                api.append(i)

    info = commands, user_modes, channel_modes, hooks, support, api, module
    return info


def support(*support):
    def add_attribute(function):
        if not hasattr(function, "support"):
            function.support = []
        function.support.extend(support)
        return function
    return add_attribute

def user_mode(cls):
    class umode(UserMode):
        pass
    return cls

def channel_mode(cls):
    class umode(ChannelMode):
        pass
    return cls

def command(cls):
    class umode(Command):
        pass
    return cls

def api(*args):
    ### ('command', host=None, password=None)
    def add_attribute(function):
        if not hasattr(function, "api"):
            function.api = []
        function.api.append(args)
        return function
    return add_attribute







def params(num):
    def add_attribute(function):
        if not hasattr(function, "params"):
            function.params = 0
        function.params = num
        return function
    return add_attribute

def commands(*command_list):
    def add_attribute(function):
        if not hasattr(function, "commands"):
            function.commands = []
        function.commands.extend(command_list)
        return function
    return add_attribute

def req_class(req_class):
    def add_attribute(function):
        if not hasattr(function, "req_class"):
            function.req_class = 'User' # Defaults to User class.
        function.req_class = req_class
        return function
    return add_attribute

def req_modes(*req_modes):
    ### Required modes for command.
    def add_attribute(function):
        if not hasattr(function, "req_modes"):
            function.req_modes = []
        function.req_modes.extend(req_modes)
        return function
    return add_attribute

def req_flags(*req_flags):
    ### Required flags for command.
    def add_attribute(function):
        if not hasattr(function, "req_flags"):
            function.req_flags = []
        function.req_flags.extend(req_flags)
        return function
    return add_attribute

def channel_modes(*args):
    ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
    def add_attribute(function):
        if not hasattr(function, "channel_modes"):
            function.channel_modes = []
        function.channel_modes.append(args)
        return function
    return add_attribute

def user_modes(*args):
    def add_attribute(function):
        if not hasattr(function, "user_modes"):
            function.user_modes = []
        function.user_modes.append(args)
        return function
    return add_attribute

def events(*command_list):
    def add_attribute(function):
        if not hasattr(function, "events"):
            function.events = []
        function.events.extend(command_list)
        return function
    return add_attribute







import inspect
all_hooks = [
            'pre_command',
            'pre_local_join',
            'local_join',
            'pre_remote_join', ### Why? Not like you can block a remote join. Oh, for m_delayjoin to hide joins.
            'remote_join',
            'channel_create',
            'pre_local_part',
            'local_part',
            'remote_part',
            'pre_local_kick',
            'local_kick',
            'remote_kick',
            'channel_destroy',
            'pre_local_nickchange',
            'local_nickchange',
            'remote_nickchange',
            'pre_local_quit',
            'local_quit',
            'remote_quit',
            'pre_chanmsg',
            'chanmsg',
            'pre_usermsg',
            'usermsg',
            'pre_channotice',
            'channotice',
            'pre_usernotice',
            'usernotice',
            'pre_local_chanmode',
            'local_chanmode',
            'pre_remote_chanmode',
            'remote_chanmode',
            'modechar_add',
            'modechar_del',
            'pre_local_connect',
            'local_connect',
            'remote_connect',
            'visible_in_channel',
            'channel_lists_sync',
            'welcome',
            'new_connection',
            'server_link',
            'rpl',
            'loop',
            ]

class hooks:
    def test_hook(*h):
        d = inspect.stack()[0][3]
        def add(function):
            if not hasattr(function, "hooks"):
                function.hooks = []
            function.hooks.extend((d, h))
            return function
        return add

    for hook in all_hooks:
        exec("""def {}(*h):
            d = inspect.stack()[0][3]
            if h:
                h = h[0]
            def add(function):
                if not hasattr(function, "hooks"):
                    function.hooks = []
                function.hooks.extend([(d, h)])
                return function
            return add""".format(hook))
