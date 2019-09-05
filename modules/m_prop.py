"""
provides channel properties with /prop command
"""

import ircd
import time
import re
from handle.functions import logging, match
#from modules.m_mode import makeMask
#from collections import OrderedDict

### Dictionary of properties. name: chlevel
properties = {
                "rejoindelay": 5,
                "nomasshighlight": 5
             }

'''
named_modes = {
            "n": "noextmsg",
            "m": "moderated",
            "r": "rejoindelay",
            }

chmode = 'Z'
mode_prefix = '!'
list_name = 'properties' ### Name of the list, i.e. channel.properties. Used in SJOIN to check if there's a duplicate entry, or to remove all entries.

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
@ircd.Modules.channel_modes(chmode, 0, 4, 'Add or remove properties for your channel with mode +Z', None, None, '[property]') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.hooks.pre_local_chanmode()
@ircd.Modules.hooks.pre_remote_chanmode()
def prop_mode(self, localServer, channel, modebuf, parambuf, action, m, param):
    if m != chmode:
        return
    try:
        if (action == '+' or not action) and not param:
            ### Requesting list.
            #if self.chlevel(channel) < 3 and 'o' not in self.modes:
            #    return self.sendraw(482, '{} :You are not allowed to view the properties'.format(channel.name))
            #for entry in OrderedDict(reversed(list(channel.properties.items()))):
            for m in channel.modes:
                self.sendraw(961, '{} +{}'.format(channel.name, named_modes[m]))
            return self.sendraw(960, '{} :End of Channel Properties'.format(channel.name))

        valid = re.findall("^([1-9][0-9]{0,3}):(.*)", param)
        if not valid:
           return logging.info('Invalid param for {}{}: {}'.format(action, m, param))

        mask = makeMask(localServer, param.split(':')[1])
        logging.info('Param for {}{} set: {}'.format(action, m, param))
        logging.info('Mask: {}'.format(mask))
        raw_param = param
        param = '{}:{}'.format(':'.join(param.split(':')[:1]), mask)
        if action == '+':
            if param in channel.properties:
                return
            try:
                setter = self.fullmask()
            except:
                setter = self.hostname
            channel.properties[param] = {}
            channel.properties[param]['setter'] = setter
            channel.properties[param]['ctime'] = int(time.time())
            #modebuf.append(m)
            parambuf.append(param)
        elif action == '-' and (param in channel.properties or raw_param in channel.properties):
            if param in channel.properties:
                del channel.properties[param]
                parambuf.append(param)
            else:
                del channel.properties[raw_param]
                parambuf.append(raw_param)
        modebuf.append(m)

    except Exception as ex:
        logging.exception(ex)
'''

@ircd.Modules.params(1)
@ircd.Modules.commands('prop')
def prop(self, localServer, recv):
    """Maintain channel properties to expand functionality.
 /prop <channel>                        - View active properties.
 /prop <channel> <property> :[param]    - Add or remove channel properties.
                                          To remove a property, dismiss the param value.
-
Current supported properties:
 rejoindelay <int(1-60)>    - Blocks immediate rejoins after kick for <int> seconds.
 nomasshighlight <int(>2)>  - Blocks mass highlights in the channel with more than <int> nicknames, or all.
"""
    try:
        chan = [chan for chan in localServer.channels if chan.name.lower() == recv[1].lower()]
        if not chan:
            return localServer.notice(self, "Channel {} does not exist".format(recv[1]))
        chan = chan[0]
        if self.chlevel(chan) < 2 and not self.ocheck('o', 'override'):
            return
        if len(recv) == 2:
            ### Requesting prop list.
            if not chan.properties:
                return localServer.notice(self, "No properties for {} set.".format(chan.name))
            for p in chan.properties:
                localServer.notice(self, "{} = {}".format(p, chan.properties[p]))
            return
        ### /PROP <channel> <property> :<data>
        elif len(recv) == 3:
            return localServer.notice(self, "Invalid syntax: /prop <channel> <property> :[data]")
        global properties
        if len(recv) > 3:
            prop = recv[2]
            data = recv[3]
            if prop not in properties:
                return localServer.notice(self, "No such property: {}".format(prop))
            if not data.startswith(':'):
                return localServer.notice(self, "Invalid syntax: /prop <channel> <property> :[data]")
            if not data[1:]:
                if prop in chan.properties:
                    del chan.properties[prop]
                    return localServer.notice(self, "Property {} removed from {}".format(prop, chan.name))
                else:
                    return localServer.notice(self, "Property {} is not active on {}".format(prop, chan.name))

            data = data[1:]
            if prop.lower() == 'rejoindelay':
                ### Takes an integer.
                if not data.isdigit() or 0 <= int(data) > 60:
                    return localServer.notice(self, "Data for {} must be an integer between 1-60.".format(prop))
                chan.properties[prop] = int(data)

            elif prop.lower() == 'nomasshighlight':
                ### Takes an integer.
                if not data.isdigit() or int(data) <= 2:
                    return localServer.notice(self, "Data for {} must be an integer >2.".format(prop))
                chan.properties[prop] = int(data)

            return localServer.notice(self, "Done: {} {}".format(prop, data))

    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.hooks.local_join()
def join(self, localServer, channel):
    if not hasattr(channel, 'properties'):
        channel.properties = {}

@ircd.Modules.hooks.channel_destroy()
def destroy(self, localServer, channel):
    channel.properties = {}

def init(localServer, reload=False):
    for chan in [chan for chan in localServer.channels if not hasattr(chan, 'properties')]:
        chan.properties = {}



### No instant rejoin after kicks checks.
@ircd.Modules.hooks.local_kick()
def got_kicked(self, localServer, user, channel, reason):
    user.kicktime = int(time.time())
    logging.debug('{} kicktime set: {}'.format(user.nickname, user.kicktime))

@ircd.Modules.hooks.pre_local_join()
def user_wants_join(self, localServer, channel, **kwargs):
    if 'rejoindelay' not in channel.properties or 'override' in kwargs:
        return (1, [])
    if hasattr(self, 'kicktime') and int(time.time()) - self.kicktime <= channel.properties['rejoindelay']:
        localServer.notice(self, "* Please wait a while before rejoining after a kick.")
        return (0, [])
    else:
        return (1, [])


### No mass highlights.
@ircd.Modules.hooks.pre_chanmsg()
def check_hl(self, localServer, channel, msg):
    hl_limit = channel.properties['nomasshighlight']
    matches = 0
    regex = re.compile("\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?", re.UNICODE)
    delimiters = [',', '!', '?', '.', ' ']
    for word in msg.split():
        word = regex.sub('', word)
        for d in delimiters:
            check_match = word.rstrip(d).lower()
            is_user = [u for u in channel.users if check_match == u.nickname.lower()]
            if is_user:
                matches += 1
                break
    if matches >= hl_limit:
        localServer.notice(self, "* Message blocked: Mass highlighting users is not allowed on {}.".format(channel.name))
        return 0
