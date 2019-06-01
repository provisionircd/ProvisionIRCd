#!/usr/bin/env python
# -*- coding: utf-8 -*-

import imp
import os
import sys
import importlib

import gc
gc.enable()

from handle.functions import _print, update_support, logging

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

def HookToCore(self, callables):
    try:
        ### Tuple: callables, channel_modes, user_modes, events, req_modes, req_flags, req_class, commands, params, support, hooks, module
        hooks = []
        channel_modes = callables[1]
        user_modes = callables[2]
        events = callables[3]
        commands = callables[7]
        module_hooks = callables[10]
        #print('HOOKS: {}'.format(hooks))
        module = callables[11]
        for callable in [callable for callable in commands if callable not in hooks]:
            hooks.append(callable)
            for cmd in [cmd for cmd in callable.commands if cmd not in self.commands]:
                params = 0
                req_modes = None
                req_flags = None
                req_modes = None
                req_class = 'User'
                if hasattr(callable, "params"):
                    params = callable.params
                if hasattr(callable, "req_modes"):
                    req_modes = callable.req_modes
                if hasattr(callable, "req_flags"):
                    req_flags = callable.req_flags
                if hasattr(callable, "req_class"):
                    req_class = callable.req_class
                info = (cmd, callable, params, req_modes, req_flags, req_class, module)
                self.commands.append(info) ### (cmd, callable, params, req_modes, req_flags, req_class, module)
                logging.info('Hooked command "{}" (params: {}, req_modes: {}, req_flags: {}, req_class: {}) to function {}'.format(cmd, params, req_modes, req_flags, req_class, callable))

        hooks = []
        for callable in [callable for callable in channel_modes if callable not in hooks]:
            hooks.append(callable)
            update_support(self)
            ### Tuple: ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
            for chmode in [chmode for chmode in callable.channel_modes if chmode[0] not in self.chmodes_string]:
                mode = chmode[0]
                type = chmode[1]
                level = chmode[2]
                desc = chmode[3]
                cls = None
                if len(chmode) > 4:
                    cls = chmode[4]
                prefix = None
                if len(chmode) > 5:
                    prefix = chmode[5]
                param_desc = None
                if len(chmode) > 6:
                    param_desc = chmode[6]
                if not str(level).isdigit():
                    logging.warning('Invalid mode-level for {} -- skipping'.format(chmode))
                    continue
                level = int(level)
                for m in mode:
                    if m in self.chstatus or m in self.chmodes_string:
                        ### Found conflicting channel mode. Skipping.
                        logging.error('Channel mode {} already exists.'.format(m))
                        continue
                    if cls and cls.lower() == 'user':
                        self.chstatus += m[0]
                        ### Adding prefix to core.
                        found_prefix = [p for p in self.chprefix if self.chprefix[p] == prefix]
                        if found_prefix:
                            continue
                        self.chprefix[m[0]] = prefix
                    ### Add mode to self.channel_modes
                    ### Index 0 beI, index 1 kLf, index 2 l, index 3 imnjprstzCNOQRTV
                    if str(type) in '0123':
                        self.channel_modes[type][m] = (level, desc) if not param_desc else (level, desc, param_desc)
                    if prefix:
                        current_prefix = ''
                        for entry in [entry for entry in self.support if len(entry.split('=')) > 1 and entry.split('=')[0] == 'PREFIX']:
                            current_prefix = entry
                            break
                        #print('New prefix found. Current prefix support: {}'.format(current_prefix))
                        ### Append new prefix at the end. ok back to watching HIMYM, again.

                    chmodes_string = ''
                    for t in self.channel_modes:
                        for n in self.channel_modes[t]:
                            chmodes_string += n
                        chmodes_string += ','
                    self.chmodes_string = chmodes_string[:-1]

                    #_print('Hooked channel mode {} (type: {}, prefix: {}) to core'.format(m, type, prefix), server=self)
                    #_print('Mode level: {}'.format(level), server=self)
                    #_print('Mode desc: {}'.format(desc), server=self)

        ### callables, channel_modes, user_modes, events, req_modes, req_flags, req_class, commands, params, module
        hooks = []
        for callable in [callable for callable in user_modes if callable not in hooks]:
            hooks.append(callable)
            for umode in [umode for umode in callable.user_modes if umode[0] not in self.user_modes]:
                ### ('mode', 0, 1 or 3 for normal user, oper or server, 'Mode description')
                mode = umode[0]
                level = umode[1]
                desc = umode[2]
                self.user_modes[mode] = (level, desc)
                logging.info('Hooked user mode {} to core (level: {}, desc: {})'.format(mode, level, desc))

        ### This does not really needed to be "hooked" here. Just loop over the callables to check if there's an event.
        ### callables, channel_modes, user_modes, events, req_modes, req_flags, req_class, commands, params, module
        hooks = []
        for callable in [callable for callable in events if callable not in hooks]:
            hooks.append(callable)
            for event in [event for event in callable.events]:
                #print('Event: {}'.format(event))
                info = (event, callable, module)
                if info not in self.events:
                    self.events.append(info)
                    #logging.info('Hooked event {} to core'.format(info))

        hooks = []
        for callable in [callable for callable in module_hooks if callable not in hooks]:
            hooks.append(callable)
            for h in [h for h in callable.hooks if h]:
                #print(callable)
                info = (h[0], h[1], callable, module)
                self.hooks.append(info)
                logging.info('Hooked {}'.format(info))

    except Exception as ex:
        logging.exception(ex)

