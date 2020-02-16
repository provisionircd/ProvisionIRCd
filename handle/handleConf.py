import json
import sys
import os
import threading
import importlib
import collections
import time
import ssl
import gc
import ircd
gc.enable()

# >>> from pathlib import Path
# >>> Path('A').resolve()
# PosixPath('/tmp/example/notexist')


bc = 0
try:
    import bcrypt
    bc = 1
except ImportError:
    #print("Could not import 'bcrypt' module. You can install it with pip")
    #sys.exit()
    pass

print('Bcrypt support: {}'.format(bc))

import handle.handleModules as Modules
from handle.functions import _print, logging

COMMENT_PREFIX = ('#', ';', '//')
MULTILINE_START = '/*'
MULTILINE_END = '*/'

LONG_STRING = '"""'

def json_preprocess(lines):
    try:
        standard_json = ""
        is_multiline = False
        keep_trail_space = 0

        for line in lines:
            line = line.strip()

            # 0 if there is no trailing space
            keep_trail_space = int(line.endswith(" "))

            if len(line) == 0:
                continue

            if line.startswith(COMMENT_PREFIX):
                continue

            if line.startswith(MULTILINE_START):
                is_multiline = True

            if is_multiline:
                if line.endswith(MULTILINE_END):
                    is_multiline = False
                continue

            if LONG_STRING in line:
                line = line.replace(LONG_STRING, '"')

            standard_json += line + " " * keep_trail_space

        standard_json = standard_json.replace(",]", "]")
        standard_json = standard_json.replace(",}", "}")

        return standard_json
    except Exception as ex:
        print(ex)

errors = []
confOpers = []
confLinks = []
#conffile = ''

def conferr(msg, noConf=False, err_conf=''):
    global errors
    if not noConf:
        msg = '{}{}'.format(err_conf+': ' if err_conf else '', msg)
    errors.append(msg)

