import sys
from dataclasses import dataclass
from enum import IntFlag
from typing import ClassVar

from handle.logger import logging

flag_idx = 100
hook_idx = 100


def flag():
    global flag_idx
    flag_idx += 1
    return flag_idx


def hook():
    global hook_idx
    hook_idx += 1
    return hook_idx


class Flag(IntFlag):
    CMD_UNKNOWN = 1 << 0  # 1
    CMD_USER = 1 << 1  # 2
    CMD_SERVER = 1 << 2  # 4
    CMD_OPER = 1 << 3  # 8

    # Allows a user to bypass most command restrictions.
    # At this moment this flag doesn't do much - not really implemented yet.
    CLIENT_CMD_OVERRIDE = 1 << 4  # 16
    CLIENT_SHUNNED = 1 << 5  # 32
    CLIENT_HANDSHAKE_FINISHED = 1 << 6  # 64
    CLIENT_REGISTERED = 1 << 7  # 128
    CLIENT_KILLED = 1 << 8  # 256
    CLIENT_USER_FLOOD_SAFE = 1 << 9  # 512
    CLIENT_USER_SAJOIN = 1 << 10  # 1024
    CLIENT_USER_SANICK = 1 << 11  # 2048
    CLIENT_EXIT = 1 << 12  # 4096
    CLIENT_TLS_FIRST_READ = 1 << 13