def LoadModule(self, name, path, reload=False, module=None):
    #logging.debug('Name: {}'.format(name))
    #logging.debug('Path: {}'.format(path))
    #logging.debug('Reload: {}'.format(reload))
    #logging.debug('Module: {}'.format(module))
    package = name.replace('/', '.')
    #logging.debug('Package: {}'.format(package))
    try:
        with open(path) as mod:
            #module = imp.load_module(name, mod, path, ('.py', 'U', imp.PY_SOURCE))
            if reload:
                importlib.reload(module)
                logging.debug('Requesting reload from importlib')
            else:
                module = importlib.import_module(package)
            if hasattr(module, 'init'):
                try:
                    getattr(module, 'init')(self, reload=reload)
                except Exception as ex:
                    logging.exception(ex)
            callables = FindCallables(module)
            HookToCore(self, callables)
            self.modules[module] = callables
            name = module.__name__
            update_support(self)
            logging.info('Loaded: {}'.format(name))
    except Exception as ex:
        logging.exception(ex)
        UnloadModule(self, name)
        raise

def UnloadModule(self, name):
    try:
        for module in [module for module in list(self.modules) if module.__name__ == name]:
            m = module.__name__
            if m == name:
                if hasattr(module, 'unload'):
                    try:
                        getattr(module, 'unload')(self)
                    except Excption as ex:
                        logging.exception(ex)
                for function in [function for function in self.modules[module][0] if hasattr(function, 'commands')]:
                    for cmd in list(function.commands):
                        function.commands.remove(cmd)
                        params = 0
                        req_modes = None
                        req_flags = None
                        req_class = 'User'
                        if hasattr(function, "params"):
                            params = function.params
                        if hasattr(function, "req_modes"):
                            req_modes = function.req_modes
                        if hasattr(function, "req_flags"):
                            req_flags = function.req_flags
                        if hasattr(function, "req_class"):
                            req_class = function.req_class
                        info = (cmd, function, params, req_modes, req_flags, req_class, module)
                        try:
                            self.commands.remove(info)
                        except ValueError:
                            logging.error('Callable {} not found in commands list.'.format(cmd))

                for function in [function for function in self.modules[module][1] if hasattr(function, 'channel_modes')]:
                    for chmode in [m for m in list(function.channel_modes) if m[0] in self.chmodes_string]:
                        ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
                        #self.channel_modes[3][m] = (level, desc)
                        mode = chmode[0]
                        type = chmode[1]
                        level = chmode[2]
                        desc = chmode[3]
                        cls = None
                        if len(chmode) > 4:
                            cls = chmode[4]
                        prefix = None
                        if len(chmode) > 5:
                            prefix = chmode[5]
                        if str(cls).lower() == 'user':
                            self.chstatus = self.chstatus.replace(mode, '')
                            if prefix:
                                ### Remove prefix from core.
                                del self.chprefix[mode]
                        else:
                            if mode in self.channel_modes[type]:
                                del self.channel_modes[type][mode]
                            else:
                                ### This happens because Python "remembers" the modules' global variables on reload (including functions):
                                ### https://docs.python.org/3/library/importlib.html#importlib.reload
                                ### So FindCallables() will append new functions if the name differs.
                                logging.error('Mode {} from type {} not found in server channel_modes list: {} ({})'.format(mode, type, self.channel_modes[type], m))
                        update_support(self)
                for function in [function for function in self.modules[module][2] if hasattr(function, 'user_modes')]:
                    for umode in list(function.user_modes):
                        mode = umode[0]
                        del self.user_modes[mode]
                for function in [function for function in self.modules[module][3] if hasattr(function, 'events')]:
                    for event in list(function.events):
                        info = (event, function, module)
                        function.events.remove(event)
                        if info in self.events:
                            #logging.info('Removed event {}'.format(info))
                            self.events.remove(info)
                        else:
                            logging.error('Unable to remove event {}: not found in events list'.format(info))
                for function in [function for function in self.modules[module][10] if hasattr(function, 'hooks')]:
                    for h in list(function.hooks):
                        info = (h[0], h[1], function, module)
                        function.hooks.remove(h)
                        if info in self.hooks:
                            logging.info('Removed {}'.format(info))
                            self.hooks.remove(info)
                        else:
                            logging.error('Unable to remove hook {}: not found in events list'.format(info))

                ### Leftover events.
                for e in [e for e in list(self.events) if e[2] == module]:
                   logging.error('Event {} was not properly removed (or added double). Removing now.'.format(e))
                   self.events.remove(e)

                ### Leftover hooks.
                for h in [h for h in list(self.hooks) if h[2] == module]:
                   logging.error('Hook {} was not properly removed (or added double). Removing now.'.format(h))
                   self.hooks.remove(h)

                for function in [function for function in self.modules[module][4] if hasattr(function, 'req_modes')]:
                    for a in list(function.req_modes):
                        function.req_modes.remove(a)

                for function in [function for function in self.modules[module][4] if hasattr(function, 'req_flags')]:
                    for a in list(function.req_flags):
                        function.req_flags.remove(a)

                logging.info('Unloaded: {}'.format(m))
                return 1

    except Exception as ex:
        logging.exception(ex)
        return str(ex)

