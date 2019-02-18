#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import re
import socket
import importlib

upd_url = 'https://provisionweb.org/provisionircd/update/'

def upd_file(file=None):
    import urllib.request
    response = urllib.request.urlopen(upd_url+file).read().decode('utf-8')
    return response

def updater(self, localServer):
    update_data = {}
    upd_temp = localServer.rootdir
    if not os.path.exists(upd_temp):
            os.makedirs(upd_temp)
    try:
        remote_version = int(upd_file('version'))
        current_version = int(localServer.versionnumber.replace('.', ''))
        remote_files = []
        result = False
        if remote_version > current_version:
            result = remote_version
            file_list = re.findall(r'href=[\'"]?([^\'" >]+)', upd_file('src/'))[5:]
            for target in file_list:
                if target.startswith('.') or target,startswith('__') or target.endswith('__'):
                    continue

                write_to = upd_temp+'/'+target
                #print('Downloading: {} to {}'.format(target, write_to))
                if target.endswith('/'):
                    if not os.path.exists(upd_temp+'/'+target):
                        print('Creating non-existent directory {}'.format(upd_temp+'/'+target))
                        os.makedirs(upd_temp+'/'+target)
                    folder_file_list = re.findall(r'href=[\'"]?([^\'" >]+)', upd_file('src/'+target))[5:]
                    for file in folder_file_list:
                        raw_file = target+file.rsplit('.')[0]
                        if raw_file not in remote_files:
                            remote_files.append(raw_file)
                        write_to = upd_temp+'/'+target+file
                        content = upd_file('src/'+target+file)
                        with open(write_to, 'w+') as f:
                            f.write(content)
                        continue
                else:
                    if target not in remote_files:
                        remote_files.append(target)
                    content = upd_file('src/'+target)
                    with open(write_to, 'w+') as f:
                        f.write(content)

            ### Creating local filelist.
            local_file_list, local_dirs = [], []
            local_dirs.append(localServer.rootdir+'/handle')
            local_dirs.append(localServer.rootdir+'/classes')
            local_dirs.append(localServer.rootdir+'/cmds')
            self.handle('reloadmod', 'ircd')
            for dir in local_dirs:
                for file in os.listdir(dir):
                    path = dir+'/'+file
                    file = path.replace(localServer.rootdir, '')
                    #print('Local path: {}'.format(path))
                    #print('Local file: {}'.format(file))
                    reload_file = file[1:].rsplit('.')[0]
                    if reload_file not in remote_files and not reload_file.startswith('/') and '__' not in reload_file:
                        print('File {} is not needed anymore. Let\'s remove it.'.format(reload_file))
                        ### Remove file here.
                        try:
                            module = importlib.import_module(reload_file.split('/')[0]+'.'+reload_file.split('/')[1])
                            print('Removing {}'.format(path))
                            os.remove(path)
                            del(module)
                        except Exception as ex:
                            print(ex)
                        continue
                    if reload_file.endswith('/'):
                        continue
                    print('Reloading file: {}'.format(reload_file))
                    p = {'silent': True, 'override': True}
                    self.handle('reloadmod', reload_file, params=p)

        return result

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        print(e)

def _print(txt):
    Logger.write(txt)
    print(txt)

def cmd_UPDATE(self, localServer, recv):
    return
    try:
        if 'o' not in self.modes:
            self.sendraw(481, ':Permission denied - You are not an IRC Operator')
            return

        if not self.ocheck('o', 'update'):
            self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            return
        result = updater(self, localServer)
        if result:
            localServer.snotice('s', '*** Server has been updated to {}! A restart might not be necessary, but is still HIGHLY recommended!'.format(result))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e)