class Numeric:
    RPL_WELCOME = 1, ":Welcome to the {} IRC Network {}!{}@{}"
    RPL_YOURHOST = 2, ":Your host is {}, running version {}"
    RPL_CREATED = 3, ":This server was created {} at {}"
    RPL_MYINFO = 4, "{} {} {} {}"
    RPL_ISUPPORT = 5, "{} :are supported by this server"
    RPL_MAP = 6, ":{:40} {} [{}%] [Uptime: {}, lag: {}ms]"
    RPL_MAPEND = 7, ":End of /MAP"
    RPL_SNOMASK = 8, "+{} :Server notice mask"
    RPL_BOUNCE = 10, "{} {} :Please connect to this server"
    RPL_CLONES = 30, ":User {} is logged in {} times via IP {}: {}"
    RPL_NOCLONES = 31, ":No clones found on this {}"

    RPL_STATSHELP = 210, "{} :- {}"
    RPL_STATSLINKINFO = 211, "{} {} {} {} {} {} {} {} :{}"
    RPL_ENDOFSTATS = 219, "{} :End of /STATS report"
    RPL_UMODEIS = 221, "{}"
    RPL_STATSGLINE = 223, "{} {} {} {} {} :{}"
    RPL_STATSSPAMF = 229, "{} {} {} {} {} {} {} {} :{}"
    RPL_STATSEXCEPTTKL = 230, "{} {} {} {} :{}"
    RPL_RULES = 232, ":- {}"
    RPL_STATSUPTIME = 242, "{}"
    RPL_STATSOLINE = 243, "{} {} * {} {} {}"
    RPL_STATSDEBUG = 249, ":{}"
    RPL_LUSERCLIENT = 251, ":There {} {} user{} and {} invisible on {} server{}"
    RPL_LUSEROP = 252, "{} :IRC Operator{} online",
    RPL_LUSERUNKNOWN = 253, "{} :unknown connection{}"
    RPL_LUSERCHANNELS = 254, "{} :channel{} in use"
    RPL_LUSERME = 255, ":I have {} client{} and {} server{}"
    RPL_ADMINME = 256, ":Administrative info about {}"
    RPL_ADMINLOC1 = 257, ":{}"
    RPL_ADMINLOC2 = 258, ":{}"
    RPL_ADMINEMAIL = 259, ":{}"
    RPL_LOCALUSERS = 265, ":{} user{} on this server. Max: {}"
    RPL_GLOBALUSERS = 266, ":{} user{} on entire network. Max: {}"
    RPL_WHOISCERTFP = 276, "{} :has client certificate fingerprint {}"
    RPL_ACCEPTLIST = 281, "{}"
    RPL_ENDOFACCEPT = 282, "End of /ACCEPT list."
    RPL_HELPTLR = 292, ":{}"

    RPL_AWAY = 301, "{} :{}"
    RPL_USERHOST = 302, ":{}"
    RPL_TEXT = 304, ":{}"
    RPL_ISON = 303, ":{}"
    RPL_UNAWAY = 305, ":You are no longer marked as being away"
    RPL_NOWAWAY = 306, ":You have been marked as being away"
    RPL_WHOISREGNICK = 307, "{} :is identified for this nick"
    RPL_RULESSTART = 308, ":- {} Rules -"
    RPL_ENDOFRULES = 309, ":End of RULES"
    RPL_WHOISUSER = 311, "{} {} {} * :{}"
    RPL_WHOISSERVER = 312, "{} {} :{}"
    RPL_WHOISOPERATOR = 313, "{} :is {}{}"
    RPL_WHOWASUSER = 314, "{} {} {} * :{}"
    RPL_ENDOFWHO = 315, "{} :End of /WHO list."
    RPL_WHOISIDLE = 317, "{} {} {} :seconds idle, signon time"
    RPL_ENDOFWHOIS = 318, "{} :End of /WHOIS list."
    RPL_WHOISCHANNELS = 319, "{} :{}"
    RPL_WHOISSPECIAL = 320, "{} :{}"
    RPL_LISTSTART = 321, "Channel :Users  Name"
    RPL_LIST = 322, "{} {} :{} {}"
    RPL_LISTEND = 323, ":End of /LIST"
    RPL_CHANNELMODEIS = 324, "{} +{} {}"
    RPL_CREATIONTIME = 329, "{} {}"
    RPL_WHOISACCOUNT = 330, "{} {} :is using account"
    RPL_NOTOPIC = 331, "{} :No topic is set."
    RPL_TOPIC = 332, "{} :{}"
    RPL_TOPICWHOTIME = 333, "{} {} {}"
    RPL_WHOISBOT = 335, "{} :is a bot on {}"
    RPL_INVITING = 341, "{} {}"
    RPL_INVEXLIST = 346, "{} {} {} {}"
    RPL_ENDOFINVEXLIST = 347, "{} :End of Channel Invite List"
    RPL_EXLIST = 348, "{} {} {} {}"
    RPL_ENDOFEXLIST = 349, "{} :End of Channel Exception List"
    RPL_VERSION = 351, "{} {} [{}]"
    RPL_WHOREPLY = 352, "{} {} {} {} {} {} :{} {}"
    RPL_NAMEREPLY = 353, "= {} :{}"
    RPL_WHOSPCRPL = 354, "{}"
    RPL_LINKS = 364, "{} {} :{} {}"
    RPL_ENDOFLINKS = 365, ":End of LINKS"
    RPL_ENDOFNAMES = 366, "{} :End of /NAMES list"
    RPL_BANLIST = 367, "{} {} {} {}"
    RPL_ENDOFBANLIST = 368, "{} :End of Channel Ban List"
    RPL_ENDOFWHOWAS = 369, "{} :End of /WHOWAS list"
    RPL_INFO = 371, ":{}"
    RPL_MOTD = 372, ":- {}"
    RPL_MOTDSTART = 375, ":{} - Message of the Day"
    RPL_ENDOFMOTD = 376, ":End of /MOTD command."
    RPL_WHOISHOST = 378, "{} :is connecting from {}@{} {}"
    RPL_WHOISMODES = 379, "{} :is using modes: +{}{}"
    RPL_YOUREOPER = 381, ":You are now an IRC Operator."
    RPL_REHASHING = 382, "{} :Rehashing"
    RPL_IRCOPS = 386, ":{}"
    RPL_QLIST = 386, "{} {}"
    RPL_ENDOFIRCOPS = 387, ":End of /IRCOPS."
    RPL_ENDOFQLIST = 387, "{} :End of Channel Owner List"
    RPL_ALIST = 388, "{} {}"
    RPL_ENDOFALIST = 389, "{} :End of Channel Admin List"
    RPL_TIME = 391, ":{}"
    RPL_HOSTHIDDEN = 396, "{} :is now your displayed host"

    RPL_LOGON = 600, "{} {} {} {} :logged online"
    RPL_LOGOFF = 601, "{} {} {} {} :logged offline"
    RPL_WATCHOFF = 602, "{} {} {} {} :stopped watching"
    RPL_WATCHSTAT = 603, ":You have {} and are on {} WATCH entries"
    RPL_NOWON = 604, "{} {} {} {} :is online"
    RPL_NOWOFF = 605, "{} {} {} {} :is offline"
    RPL_WATCHLIST = 606, ":{}"
    RPL_ENDOFWATCHLIST = 607, ":End of WATCH {}"
    RPL_OTHERUMODEIS = 665, "{} {}"
    RPL_STARTTLS = 670, ":{}"
    RPL_WHOISSECURE = 671, "{} :is using a secure connection"

    RPL_TARGUMODEG = 716, "{} :has usermode +g"
    RPL_TARGNOTIFY = 717, "{} :has been informed of your request, awaiting reply"
    RPL_UMODEGMSG = 718, "{} {} :is messaging you, and you have umode +g."
    RPL_MONONLINE = 730, ":{}"
    RPL_MONOFFLINE = 731, ":{}"
    RPL_MONLIST = 732, ":{}"
    RPL_ENDOFMONLIST = 733, ":End of MONITOR list."
    RPL_MONLISTFULL = 734, ":Monitor list is full."

    RPL_LOGGEDIN = 900, "{} {} :You are now logged in as {}"
    RPL_LOGGEDOUT = 901, "{} :You are now logged out"
    RPL_NICKLOCKED = 902, ":You must use a nick assigned to you."
    RPL_SASLSUCCESS = 903, ":SASL authentication successful"
    RPL_SASLMECHS = 908, ":{} are available SASL mechanisms"

    # Error numerics.
    ERR_NOSUCHNICK = 401, "{} :No such nick"
    ERR_NOSUCHSERVER = 402, "{} :No such server"
    ERR_NOSUCHCHANNEL = 403, "{} :No such channel"
    ERR_CANNOTSENDTOCHAN = 404, "{} :{}"
    ERR_TOOMANYCHANNELS = 405, "{} :Too many channels open"
    ERR_WASNOSUCHNICK = 406, "{} :There was no such nickname"
    ERR_INVALIDCAPCMD = 410, "{} :Unknown CAP command"
    ERR_NORECIPIENT = 411, ":No recipient given'"
    ERR_NOTEXTTOSEND = 412, ":No text to send"
    ERR_UNKNOWNCOMMAND = 421, "{} :Unknown command"
    ERR_NOMOTD = 422, ":MOTD File is missing"
    ERR_NONICKNAMEGIVEN = 431, ":No nickname given"
    ERR_ERRONEUSNICKNAME = 432, "{} :Erroneous nickname (Invalid: {})"
    ERR_NICKNAMEINUSE = 433, "{} :Nickname is already in use"
    ERR_NORULES = 434, ":RULES File is missing"
    ERR_NICKTOOFAST = 438, "{} :Nick change too fast. Please wait a while before attempting again."
    ERR_SERVICESDOWN = 440, ":Services are currently down. Please try again later."
    ERR_USERNOTINCHANNEL = 441, "{} {} :User not on channel"
    ERR_NOTONCHANNEL = 442, "{} :You're not on that channel"
    ERR_USERONCHANNEL = 443, "{} :is already on channel {}"
    ERR_NONICKCHANGE = 447, ":{} Nick changes are not allowed on this channel"
    ERR_FORBIDDENCHANNEL = 448, "{} {}"
    ERR_NOTREGISTERED = 451, "You have not registered"
    ERR_ACCEPTEXIST = 457, "{} :does already exist on your ACCEPT list."
    ERR_ACCEPTNOT = 458, "{} :is not found on your ACCEPT list."
    ERR_NEEDMOREPARAMS = 461, ":{} Not enough parameters"
    ERR_ALREADYREGISTRED = 462, ":You may not reregister"
    ERR_PASSWDMISMATCH = 464, ":Password mismatch"
    ERR_CHANNELISFULL = 471, "{} :Cannot join channel (+l)"
    ERR_UNKNOWNMODE = 472, "{} :unknown mode"
    ERR_INVITEONLYCHAN = 473, "{} :Cannot join channel (+i)"
    ERR_BANNEDFROMCHAN = 474, "{} :Cannot join channel (+b)"
    ERR_BADCHANNELKEY = 475, "{} :Cannot join channel (+k)"
    ERR_NEEDREGGEDNICK = 477, "{} :Cannot join cannel: you need a registered nickname"
    ERR_BANLISTFULL = 478, "{} {} :Channel {} list is full"
    ERR_CANNOTKNOCK = 480, ":Cannot knock on {} ({})"
    ERR_NOPRIVILEGES = 481, ":Permission denied - You do not have the correct IRC Operator privileges"
    ERR_CHANOPRIVSNEEDED = 482, "{} :You're not a channel operator"
    ERR_ATTACKDENY = 484, "{} :Cannot kick protected user {}"
    ERR_KILLDENY = 485, ":Cannot kill protected user {}"
    ERR_SERVERONLY = 487, ":{} is a server-only command"
    ERR_SECUREONLY = 489, "{} :Cannot join channel (not using a secure connection)"
    ERR_NOOPERHOST = 491, ":No O:lines for your host"
    ERR_CHANOWNPRIVNEEDED = 499, "{} :You're not a channel owner"

    ERR_UMODEUNKNOWNFLAG = 501, "{} :Unknown MODE flag"
    ERR_USERSDONTMATCH = 502, ":Not allowed to change mode of other users"
    ERR_TOOMANYWATCH = 512, "{} :Maximum size for WATCH-list is 128 entries"
    ERR_NOINVITE = 518, ":Invite is disabled on channel {} (+V)"
    ERR_OPERONLY = 520, "{} :Cannot join channel (IRCOps only)"
    ERR_CANTSENDTOUSER = 531, "{} :{}"

    ERR_STARTTLS = 691, ":STARTTLS failed: {}"
    ERR_INVALIDMODEPARAM = 696, "{} {} {} :{}"

    ERR_SASLFAIL = 904, ":SASL authentication failed"
    ERR_SASLTOOLONG = 905, ":SASL message too long"
    ERR_SASLABORTED = 906, ":SASL authentication aborted"
    ERR_SASLALREADY = 907, ":You have already authenticated using SASL"
    ERR_CANNOTDOCOMMAND = 972, "{} :{}"
    ERR_CANNOTCHANGEUMODE = 973, "{} :{}"
    ERR_CANNOTCHANGECHANMODE = 974, "{} :{}"


