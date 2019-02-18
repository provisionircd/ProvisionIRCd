from cmds import cmd_zline
import importlib

def cmd_GZLINE(self, localServer, recv):
    cmd = importlib.import_module('cmds.cmd_zline')
    getattr(cmd,'cmd_ZLINE')(self,localServer,recv,g=True)