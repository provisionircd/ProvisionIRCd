import importlib
import imp
import os
import sys

import handle.handleModules as Modules

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
os.chdir(dir_path)
os.chdir('..')
p = os.getcwd()

def cmd_RELOADMOD(self, localServer, recv):
    if len(recv) < 2:
        return self.sendraw(461, ':RELOADMOD Not enough parameters')
    if 'o' not in self.modes:
        return self.sendraw(481, ':Permission denied - You are not an IRC Operator')
    if not self.ocheck('o', 'reload'):
        return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
    modname = None
    found_module = None
    if '/' in recv[1]:
        rootpath = recv[1].split('/')[0]
        modname = recv[1].split('/')[1].split('.py')[0]
        try:
            modname = '/'.join(recv[1].split('/')[1:])
        except:
            pass
        # file = file.split('.py')[:1][0]
        path_string = '{}'.format(rootpath)
        for x in range(0, recv[1].count('/')):
            path_string += '.{}'.format(recv[1].split('/')[x+1])
        m = path_string
    else:
        m = recv[1]
    try:
        found_module = [module for module in localServer.modules if module.__name__ == modname]
        module = importlib.import_module(m)
        imp.reload(module)
        if modname:
            if found_module:
                module = found_module[0]
                ### First, unload.
                Modules.UnloadModule(localServer, modname)
                ### Then, load.
                Modules.LoadModule(localServer, modname, module.__file__)
            else:
                ### Module is not yet loaded. Check if it exists.
                path = '{}/{}.py'.format(p, path_string.replace('.', '/'))
                #path = p+'/'+rootpath+'/'+modname+'.py'
                Modules.LoadModule(localServer, modname, path)

            already_seen = []
            for m in list(localServer.commands):
                pass
                #if m[0] == 'modules':
                #    localServer.commands.remove(m)

            #for x in range(0, 10):
            #    print('-')
            for cmd in list(localServer.commands):
                if cmd[0] in already_seen:
                    #print('Found duplicate command: {}'.format(cmd[0]))
                    #localServer.commands.remove(cmd)
                    continue
                already_seen.append(cmd[0])
        jointhread = False
        if m == 'ircd':
            #localServer.commands = []
            #localServer.modules = {}
            try:

                self.send('NOTICE', '*** Requesting core reload; also reloading essential handles.', direct=True)
                cores = [
                    'classes.user',
                    'handle.handleLink',
                    'handle.handleConf',
                    'handle.handleModules',
                    'handle.functions',
                    'handle.handleSockets'
                    ]
                for c in cores:
                    module = importlib.import_module(c)
                    imp.reload(module)
                #current = localServer.datahandler
                #from handle.handleSockets import data_handler
                #localServer.datahandler = data_handler(localServer)
                #localServer.datahandler.start()
                #jointhread = True

            except Exception as ex:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
                print(e)
        self.send('NOTICE', '*** Module \'{}\' reloaded.'.format(recv[1].split('.py')[0]), direct=True)
        #if jointhread:
        #    current.running = False
        #    localServer.datahandler.join()

    except Exception as ex:
        #exc_type, exc_obj, exc_tb = sys.exc_info()
        #fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        #e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        #print(e)
        self.send('NOTICE', '*** Module \'{}\' failed to reload: {}'.format(recv[1].split('.py')[0], ex))

        ### Uncomment if you want to unload the module on fail.
        if found_module:
            #modname = recv[1].split('.py')[0]
            Modules.UnloadModule(localServer, modname)