class Hook:
    # Deny the call. Stop processing other modules.
    DENY = hook()

    # Allow the call. Stop processing other modules.
    ALLOW = hook()

    # Do nothing. Keep processing other modules.
    CONTINUE = hook()

    # Called after the IRCd has successfully booted up.
    BOOT = hook()

    # This is called every 100 milliseconds, or as soon as new data is being handled.
    LOOP = hook()

    # Called when a packet is being read or sent.
    # Arguments         from            Sender of this data.
    #                   to              Direction to send the data to.
    #                   intended_to     Actual client this data is for.
    #                   data            List of data, so that it can be modified by modules.
    PACKET = hook()

    # Called when preparing an outgoing new message. Used to assign tags etc.
    # This is used by hooks and is currently only called in the early stages of PRIVMSG, JOIN, PART and MODE.
    # Modules can use this hook to generate a new message and add tags.
    NEW_MESSAGE = hook()

    # This hook is called early in the connection phase.
    # Basically the only useful information in this phase is the IP address and the socket object of the connection.
    # Arguments:        Client
    NEW_CONNECTION = hook()

    # Used by modules to check if the handshake is completed.
    # Arguments:        Client
    IS_HANDSHAKE_FINISHED = hook()

    # This is when the connection has been accepted, but still needs to go through verification phase
    # against configuration and internal block lists.
    # When denying a connection this way, you are responsible for providing feedback to the client.
    #
    # Arguments:        Client
    # Return:           Hook.DENY or Hook.ALLOW
    PRE_CONNECT = hook()

    # This is further down the connection process, when all internal checks have been passed.
    # When this hook gets called, the local client is already registered on the server.
    # This hook is generally not used to deny/exit clients. Use PRE_CONNECT for that.
    # Argument:                 User object.
    LOCAL_CONNECT = hook()

    # When a new remote user is introduced, this hook gets called.
    # Argument:         User object.
    REMOTE_CONNECT = hook()

    # Called after reading a socket, but before performing any commands.
    # Used in IRCv3 reply tags.
    # Arguments:        client, recv
    # Return value is ignored.
    POST_SOCKREAD = hook()

    # Called in the early phase of changing channel modes.
    # Arguments:
    # client            Client changing the mode.
    # channel           Channel on which the mode is being changed.
    # modebuf           Current mode buffer
    # parambuf          Current parameter buffer
    # action            Action: + or -
    # mode              Mode char
    # param_mode        Param mode, or None if none
    # Return:           Hook.DENY or Hook.CONTINUE
    PRE_LOCAL_CHANNEL_MODE = hook()

    # Called when a local user or server changes channel modes.
    # Arguments:        client, channel, modebuf, parambuf
    LOCAL_CHANNEL_MODE = hook()

    # Called after a remote user changes channel modes.
    # Arguments:        client, channel, modebuf, parambuf
    REMOTE_CHANNEL_MODE = hook()

    # Called before a local nick change.
    # Arguments:        client, newnick
    # Return:           Hook.DENY or Hook.CONTINUE
    PRE_LOCAL_NICKCHANGE = hook()

    # Called after a local user changes his nickname
    # Arguments:        client, newnick
    LOCAL_NICKCHANGE = hook()

    # Called after a remote user changes his nickname
    # Arguments:    client, newnick
    REMOTE_NICKCHANGE = hook()

    # Called when a user joins the channel, but before sending TOPIC and NAMES.
    # Does not return anything.
    # Arguments:    client, channel
    PRE_LOCAL_JOIN = hook()

    # Gets called when a local user has joined a channel.
    # Arguments:    client, channel
    LOCAL_JOIN = hook()

    # Gets called when a remote user joins a channel.
    # Arguments:    client, channel
    REMOTE_JOIN = hook()

    # Called when a local user wants to part a channel.
    # Arguments:    client, channel, reason
    # Returns:      part reason, if it has been changed. Return nothing to keep original part reason.
    PRE_LOCAL_PART = hook()

    # Called after a local user leaves a channel.
    # Arguments:    client, channel, reason
    LOCAL_PART = hook()

    # Called after a remote user leaves a channel.
    # Arguments:    client, channel, reason
    REMOTE_PART = hook()

    # Used to check if a user can join a channel.
    # Arguments:    client, channel, key
    # Returns:      0 to allow, RPL to deny.
    CAN_JOIN = hook()

    # Called when a user fails to join a channel due to a channel mode.
    # Arguments:    client, channel, error or None
    JOIN_FAIL = hook()

    # Called after a user is allowed to join the channel,
    # but before broadcasting its join to users.
    # It will loop over all users in the channel on each call
    # to check if `client_1` may see `client_2` on the channel.
    # Arguments:    client_1, client_2, channel
    # Return:       Hook.DENY or Hook.CONTINUE
    VISIBLE_ON_CHANNEL = hook()

    # Called before a local user broadcasts his/her quit.
    # Arguments:    client, reason
    # Return:       reason, or None
    PRE_LOCAL_QUIT = hook()

    # Called after a local user quits the server.
    # Arguments:    client, reason
    LOCAL_QUIT = hook()

    # Called after a remote user quits the network.
    # Arguments:    client, reason
    REMOTE_QUIT = hook()

    # Called when a new channel is created.
    # Arguments:    client, channel
    CHANNEL_CREATE = hook()

    # Called when a channel is destroyed.
    # Arguments:    client, channel
    CHANNEL_DESTROY = hook()

    # Called before a local user sends a channel message.
    # If you do not need to modify the message, you can use CAN_SEND_TO_CHANNEL hook.
    # Arguments:    client, channel, message as list, statusmsg_prefix
    # Returns:      Hook.DENY or Hook.CONTINUE
    PRE_LOCAL_CHANMSG = hook()

    # This is called after a local user has sent a channel message.
    # Arguments:    client, channel, message, statusmsg_prefix
    LOCAL_CHANMSG = hook()

    # Called when a remote user sends a channel message.
    # Arguments:    client, channel, message, statusmsg_prefix
    REMOTE_CHANMSG = hook()

    # Called before a local user sends a private user message.
    # Arguments:    client, target, message as list, statusmsg_prefix
    # Return:       Hook.DENY or Hook.CONTINUE
    PRE_LOCAL_USERMSG = hook()

    # Called when a local user sends a private message.
    # Arguments:    client, target, message
    LOCAL_USERMSG = hook()

    # Called when a remote user sends a private message.
    # Arguments:    client, channel, message
    REMOTE_USERMSG = hook()

    # Check whether a user can send a privsmg to another user. This includes remote users (for callerid)
    # The message cannot be modified.
    # Modules using this hook are responsible to deliver any error messages back to the client.
    # Arguments:    client, target, message
    # Return:       Hook.DENY or Hook.CONTINUE
    CAN_SEND_TO_USER = hook()

    # Check whether a user can send a privsmg to a channel.
    # The message cannot be modified. If you need to edit the message, use PRE_LOCAL_CHANMSG hook.
    # Modules using this hook are responsible to deliver any error messages back to the client.
    # Arguments:    client, channel object, message, sendtype (PRIVMSG or NOTICE).
    # Return:       Hook.DENY or Hook.CONTINUE
    CAN_SEND_TO_CHANNEL = hook()

    # Called before a channel notice will be sent.
    # The message is a list, so it can be modified by modules.
    # Arguments:    client, channel, message, statusmsg_prefix
    PRE_LOCAL_CHANNOTICE = hook()

    # Called whenever a local channel notice has been sent.
    # Arguments:    client, channel, message, statusmsg_prefix
    LOCAL_CHANNOTICE = hook()

    # Called whenever a remote channel notice has been sent.
    # Arguments:    client, channel, message, statusmsg_prefix
    REMOTE_CHANNOTICE = hook()

    PRE_LOCAL_USERNOTICE = hook()

    # Called when a locel user sends a user notice.
    # Arguments:    client, user, msg
    LOCAL_USERNOTICE = hook()

    # Called when a remote user sends a user notice.
    # Arguments:    client, user, msg
    REMOTE_USERNOTICE = hook()

    # Called when a local client wants to kick a user off a channel.
    # Arguments:    client, target_client, channel, reason, oper_override (list)
    # Return:       Hook.DENY to deny.
    CAN_KICK = hook()

    # Called after a local user kicked gets kicked off a channel.
    # Arguments:    client, kick_user, channel, reason
    LOCAL_KICK = hook()

    # Called after a remote user kicked gets kicked off a channel.
    # Arguments:    client, kick_user, channel, reason
    REMOTE_KICK = hook()

    # Called when a modebar has been set on a channel.
    # Arguments:    client, channel, modebar
    MODEBAR_ADD = hook()

    # Called when a modebar has been unset from a channel.
    # Arguments:    Client, channel, modebar
    MODEBAR_DEL = hook()

    # Called when a new usermode has been set.
    # Allows for modification of `modebuf`. Use with caution.
    # Arguments:    Client, target, modebuf, mode
    UMODE_SET = hook()

    # Called when a new usermode has been unset.
    # Allows for modification of `modebuf`. Use with caution.
    # Arguments:    Client, target, modebuf, mode
    UMODE_UNSET = hook()

    # Called after a user mode has been changed.
    # Arguments:   Client, target, old_modes, current_modes
    UMODE_CHANGE = hook()

    # Called after a user changes its host or ident.
    # Arguments:    Client, old_ident, old_host
    USERHOST_CHANGE = hook()

    # Called after a user changes its realname (GECOS)
    # Arguments:    Client, realname
    REALNAME_CHANGE = hook()

    # Called before a user sets /away status.
    # Arguments:    Client, reason
    # Can be rejected by returning Hook.DENY
    PRE_AWAY = hook()

    # Called after a user successfully set /away status.
    # Arguments:    Client, reason
    AWAY = hook()

    # Called when a server links after successful auth.
    SERVER_CONNECT = hook()

    # Called after a server send its EOS.
    POST_SERVER_CONNECT = hook()

    # Called very early when we request a link, before the socket connects.
    # Arguments:    Client
    SERVER_LINK_OUT = hook()

    # Called right after an outgoing link socket connects, but before basic negotiation.
    # Arguments:    Client
    SERVER_LINK_OUT_CONNECTED = hook()

    # Called after every successful incoming SJOIN during linking.
    # Arguments:    client, recv
    # A better way to handle this is to use the CHANNEL_CREATE hook and check if the `client` is remote,
    # or in the case of locally existing channels, use the REMOTE_JOIN hook.
    SERVER_SJOIN_IN = hook()

    # Called after every outgoing UID.
    # This allows modules to sync additional user data across the network.
    # Arguments:    the client object being synced, new user client
    # If the UID is broadcast to the entire network at once, `new user client` will be None.
    # It will only be set if the UID is sent to a single server client, like in the syncing phase of a link.
    SERVER_UID_OUT = hook()

    # Called after every outgoing SJOIN.
    # This allows modules to sync additional channel data across the network.
    # This is not the same as LOCAL_JOIN and REMOTE_JOIN module hooks.
    # Arguments:    channel object, new server client
    SERVER_SJOIN_OUT = hook()

    # Called after all users and channels have been synced, but before we send our EOS.
    # Arguments:    client
    SERVER_SYNC = hook()

    # Called after everything has been synced from the remote server, after we reached their EOS.
    # Arguments:    client
    SERVER_SYNCED = hook()

    # Called when a server disconnects.
    # Arguments:    client
    SERVER_DISCONNECT = hook()

    # Called before a local user performs a command.
    # Arguments:    client, recv
    # Return:       Hook.DENY or Hook.CONTINUE
    PRE_COMMAND = hook()

    # Called after a local user performs a command.
    # Arguments:    client, recv
    POST_COMMAND = hook()

    # Called before a local user changes a channel topic.
    # Arguments:    client, channel, newtopic
    # Return:       Hook.DENY or Hook.CONTINUE
    PRE_LOCAL_TOPIC = hook()

    # Called after a user changes a channel topic.
    # Arguments:    Client, Channel, newtopic: str
    TOPIC = hook()

    # Called when a user logs in or out of a services account.
    # Arguments:    Client
    ACCOUNT_LOGIN = hook()

    # Called when /WHOIS is performed.
    # Arguments:    Client, target, whoislines: list
    WHOIS = hook()

    # Called when a /WHOIS is performed.
    # Used to add custom status characters to /WHO output.
    # Arguments:    Client, target_client (target_client = the user client in the /WHO reply)
    # Returns a single char, or None.
    WHO_STATUS = hook()

    # Called when a /MODE list is requested.
    CHAN_LIST_ENTRY = hook()

    # This dictionary is holding callbacks for each hook type.
    hooks = {}

    @staticmethod
    def call(hook_type, args=(), kwargs=None, file=None):
        """
        :param hook_type:   Hook type
        :param args:        Command arguments to pass to the hook callback
        :param kwargs:      Command keyword arguments to pass to the book callback
        :return:            0 for success, anything else for process
        """

        kwargs = kwargs or {}
        if hook_type not in Hook.hooks:
            # Hook not implemented yet.
            return Hook.CONTINUE, None

        Hook.check_deprecation(hook_type, file)

        hooks_sorted_priority = sorted(Hook.hooks[hook_type], key=lambda hook: hook[1], reverse=True)
        for callback, priority in hooks_sorted_priority:
            try:
                yield callback(*args, **kwargs), callback
            except Exception as ex:
                logging.exception(f"Exception in callback {callback}, args {args}: {ex}")
                break

    @staticmethod
    def add(hook_type, callback, priority=0):
        Hook.hooks.setdefault(hook_type, [])
        if (callback, priority) not in Hook.hooks[hook_type]:
            Hook.hooks[hook_type].append((callback, priority))

    @staticmethod
    def check_deprecation(hook_type, file=None):
        deprecated = {
            # Hook.UMODE_CHANGE: "Please use Hook.UMODE_SET and Hook.UMODE_UNSET instead!",
        }

        if hook_type in deprecated:
            hook_name = next(k for k, v in vars(Hook).items() if v is hook_type and not k.startswith('__'))
            logging.warning(f"Hook {hook_name} is deprecated: {deprecated[hook_type]}")