def checkConf(localServer, user, confdir, conffile, rehash=False):
    global errors
    global confOpers
    global confLinks
    confOpers = []
    confLinks = []
    errors = []
    main_conf = conffile
    if rehash:
        user.sendraw(382, '{} :Rehashing'.format(confdir+conffile))
    try:
        with open(confdir+conffile) as j:
            j = j.read().split('\n')
            j = json_preprocess(j)
            tempconf = json.loads(j, object_pairs_hook=collections.OrderedDict)
            tempmods = []
        if 'me' not in tempconf:
            conferr('\'me\' block not found!')

        else:
            if 'server' not in tempconf['me']:
                conferr('\'me::server\' not found!')

            if 'name' not in tempconf['me']:
                conferr('\'me::name\' not found!')
            else:
                localServer.name = tempconf['me']['name']

            if 'sid' not in tempconf['me']:
                conferr('\'me::sid\' not found!')

            if tempconf['me']['sid'] == '000':
                conferr('\'me::sid\' must be a unique number. Please change this to a random number between 001-999')

            if not tempconf['me']['sid'].isdigit() or len(tempconf['me']['sid']) != 3:
                conferr('\'me::sid\' must be a 3 length number')
            if isinstance(tempconf['me']['sid'], int):
                tempconf['me']['sid'] = str(tempconf['me']['sid'])

        localServer.hostname = tempconf['me']['server']
        localServer.name = tempconf['me']['name']
        localServer.sid = tempconf['me']['sid']

        if 'admin' not in tempconf:
            conferr('\'admin\' block not found!')

        if 'listen' not in tempconf:
            conferr('\'listen\' block not found')
        else:
            for port in tempconf['listen']:
                if not str(port).isdigit():
                    conferr( 'invalid port in \'listen\' block: {} -- ports must be numeric.'.format(port))
                    continue
                if int(port) <= 1024:
                    conferr('invalid port in \'listen\' block: {} -- port cannot be lower than 1024.'.format(port))
                    continue
                if 'options' not in tempconf['listen'][port]:
                    conferr('\'options\' missing in \'listen\' block for port {}.'.format(port))
                elif 'clients' not in tempconf['listen'][port]['options'] and 'servers' not in tempconf['listen'][port]['options']:
                    conferr("Port {} does not have a 'servers' or 'clients' option in their listen-block.".format(port))
                elif 'clients' in tempconf['listen'][port]['options'] and 'servers' in tempconf['listen'][port]['options']:
                    conferr("'options' can not contain both 'servers' and 'clients' in 'listen' block for port {}.".format(port))

            for port in tempconf['listen']:
                if 'ssl' in tempconf['listen'][port]['options']:
                    if not os.path.isfile(localServer.rootdir+'/'+tempconf['settings']['ssl_cert']) or not os.path.isfile(localServer.rootdir+'/'+tempconf['settings']['ssl_key']):
                        conferr("You have one or more SSL ports listening but there are files missing in {}/ssl/ folder. Make sure you have 'server.cert.pem' and 'server.key.pem' present!".format(localServer.rootdir), noConf=True)
                        conferr("You can create self-signed certs (not recommended) by issuing the following command in your terminal: openssl req -x509 -newkey rsa:4096 -keyout server.key.pem -out server.cert.pem", noConf=True)
                        conferr("or you can get a free CA cert from Let's Encrypt: https://letsencrypt.org", noConf=True)
                        break
        if 'class' not in tempconf:
            conferr('\'class\' block not found')
        else:
            for cls in tempconf['class']:
                if 'sendq' not in tempconf['class'][cls]:
                    conferr('\'sendq\' missing for class \'{}\''.format(cls))
                if 'recvq' not in tempconf['class'][cls]:
                    conferr('\'recvq\' missing for class \'{}\''.format(cls))
                if 'max' not in tempconf['class'][cls]:
                    conferr('\'max\' missing for class \'{}\''.format(cls))

        if 'allow' not in tempconf:
            conferr('\'allow\' block not found')
        else:
            for cls in tempconf['allow']:
                if cls not in tempconf['class']:
                    conferr('Class \'{}\' found in allow-block, but it does not exist'.format(cls))
                else:
                    if 'ip' not in tempconf['allow'][cls] and 'hostname' not in tempconf['allow'][cls]:
                        conferr('\'ip\' or \'hostname\' missing for allow-class \'{}\''.format(cls))
                    if 'maxperip' not in tempconf['allow'][cls]:
                        conferr('\'maxperip\' missing for allow-class \'{}\''.format(cls))

        if 'settings' not in tempconf:
            conferr('\'settings\' block not found!')
        else:
            reqvalues = ['cloak-key', 'throttle', 'nickflood', 'regtimeout', 'restartpass', 'diepass']
            for v in reqvalues:
                if v not in tempconf['settings']:
                    conferr('\'{}\' missing in settings-block'.format(v))

            if 'throttle' in tempconf['settings']:
                try:
                    tempconf['settings']['throttle'].split(':')[1]
                except:
                    conferr('invalid \'throttle\' in settings-block: must be connections:time in integer format')
                if not tempconf['settings']['throttle'].split(':')[0].isdigit() or not tempconf['settings']['throttle'].split(':')[1].isdigit():
                    conferr('invalid \'throttle\' in settings-block: must be connections:time in integer format')

            if 'nickflood' in tempconf['settings']:
                try:
                    tempconf['settings']['nickflood'].split(':')[1]
                except:
                    conferr('invalid \'nickflood\' in settings-block: must be nickchanges:time in integer format')
                if not tempconf['settings']['nickflood'].split(':')[0].isdigit() or not tempconf['settings']['nickflood'].split(':')[1].isdigit():
                    conferr('invalid \'nickflood\' in settings-block: must be nickchanges:time in integer format')

            if 'regtimeout' in tempconf['settings']:
                if not str(tempconf['settings']['regtimeout']).isdigit() or not isinstance(tempconf['settings']['regtimeout'], int):
                    conferr('invalid \'regtimeout\' in settings-block: must be an integer')

        if 'ulines' in tempconf['settings'] and not isinstance(tempconf['settings']['ulines'], list):
            conferr('invalid \'ulines\' in settings-block: must be a list')

        if 'services' in tempconf['settings'] and not isinstance(tempconf['settings']['services'], str):
            conferr('invalid \'ulines\' in settings-block: must be a string')

        if 'restartpass' in tempconf['settings'] and not isinstance(tempconf['settings']['restartpass'], str):
            conferr('invalid \'restartpass\' in settings-block: must be a string')
        else:
            if 'restartpass' in tempconf['settings'] and len(tempconf['settings']['restartpass']) < 8:
                conferr('Restart password is too short in settings-block: minimum 8 characters')

        if 'diepass' in tempconf['settings'] and not isinstance(tempconf['settings']['diepass'], str):
            conferr('invalid \'diepass\' in settings-block: must be a string')
        else:
            if 'diepass' in tempconf['settings'] and len(tempconf['settings']['diepass']) < 8:
                conferr('Die password is too short in settings-block: minimum 8 characters')

        if 'dnsbl' in tempconf:
            if 'list' not in tempconf['dnsbl']:
                conferr('\'list\' containing DNSBL\'s missing')
            if 'iplist' in tempconf['dnsbl']:
                try:
                    with open(confdir+tempconf['dnsbl']['iplist'], 'r') as f:
                        localServer.bannedList = f.read().splitlines()
                        logging.debug('Added {} entries to bannedList: {}'.format(len(localServer.bannedList), localServer.bannedList))
                except Exception as ex:
                    pass

        if 'opers' in tempconf:
            oper_conf = main_conf

        if 'link' in tempconf:
            link_conf = main_conf

        if 'include' in tempconf:
            for include in tempconf['include']:
                noUpdate = False
                conffile = include
                try:
                    with open(confdir+conffile) as j:
                        t = j.read().split('\n')
                        t = json_preprocess(t)
                        t = json.loads(t)
                        for entry in dict(t):
                            if entry in tempconf:
                                tempconf[entry].update(t[entry])
                                noUpdate = True
                                continue
                        if not noUpdate:
                            tempconf.update(t)
                        if 'opers' in t:
                            oper_conf = include
                        if 'link' in t:
                            link_conf = include
                        if 'dnsbl' in t:
                            if 'list' not in t['dnsbl']:
                                conferr('\'list\' containing DNSBL\'s missing')

                except Exception as ex:
                    logging.exception(ex)
                    conferr(ex, err_conf=include)
        if 'opers' in tempconf:
            check_opers(tempconf, err_conf=oper_conf)
        if 'link' in tempconf:
            check_links(tempconf, mainconf=main_conf, err_conf=link_conf)
        localServer.excepts = {}
        if 'except' in tempconf:
            for type in tempconf['except']:
                if type not in localServer.excepts:
                    localServer.excepts[type] = []
                for entry in tempconf['except'][type]:
                    localServer.excepts[type].append(entry)

        localServer.deny = {}
        if 'deny' in tempconf:
            for entry in tempconf['deny']:
                localServer.deny[entry] = tempconf['deny'][entry]
                logging.debug('Added deny for {}: {}'.format(entry, localServer.deny))

        ### Checking optional modules.
        if 'modules' not in tempconf:
            conferr('You don\'t seem to have any modules loaded. ProvisionIRCd will not function without them.')
            return

        if 'modules' in tempconf:
            local_modules = [m for m in localServer.modules]
            for m in dict(localServer.modules):
                #logging.info('Unloading module {}'.format(m.__name__))
                Modules.UnloadModule(localServer, m.__name__)
            modules = Modules.ListModules(localServer)
            for m in [m for m in local_modules if m not in tempconf['modules']]:
                tempconf['modules'].append(m.__name__)
            for m in [m for m in tempconf['modules'] if not m.startswith('modules.')]:
                m = 'modules.'+m.replace('/', '.')
                try:
                    reload = 1 if m in [mod.__name__ for mod in local_modules] else 0
                    module = [mod for mod in local_modules if mod.__name__ == m]
                    if module:
                        module = module[0]
                    try:
                        result = Modules.LoadModule(localServer, m, modules[m], reload=reload, module=module)
                        if result:
                            raise Exception(result)
                    except Exception as ex:
                        err = 'Unable to load module \'{}\': {}'.format(m, ex)
                        logging.error(err)
                        if rehash:
                            localServer.broadcast([user], 'NOTICE {} :*** [info] -- {}'.format(user.nickname, err))
                        else:
                            conferr(err)
                        continue
                except Exception as ex:
                    logging.exception(ex)
        try:
            localServer.server_cert = tempconf['settings']['ssl_cert']
            localServer.server_key = tempconf['settings']['ssl_key']
            localServer.ca_certs = tempconf['settings']['ssl_ca']
            localServer.server_password = tempconf['settings']['ssl_password']
            version = '{}{}'.format(sys.version_info[0], sys.version_info[1])
            if int(version) >= 36:
                temp_sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
                temp_sslctx.load_cert_chain(certfile=localServer.server_cert, keyfile=localServer.server_key, password=localServer.server_password)
                temp_sslctx.load_default_certs(purpose=ssl.Purpose.CLIENT_AUTH)
                temp_sslctx.load_verify_locations(cafile=localServer.ca_certs)
                temp_sslctx.verify_mode = ssl.CERT_NONE
                localServer.sslctx = temp_sslctx

        except PermissionError as ex:
            err = 'Reloading TLS certificates failed with PermissionError. Make sure the files can be read by the current user.'
            if rehash:
                localServer.notice(user, '*** {}'.format(err))
            else:
                conferr(err)

        except FileNotFoundError as ex:
            err = "One or more required SSL files could not be found."
            err += "\nCheck to see if the following files are present and valid:"
            err += "\n"+localServer.server_cert
            err += "\n"+localServer.server_key
            err += "\n"+localServer.ca_certs
            conferr(err)
            logging.exception(ex)

        except Exception as ex:
            logging.exception(ex)
            if rehash:
                localServer.notice(user, '*** [ssl] -- Error: {}'.format(ex))

    except KeyError as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        conferr('Missing conf block: {}'.format(ex), err_conf=main_conf)

    except json.JSONDecodeError as ex:
        s = 'Invalid conf format. Make sure the JSON format is correct: {}'.format(ex)
        _print(s, server=localServer)
        conferr(s)

    except Exception as ex:
        #pass
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        conferr(e)

    if errors:
        for e in errors:
            s = 'ERROR: '+e
            if localServer.running:
                logging.error(e)
            else:
                print(s)
            if rehash:
                localServer.broadcast([user], 'NOTICE {} :*** [error] -- {}'.format(user.nickname, e))
        if rehash:
            localServer.broadcast([user], 'NOTICE {} :*** Configuration failed to reload.'.format(user.nickname))
        return 0

    else:
        ### Open new ports?
        currently_listening = []
        new_ports = []
        for sock in localServer.listen_socks:
            try:
                ip, port = sock.getsockname()
                currently_listening.append(str(port))
            except Exception as ex:
                logging.exception(ex)
        for port in tempconf['listen']:
            new_ports.append(port)

        localServer.conf = tempconf
        for p in [p for p in localServer.conf['listen'] if str(p) not in currently_listening]:
            if 'clients' in set(localServer.conf['listen'][p]['options']):
                try:
                    localServer.listen_socks[localServer.listenToPort(int(p), 'clients')] = 'clients'
                except Exception as ex:
                    logging.warning('Unable to listen on port {}: {}'.format(p, ex))

            elif 'servers' in set(localServer.conf['listen'][p]['options']):
                try:
                    localServer.listen_socks[localServer.listenToPort(int(p), 'servers')] = 'servers'
                except Exception as ex:
                    logging.warning('Unable to listen on port {}: {}'.format(p, ex))
        ### Now close ports.
        for p in [p for p in localServer.listen_socks if str(p.getsockname()[1]) not in new_ports]:
            try:
                logging.info('Closing port {}'.format(p))
                del localServer.listen_socks[p]
                p.close()
            except Exception as ex:
                print(ex)

        if rehash:
            localServer.broadcast([user], 'NOTICE {} :*** Configuration reloaded without any problems.'.format(user.nickname))

        del j, t, tempconf, tempmods

        ### Load +P channels from db/chans.db with their modes/settings.
        if os.path.exists(localServer.rootdir+'/db/chans.db'):
            perm_data = {}
            try:
                with open(localServer.rootdir+'/db/chans.db') as f:
                    perm_data = f.read().split('\n')[0]
                    perm_data = json.loads(perm_data)
                    ### Restoring permanent channels.
                    for chan in [chan for chan in perm_data if chan.lower() not in [c.name.lower() for c in localServer.channels]]:
                        c = ircd.Channel(chan)
                        localServer.channels.append(c)
                        localServer.chan_params[c] = {}
                        for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'channel_create']:
                            try:
                                callable[2](localServer, localServer, c)
                            except Exception as ex:
                                logging.exception(ex)

                        if 'creation' in perm_data[chan]:
                            c.creation = perm_data[chan]['creation']
                        params = []
                        for m in [m for m in perm_data[chan]['modes'] if m in perm_data[chan]['modeparams']]:
                            params.append(perm_data[chan]['modeparams'][m])
                        #params = ' '.join([perm_data[chan]['modeparams'][key] for key in perm_data[chan]['modeparams']])
                        modestring = '+{} {}'.format(perm_data[chan]['modes'], ' '.join(params))
                        logging.debug('Sending: {}'.format(modestring))
                        localServer.handle('MODE', c.name+' '+modestring)
                        logging.debug('Sent: {}'.format(modestring))
                        c.bans = perm_data[chan]['bans']
                        c.excepts = perm_data[chan]['excepts']
                        c.invex = perm_data[chan]['invex']
                        if perm_data[chan]['topic']:
                            c.topic = perm_data[chan]['topic'][0]
                            c.topic_author = perm_data[chan]['topic'][1]
                            c.topic_time = perm_data[chan]['topic'][2]
                        logging.debug('Restored: {}'.format(c))
                        logging.debug('Modes: {}'.format(c.modes))
                        logging.debug('Params: {}'.format(localServer.chan_params[c]))
            except Exception as ex:
                logging.debug(ex)

        ### Restore TKL.
        if os.path.exists(localServer.rootdir+'/db/tkl.db') and not localServer.tkl:
            try:
                with open(localServer.rootdir+'/db/tkl.db') as f:
                    tkl_data = f.read().split('\n')[0]
                    tkl_data = json.loads(tkl_data)
                    localServer.tkl = tkl_data
                    num = 0
                    for key in localServer.tkl:
                        for item in localServer.tkl[key]:
                            num += 1

                    logging.debug(f'Restored {(num)} TKL entr{"y" if num == 1 else "ies"}.')
            except Exception as ex:
                logging.exception(ex)

        return 1
    gc.collect()
    return 1

