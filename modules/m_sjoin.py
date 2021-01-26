"""
/sjoin command (server)
"""

import re
from modules.m_mode import processModes
from handle.functions import logging

import ircd

Channel = ircd.Channel

W = '\033[0m'  # white (normal)
R = '\033[31m'  # red
G = '\033[32m'  # green
Y = '\033[33m'  # yellow


class Sjoin(ircd.Command):
    def __init__(self):
        self.command = 'sjoin'
        self.req_class = 'Server'

    def execute(self, client, recv):
        raw = ' '.join(recv)
        source = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname == recv[0][1:], self.ircd.servers))
        if not source:
            logging.error('/SJOIN source not found!')
            return
        source = source[0]

        channel = recv[3]
        if channel[0] == '&':
            logging.error('{}ERROR: received a local channel from remote server: {}{}'.format(R, channel, W))
            return client.squit('Sync error! Remote server tried to link local channels.')

        if not client.eos:
            self.ircd.new_sync(self.ircd, client, raw)
        self.ircd.parammodes = self.ircd.chstatus
        for x in range(0, 4):
            for m in [m for m in self.ircd.channel_modes[x] if str(x) in '012' and m not in self.ircd.parammodes]:
                self.ircd.parammodes += m
        memberlist = []
        banlist = []
        excepts = []
        invex = []
        mod_list_data = []  # Store temp data from mods list types.
        c = 0
        if recv[4].startswith('+'):
            modes = recv[4].replace('+', '')
        else:
            modes = ''
        for pos in [pos for pos in recv[1:] if pos]:
            c += 1
            if pos.startswith(':'):
                memberlist = ' '.join(recv[c:]).split('&')[0].split('"')[0].split("'")[0][1:].split()
                continue
            if pos.startswith('&'):
                banlist.append(pos[1:])
            elif pos.startswith('"'):
                excepts.append(pos[1:])
            elif pos.startswith("'"):
                invex.append(pos[1:])

            elif c > 4 and pos and not pos[0].isalpha() and not pos[0].isdigit() and pos[0] not in ":&\"'*~@%+":
                if pos in memberlist:
                    memberlist.remove(pos)
                # Unrecognized mode, checking modules.
                # Loop over modules to check if they have a 'mode_prefix' attr.
                try:
                    for m in [m for m in self.ircd.modules if hasattr(m, 'mode_prefix') and pos[0] == m.mode_prefix]:
                        mod_list_data.append((m.chmode, pos[1:]))
                except Exception as ex:
                    logging.exception(ex)

            # Custom list. In the beginning of SJOIN args.
            custom_mode_list = {}
            list_prefix = pos[0]  # Like ^

            for m in [m for m in self.ircd.channel_mode_class if m.type == 0 and m.mode_prefix == list_prefix]:
                # 2020/02/29 05:31:20 DEBUG [m_sjoin]: Set lokale <ChannelMode 'w'>
                mode = m.mode
                custom_mode_list[mode] = []  # Params for mode, like +w (whitelist)
                p = pos[1:]
                custom_mode_list[mode].append(p)
                logging.debug(f"Appended {p} to '{mode}' (list_name={m.list_name}) custom mode list.")

                continue

        data = []

        giveModes = []
        giveParams = []

        removeModes = []
        removeParams = []

        timestamp = int(recv[2])

        for member in memberlist:
            membernick = []
            for c in member:
                if c not in ':*~@%+':
                    membernick.append(c)
            membernick = ''.join(membernick)

            userClass = list(filter(lambda c: c.nickname.lower() == membernick.lower() or c.uid == membernick, self.ircd.users))
            if not userClass:
                logging.error('{}ERROR: could not fetch userclass for remote user {}. Looks like the user did not sync correctly. Maybe nick collision, or remote leftover from a netsplit.{}'.format(R, membernick, W))
                ##continue
                # source.quit('ERROR: could not fetch userclass for remote user {}. Looks like the user did not sync correctly. Maybe nick collision, or remote leftover from a netsplit.'.format(membernick))
                continue

            userClass = userClass[0]
            p = {'override': True, 'sourceServer': client}

            # Making the remote client join local channel, creating if needed.

            userClass.handle('join', channel, params=p)
            localChan = list(filter(lambda c: c.name.lower() == channel.lower(), self.ircd.channels))[0]
            local_chan = next((c for c in self.ircd.channels if c.name == channel), None)

            if not local_chan:
                logging.error(f"ERROR: Could not find or create local channel: {channel}")
                return 0

            if len(local_chan.users) == 1:
                # Channel did not exist on self.ircd. Hook channel_create? Sure, why not.
                pass
            if userClass.server != self.ircd:
                logging.info('{}External user {} joined {} on local server.{}'.format(G, userClass.nickname, channel, W))
            if timestamp < local_chan.creation and not source.eos:
                if '*' in member:
                    giveModes.append('q')
                    giveParams.append(userClass.nickname)
                if '~' in member:
                    giveModes.append('a')
                    giveParams.append(userClass.nickname)
                if '@' in member:
                    giveModes.append('o')
                    giveParams.append(userClass.nickname)
                if '%' in member:
                    giveModes.append('h')
                    giveParams.append(userClass.nickname)
                if '+' in member:
                    giveModes.append('v')
                    giveParams.append(userClass.nickname)

        if timestamp < local_chan.creation and not source.eos:
            # Remote channel is dominant. Replacing modes with remote channel
            # Clear the local modes.
            #
            logging.info('Remote channel {} is dominant. Replacing modes with remote channels\''.format(channel))
            local_chan.creation = timestamp
            local_chan.name = channel
            pc = 5
            for m in local_chan.modes:
                if m not in modes and m in list(self.ircd.channel_modes[2]) + list(self.ircd.channel_modes[3]):
                    removeModes.append(m)
                    continue
                ### Remote info is different, remove old one first.
                if m in self.ircd.channel_modes[1] and self.ircd.chan_params[local_chan][m] != recv[pc]:
                    removeParams.append(self.ircd.chan_params[local_chan][m])
                    removeModes.append(m)
                if m in self.ircd.parammodes:
                    pc += 1

            pc = 5
            for m in modes:
                if m not in local_chan.modes and m in self.ircd.channel_modes[3]:
                    giveModes.append(m)
                    continue
                if m in self.ircd.parammodes:
                    giveModes.append(m)
                    giveParams.append(recv[pc])
                    logging.debug('SJOIN: Mode {} has param: {}'.format(m, recv[pc]))
                    pc += 1

            # Removing local channel user modes.
            for user in local_chan.users:
                for m in local_chan.usermodes[user]:
                    removeModes.append(m)
                    removeParams.append(user.nickname)

            for b in [b for b in local_chan.bans if b not in banlist]:
                removeModes.append('b')
                removeParams.append(b)

            for e in [e for e in local_chan.excepts if e not in excepts]:
                removeModes.append('e')
                removeParams.append(e)

            for I in [I for I in local_chan.invex if I not in invex]:
                removeModes.append('I')
                removeParams.append(I)

            # Remove modulair lists.
            for m in [m for m in self.ircd.channel_mode_class if m.type == 0]:
                # Remove modulair lists.
                mode = m.mode
                list_name = getattr(m, 'list_name')
                logging.debug(f"Remote takeover, clearing local list: '{list_name}' (if any)")
                l = getattr(local_chan, list_name)
                for local_modulair_mode in l:
                    param = local_modulair_mode
                    logging.debug(f"[SJOIN RT] Removing from local: -{mode} {param}")
                    removeModes.append(mode)
                    removeParams.append(param)

            # Send all remote modes to local_chan
            for b in [b for b in banlist if b not in local_chan.bans]:
                giveModes.append('b')
                giveParams.append(b)

            for e in [e for e in excepts if e not in local_chan.excepts]:
                giveModes.append('e')
                giveParams.append(e)

            for m in custom_mode_list:
                for p in custom_mode_list[m]:
                    logging.debug(f"[SJOIN RT] Syncing from remote: +{m} {p}")
                    giveModes.append(m)
                    giveParams.append(p)

            # ???
            for I in [I for I in invex if I not in local_chan.invex]:
                giveModes.append('I')
                giveParams.append(I)

            for m in [m for m in self.ircd.modules if hasattr(m, 'list_name') and hasattr(local_chan, m.list_name)]:
                remote_temp = []
                for e in mod_list_data:
                    remote_temp.append(e[1])
                for entry in [entry for entry in getattr(local_chan, m.list_name) if entry not in remote_temp]:
                    logging.debug('Local list entry +{} {} not found in remote data, so removing.'.format(m.chmode, entry, remote_temp))
                    removeModes.append(m.chmode)
                    removeParams.append(entry)

            for entry in [entry for entry in mod_list_data if entry[1] not in getattr(local_chan, m.list_name)]:
                giveModes.append(entry[0])
                giveParams.append(entry[1])

            data = []
            data.append(local_chan.name)
            modes = '{}{}'.format('-' + ''.join(removeModes) if removeModes else '', '+' + ''.join(giveModes) if giveModes else '')
            data.append(modes)
            for p in removeParams:
                data.append(p)
            for p in giveParams:
                data.append(p)




        elif timestamp == local_chan.creation and not source.eos:
            if modes:
                logging.info('{}Equal timestamps for remote channel {} -- merging modes.{}'.format(Y, local_chan.name, W))
                logging.debug(f"Modes: {modes}")
                for member in memberlist:
                    rawUid = re.sub('[:*!~&@%+]', '', member)
                    if '*' in member:
                        giveModes.append('q')
                        giveParams.append(rawUid)
                    if '~' in member:
                        giveModes.append('a')
                        giveParams.append(rawUid)
                    if '@' in member:
                        giveModes.append('o')
                        giveParams.append(rawUid)
                    if '%' in member:
                        giveModes.append('h')
                        giveParams.append(rawUid)
                    if '+' in member:
                        giveModes.append('v')
                        giveParams.append(rawUid)
                pc = 5
                for m in modes:
                    if m not in local_chan.modes:
                        giveModes.append(m)
                        if m in self.ircd.parammodes:
                            giveParams.append(recv[pc])
                            pc += 1
                        continue

                for b in [b for b in banlist if b not in local_chan.bans]:
                    giveModes.append('b')
                    giveParams.append(b)

                for e in [e for e in excepts if e not in local_chan.excepts]:
                    giveModes.append('e')
                    giveParams.append(e)

                for I in [I for I in invex if I not in local_chan.invex]:
                    giveModes.append('I')
                    giveParams.append(I)

                for m in custom_mode_list:
                    for p in custom_mode_list[m]:
                        logging.debug(f"[SJOIN merge] Appending modes: +{m} {p}")
                        giveModes.append(m)
                        giveParams.append(p)

                data = [local_chan.name]
                modes = '{}'.format('+' + ''.join(giveModes) if giveModes else '')
                data.append(modes)
                for p in removeParams:
                    data.append(p)
                for p in giveParams:
                    data.append(p)

        if modes and data:
            processModes(client, self.ircd, local_chan, data, sync=1, sourceServer=client, sourceUser=client)