@dataclass
class Isupport:
    table: ClassVar[list] = []
    name: str = ''
    value: str = ''
    server: int = 0

    @property
    def string(self):
        return f"{self.name}{f'={self.value}' if self.value else ''}"

    @staticmethod
    def add(name: str, value=None, server_isupport=0):
        if (isupport := Isupport.get(name)) and value:
            isupport.value = value
            return
        Isupport.table.append(Isupport(name=name, value=value, server=server_isupport))

    @staticmethod
    def targmax(cmdname: str, value=''):
        if value is int:
            value = str(value)
        if isupport := Isupport.get("TARGMAX"):
            isupport.value += f",{cmdname}:{value}"
            return
        Isupport.add(name="TARGMAX", value=f"{cmdname}:{value}")

    @staticmethod
    def get(name):
        return next((isupport for isupport in Isupport.table if isupport.name.lower() == name.lower()), 0)

    @staticmethod
    def send_to_client(client):
        line = []
        for isupport in Isupport.table:
            line.append(isupport.string)
            if len(line) == 15:
                client.sendnumeric(Numeric.RPL_ISUPPORT, ' '.join(line))
                line = []

        if line:
            client.sendnumeric(Numeric.RPL_ISUPPORT, ' '.join(line))


class Extban:
    table = []
    symbol = '~'

    @staticmethod
    def add(extban):
        if missing_attrs := [attr for attr in ("flag", "name") if not hasattr(extban, attr)]:
            logging.error(f"Could not add extban: attributes missing: {', '.join(missing_attrs)}")
            sys.exit()

        if any(e.flag == extban.flag for e in Extban.table):
            logging.error(f"Could not add extban: flag '{extban.flag}' already exists")
            sys.exit()

        extban.is_ok = getattr(extban, "is_ok", lambda client, channel, action, mode, param: 1)
        extban.is_match = getattr(extban, "is_match", lambda a, b, c: 0)

        Extban.table.append(extban)
        Isupport.add("EXTBAN", f"{Extban.symbol},{''.join([e.flag for e in Extban.table])}")

    @staticmethod
    def is_extban(client, channel, action, mode, param):
        if not param.startswith(Extban.symbol):
            return 0

        param_split = param.split(':')
        if len(param_split) < 2:
            return -1

        name = param_split[0][1:]

        for extban in Extban.table:
            if (extban.name and extban.name == name) or extban.flag == name:
                if name == extban.flag:
                    param_split[0] = Extban.symbol + extban.name
                param = ':'.join(param_split)
                if returned_param := extban.is_ok(client, channel, action, mode, param):
                    return returned_param
        return -1

    @staticmethod
    def find(param: str):
        return next((e for e in Extban.table if param in [Extban.symbol + e.name, Extban.symbol + e.flag]), 0)

    @staticmethod
    def convert_param(param: str, convert_to_name: int = 1) -> str:
        """
        Converts extban flags or names to their counterparts.

        +b ~t:1:~a:AccountName       ->  +b ~timed:1:~account:AccountName
        """

        if not param.startswith(Extban.symbol):
            return param

        parts = [i for i in param.split(':') if i]
        converted = []
        for item in parts:
            if item[0] == Extban.symbol:
                if not (main_ext := Extban.find(item)):
                    return param

                converted.append(Extban.symbol + (main_ext.flag if not convert_to_name else main_ext.name))
            else:
                converted.append(item)

        return ':'.join(converted)
