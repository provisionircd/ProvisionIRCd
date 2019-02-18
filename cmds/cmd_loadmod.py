import importlib, imp
import os

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
os.chdir(dir_path)
os.chdir('..')
p = [os.getcwd()]

def cmd_LOADMOD(self, localServer, recv):
    if len(recv) < 2:
        self.sendraw(461, ':LOADMOD Not enough parameters')
        return
    if 'o' not in self.modes:
        self.sendraw(481,':Permission denied - You are not an IRC Operator')
        return
    if not self.ocheck('o','reload'):
        self.sendraw(481,':Permission denied - You are not an IRC Operator')
        return
    modname = recv[1]
    m = '{}/{}'.format(''.join(p),recv[1])
    try:
        try:
            fp, pathname, description = imp.find_module(m,p)
        except Exception as ex:
            self.send('NOTICE','*** {}'.format(ex))
            return
        imp.load_module(m, fp, pathname, description)
        try:
            getattr(m,'init')(self)
        except:
            pass
        self.send('NOTICE','*** Module \'{}\' loaded.'.format(modname))
    except Exception as ex:
        self.send('NOTICE','*** Module \'{}\' failed to load: {}'.format(modname,ex))