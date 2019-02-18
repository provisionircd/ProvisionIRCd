#!/usr/bin/env python
# -*- coding: utf-8 -*-

import imp
import os
import sys

import gc
gc.enable()

from handle.functions import _print, update_support

def ListModules(self):
    modules = {}
    for file in [file for file in os.listdir(self.modules_dir) if not file.startswith('__') and file.startswith('m_')]:
        path = os.path.join(self.modules_dir, file)
        file = file.split('.py')[:1][0]
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
            file = '{}/{}'.format(folder, file.split('.py')[:1][0])
            modules[file] = path
            folder = ''
    return modules

def LoadModules(self):
    #_print('LoadModules() called', server=self)
    ### Loading modules from config file
    mods = ListModules(self)
    for m in [m for m in self.conf['modules'] if m in mods]:
        LoadModule(self, m, mods[m])
    update_support(self)

def HookToCore(self, callables):
    try:
        ### Tuple: callables, channel_modes, user_modes, events, req_modes, req_flags, req_class, commands, params, support, module
        hooks = []
        channel_modes = callables[1]
        user_modes = callables[2]
        events = callables[3]
        commands = callables[7]
        module = callables[10]

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
                #print('Adding cmd: {}'.format(info))
                self.commands.append(info) ### (cmd, callable, params, req_modes, req_flags, req_class, module)
                #_print('Hooked command "{}" (params: {}, req_modes: {}, req_flags: {}, req_class: {}) to function {}'.format(cmd, params, req_modes, req_flags, req_class, callable), server=self)

        hooks = []
        for callable in [callable for callable in channel_modes if callable not in hooks]:
            hooks.append(callable)
            update_support(self)
            ### Tuple: ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
            for chmode in [chmode for chmode in callable.channel_modes if chmode[0] not in self.channel_modes]:
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
                    _print('Invalid mode-level for {} -- skipping'.format(chmode), server=self)
                    continue
                level = int(level)
                for m in mode:
                    if (cls and cls.lower() == 'user' and m in self.chstatus) or (not type and m in self.chmodes):
                        ### Found conflicting channel user-mode. Skipping.
                        _print('Channel (user)-mode {} already exists.'.format(m), server=self)
                        continue
                    if cls and cls.lower() == 'user':
                        #chstatus = ''.join(self.chmodes.split(',')[4])
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
                #_print('Hooked user mode {} to core (level: {}, desc: {})'.format(mode, level, desc), server=self)

        ### This does not really needed to be "hooked" here. Just loop over the callables to check if there's an event.
        ### callables, channel_modes, user_modes, events, req_modes, req_flags, req_class, commands, params, module
        hooks = []
        for callable in [callable for callable in events if callable not in hooks]:
            hooks.append(callable)
            for event in [event for event in callable.events]:
                info = (event, callable, module)
                self.events.append(info)
                #_print('Hooked event {} to core'.format(info), server=self)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=self)

def LoadModule(self, name, path):
    try:
        with open(path) as mod:
            module = imp.load_module(name, mod, path, ('.py', 'U', imp.PY_SOURCE))
            if hasattr(module, 'init'):
                getattr(module, 'init')(self)
            callables = FindCallables(module)
            HookToCore(self, callables)
            self.modules[module] = callables
            name = module.__name__
            #_print('Loaded {}'.format(name), server=self)
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=self)
        e = 'Unable to load module {}: {}'.format(name, exc_obj)
        _print(e, server=self)

def UnloadModule(self, name):
    try:
        for module in dict(self.modules):
            m = module.__name__
            if m == name:
                if hasattr(module, 'unload'):
                    getattr(module, 'unload')(self)
                #for index in range(0, len(self.modules[module])):
                #    print('{} index {}: {}'.format(name, index, self.modules[module][index]))
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
                        #print('Removing cmd: {}'.format(info))
                        try:
                            self.commands.remove(info)
                        except ValueError:
                            _print('REMOVE ERROR: Callable {} not found in commands list.'.format(cmd), server=self)

                for function in [function for function in self.modules[module][1] if hasattr(function, 'channel_modes')]:
                    for chmode in list(function.channel_modes):
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
                                _print('REMOVE ERROR: Mode {} from type {} not found in server channel_modes list.'.format(mode, type), server=self)
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
                            self.events.remove(info)
                        else:
                            _print('REMOVE ERROR: Unable to remove event {}: not found in events list'.format(info), server=self)

                ### Leftover events.
                for e in [e for e in list(self.events) if e[2] == module]:
                   _print('REMOVE ERROR: Event {} was not properly removed (or added double). Removing now.'.format(e), server=self)
                   self.events.remove(e)

                for function in [function for function in self.modules[module][4] if hasattr(function, 'req_modes')]:
                    for a in list(function.req_modes):
                        function.req_modes.remove(a)

                for function in [function for function in self.modules[module][4] if hasattr(function, 'req_flags')]:
                    for a in list(function.req_flags):
                        function.req_flags.remove(a)

                del self.modules[module]
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=self)

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
    info = callables, channel_modes, user_modes, events, req_modes, req_flags, req_class, commands, params, support, module
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

def events(*command_list):
    def add_attribute(function):
        if not hasattr(function, "events"):
            function.events = []
        function.events.extend(command_list)
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