def FindCallables(module):
    itervalues = dict.values
    callables = []
    channel_modes = []
    user_modes = []
    events = []
    req_modes = []
    req_flags = []
    req_class = [] # Defaults to User class.
    commands = []
    params = [] # For commands.
    support = []
    hooks = []
    for i in itervalues(vars(module)):
        if callable(i):
            callables.append(i)
            if hasattr(i, 'channel_modes'):
                channel_modes.append(i)
            if hasattr(i, 'user_modes'):
                user_modes.append(i)
            if hasattr(i, 'events'):
                events.append(i)
            if hasattr(i, 'req_modes'):
                req_modes.append(i)
            if hasattr(i, 'req_flags'):
                req_flags.append(i)
            if hasattr(i, 'req_class'):
                req_class.append(i)
            if hasattr(i, 'commands'):
                commands.append(i)
            if hasattr(i, 'params'):
                params.append(i)
            if hasattr(i, 'support'):
                support.append(i)
            if hasattr(i, 'hooks'):
                hooks.append(i)
    info = callables, channel_modes, user_modes, events, req_modes, req_flags, req_class, commands, params, support, hooks, module
    return info

def commands(*command_list):
    def add_attribute(function):
        if not hasattr(function, "commands"):
            function.commands = []
        function.commands.extend(command_list)
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

def req_class(req_class):
    def add_attribute(function):
        if not hasattr(function, "req_class"):
            function.req_class = 'User' # Defaults to User class.
        function.req_class = req_class
        return function
    return add_attribute

def params(num):
    def add_attribute(function):
        if not hasattr(function, "params"):
            function.params = 0
        function.params = num
        return function
    return add_attribute

def support(*support):
    def add_attribute(function):
        if not hasattr(function, "support"):
            function.support = []
        function.support.extend(support)
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
            'welcome',
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
    '''
    def pre_chanmode(*h):
        d = inspect.stack()[0][3]
        def add(function):
            info = (function, d, *h)
            function.hooks = info
            return function
        return add
    '''
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