def check_opers(tempconf, err_conf):
    if 'opers' not in tempconf: # or 'operclass' not in tempconf:
        return
    reqvalues = ['class', 'password', 'modes', 'snomasks', 'host', 'operclass']
    for oper in tempconf['opers']:
        if oper not in confOpers:
            confOpers.append(oper)
        else:
            conferr('duplicate oper-block \'{}\''.format(oper))
            continue
        for v in reqvalues:
            if v not in tempconf['opers'][oper]:
                conferr('\'{}\' missing in oper-block \'{}\''.format(v, oper))
        if not isinstance(tempconf['opers'][oper]['host'], list):
            conferr('\'host\' must be a list for oper-block \'{}\''.format(oper))

        operclass = tempconf['opers'][oper]['operclass']
        if operclass not in tempconf['operclass']:
            conferr('operclass \'{}\' not found'.format(operclass), err_conf=err_conf)

        #operpass = tempconf['opers'][oper]['password'].encode('utf-8')
        if tempconf['opers'][oper]['password'].startswith('$2b$') and len(tempconf['opers'][oper]['password']) > 58:
            if not bc:
                ### detected bcrypt pass.
                conferr('Oper block {} has a bcrypt password but the bcrypt package is not installed. Either install it with pip or use a plaintext password.'.format(oper))

        #try:
        #    bcrypt.checkpw(b'test', operpass)
        #except ValueError:
        #    conferr('Invalid salt for oper {} password. Make sure you use bcrypt. You can get one with /mkpasswd on IRC or use the --mkpasswd argument.'.format(oper))

def check_links(tempconf, mainconf, err_conf):
    if 'link' not in tempconf:
        return
    reqvalues = ['pass', 'class']
    for link in tempconf['link']:
        if link not in confLinks:
            confLinks.append(link)
        else:
            conferr('duplicate link-block \'{}\''.format(link), err_conf=err_conf)
            continue
        for v in reqvalues:
            if v not in tempconf['link'][link]:
                conferr('\'{}\' missing in link-block \'{}\''.format(v, link), err_conf=err_conf)
                continue
        if len(tempconf['link'][link]['pass']) < 8:
            conferr('Link password for \'{}\' is too short. Minimum 8 characters'.format(link), err_conf=err_conf)

        if 'class' in tempconf['link'][link]:
            cls = tempconf['link'][link]['class']
            if cls not in tempconf['class']:
                conferr('Class \'{}\' not found for link \'{}\''.format(cls, link), err_conf=err_conf)
                continue

        if 'outgoing' not in tempconf['link'][link] and 'incoming' not in tempconf['link'][link]:
            conferr('link-block \'{}\' must have either an \'outgoing\' or an \'incoming\' block, or both'.format(link), err_conf=err_conf)
