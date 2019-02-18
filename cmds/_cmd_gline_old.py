from cmds import cmd_kline
import importlib

def cmd_GLINE(self, localServer, recv):
    cmd = importlib.import_module('cmds.cmd_kline')
    getattr(cmd,'cmd_KLINE')(self,localServer,recv,g=True)