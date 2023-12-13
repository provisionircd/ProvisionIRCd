"""
provides spamfilter capabilities
"""

import logging
import re
from time import time

from handle.core import IRCD, Command, Numeric, Flag, Hook, Tkl, Stat
from handle.functions import valid_expire, is_match
from handle.validate_conf import Spamfilter


def spamfilter_match(client, spamfilter, target_cause):  # filtertarget, to_target, target_cause):
    msg = f"Spamfilter match by {client.name} ({client.user.username}@{client.user.realhost}) matching {spamfilter.match} [{target_cause}] (action: {spamfilter.action})"
    IRCD.send_snomask(client, "F", msg)
    reason = spamfilter.reason.replace("_", " ")
    if spamfilter.action == "warn":
        client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, client.name, f"[WARNING] Spamfilter match: {reason}")
        return 1

    elif spamfilter.action == "block":
        client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, client.name, f"[BLOCKED] Spamfilter match: {reason}")
        return 0

    elif spamfilter.action == "kill":
        client.kill(f"Spamfilter match: {reason}")
        return 0

    elif spamfilter.action == "gzline":
        Tkl.add(client.uplink, "Z", "*", client.ip, '*', IRCD.me.name, int(time()) + spamfilter.duration, int(time()), f"Spamfilter match: {reason}")
        return 0


def spamfilter_check(client, target, to_target, target_cause):
    if client.has_permission("immune:spamfilter"):
        return Hook.ALLOW
    allow = 1
    for spamfilter in [s for s in IRCD.configuration.spamfilters if target in s.target]:
        _filter = spamfilter.match
        if (spamfilter.match_type == "simple" and
            is_match(_filter.lower(), target_cause.lower())) or \
                (spamfilter.match_type == "regex" and re.search(_filter, target_cause)):

            if IRCD.is_except_client("spamfilter", client):
                return Hook.ALLOW

            for e in [e for e in IRCD.configuration.excepts if e.name == "spamfilter"]:
                for e_mask in e.mask:
                    if e_mask[0][0] in IRCD.CHANPREFIXES and to_target[0] in IRCD.CHANPREFIXES:
                        # Channel exception.
                        if is_match(e_mask[0].lower(), to_target.lower()):
                            logging.debug(f"Spamfilter match from {client.name} ignored: exception found on channel: {e_mask[0]}")
                            logging.debug(f"Match: {_filter}")
                            return Hook.ALLOW
            allow = spamfilter_match(client, spamfilter, target_cause)

    return Hook.ALLOW if allow else Hook.DENY
    # return target_cause if allow and target in ["a", "c", "p", "n", "t", "N"] else Hook.DENY


def spamfilter_chanmsgcheck(client, channel, msg):
    msg = " ".join(msg)
    return spamfilter_check(client, "c", to_target=channel.name, target_cause=msg)


def spamfilter_usermsgcheck(client, target, msg):
    msg = " ".join(msg)
    return spamfilter_check(client, "p", to_target=target.name, target_cause=msg)


def spamfilter_usernoticecheck(client, target, msg):
    msg = " ".join(msg)
    return spamfilter_check(client, "n", to_target=target.name, target_cause=msg)


def spamfilter_channoticecheck(client, channel, msg):
    msg = " ".join(msg)
    return spamfilter_check(client, "N", to_target=channel.name, target_cause=msg)


def spamfilter_awaycheck(client, awaymsg):
    return spamfilter_check(client, "a", to_target=client.name, target_cause=awaymsg)


def spamfilter_topiccheck(client, channel, newtopic):
    return spamfilter_check(client, "t", to_target=channel.name, target_cause=newtopic)


def cmd_spamfilter(client, recv):
    """View or modify the spamfilter by adding or removing entries.
    Syntax:
-          /SPAMFILTER add|+ <simple|regex> <target(s)> <action> <duration> <reason> <match>
-          /SPAMFILTER del|- <id|match>
-
    Valid targets are:
        * private (p)
        * channel (c)
        * private-notice (n)
        * channel-notice (N)
        * away (a)
        * topic (t)
-
    To view the spamfilter list, use /SPAMFILTER without any arguments.
    """

    targets = "pcnNat"
    actions = ["warn", "block", "kill", "gzline"]

    if len(recv) == 1 and client.has_permission("server:spamfilter:view"):
        Command.do(client, "STATS", "F")
        return IRCD.server_notice(client, f"To view info about removing spamfilter entries, use: /SPAMFILTER del")

    if recv[1] not in ["add", "del", "+", "-"]:
        return IRCD.server_notice(client, "Syntax: SPAMFILTER <add|+|del|-> <simple|regex> <target(s)> <action> <duration> <reason> <match> [id]")

    if recv[1] in ["add", "+"]:
        if not client.has_permission("server:spamfilter:add"):
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
        if len(recv) == 2:
            return IRCD.server_notice(client, "Syntax: SPAMFILTER <add|+> <simple|regex> <target(s)> <action> <duration> <reason> <match>")
        if recv[2] not in ["simple", "regex"]:
            return IRCD.server_notice(client, "Supported spamfilter types are: simple, regex")
        match_type = recv[2]

        if len(recv) == 3:
            return IRCD.server_notice(client, f"Syntax: SPAMFILTER {recv[1]} {match_type} <target(s)> <action> <duration> <reason> <match>")

        for target in recv[3]:
            if target not in targets:
                IRCD.server_notice(client, f"Invalid target: {target}")
                IRCD.server_notice(client, "Supported targets are: p (private), c (channel), n (private-notice), N (channel-notice), a (away), t (topic)")
                IRCD.server_notice(client, "You can chain multiple targets together. Example: pcN")
                return
        targets = recv[3]

        if len(recv) == 4:
            return IRCD.server_notice(client, f"Syntax: SPAMFILTER {recv[1]} {match_type} {targets} <action> <duration> <reason> <match>")

        if recv[4] not in actions:
            IRCD.server_notice(client, f"Invalid action: {recv[4]}")
            IRCD.server_notice(client, f"Supported actions are: {', '.join(actions)}")
            return
        action = recv[4]

        if len(recv) == 5:
            return IRCD.server_notice(client, f"Syntax: SPAMFILTER {recv[1]} {match_type} {targets} {action} <duration> <reason> <match>")

        if action == "gzline":
            if not valid_expire(recv[5]):
                IRCD.server_notice(client, f"Invalid duration for action gzline: {recv[5]}")
                IRCD.server_notice(client, "Examples: 1m, 3d, 24h. Stacking is not supported.")
                return
            duration = valid_expire(recv[5])
        else:
            duration = 0

        if len(recv) < 8:
            return IRCD.server_notice(client, f"Syntax: SPAMFILTER {recv[1]} {match_type} {targets} {action} {duration} <reason> <match>")

        reason = recv[6]
        match = recv[7]

        # Check for possible duplicates.
        if next((s for s in IRCD.configuration.spamfilters if s.match == match), 0):
            return IRCD.server_notice(client, f"Duplicate spamfilter match found: {match}")

        if len(match.replace("*", "")) <= 3:
            return IRCD.server_notice(client, f"Spamfilter match too broad.")

        reason = reason.replace("_", " ")
        s = Spamfilter(match_type, action, duration, match, targets, reason, conf=0)
        s.set_by = client.fullrealhost
        logging.debug(f"Spamfilter object added: {s}")
        snotice_string = f"Spamfilter object added by {client.name} ({client.user.username}@{client.user.realhost}) [{match_type} {action} {targets}: {match}]. Reason: {reason}"
        IRCD.send_snomask(client, "f", snotice_string)

    if recv[1] in ["del", "-"]:
        if not client.has_permission("server:spamfilter:del"):
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
        if len(recv) < 3:
            for obj in IRCD.configuration.spamfilters:
                if obj.conf:
                    continue
                client.sendnumeric(Numeric.RPL_STATSSPAMF, obj.match_type, obj.target, obj.action, obj.duration, obj.active_time(), obj.set_time, obj.set_by, obj.reason, obj.match)
                if obj.conf:
                    client.sendnumeric(Numeric.RPL_TEXT, "This spamfilter is stored in the configuration file and cannot be removed with /SPAMFILTER del")
                else:
                    client.sendnumeric(Numeric.RPL_TEXT, f"To remove this spamfilter entry, use: /SPAMFILTER del {obj.entry_num}")
            return

        for obj in list(IRCD.configuration.spamfilters):
            if obj.entry_num == int(recv[2]) and not obj.conf:
                IRCD.configuration.spamfilters.remove(obj)
                reason = obj.reason.replace("_", " ")
                return IRCD.send_snomask(client, "f",
                                         f"Spamfilter entry removed by {client.name} ({client.user.username}@{client.user.realhost}): "
                                         f"[{obj.match_type}, {obj.action}, {''.join(obj.target)}: {obj.match}]. Reason: {reason}")
        return IRCD.server_notice(client, "Could not find a spamfilter entry with that ID.")


def spamfilter_stats(client):
    for t in IRCD.configuration.spamfilters:
        if not t.set_by:
            t.set_by = IRCD.me.name
        client.sendnumeric(Numeric.RPL_STATSSPAMF, t.match_type, t.target, t.action, t.duration, t.active_time(), t.set_time, t.set_by, t.reason, t.match)


def spamfilter_partcheck(client, channel, reason):
    if spamfilter_check(client, "p", to_target=channel.name, target_cause=reason) == Hook.DENY:
        return client.name


def init(module):
    Hook.add(Hook.PRE_LOCAL_USERMSG, spamfilter_usermsgcheck)
    Hook.add(Hook.PRE_LOCAL_CHANMSG, spamfilter_chanmsgcheck)
    Hook.add(Hook.PRE_LOCAL_USERNOTICE, spamfilter_usernoticecheck)
    Hook.add(Hook.PRE_LOCAL_CHANNOTICE, spamfilter_channoticecheck)
    Hook.add(Hook.PRE_AWAY, spamfilter_awaycheck)
    Hook.add(Hook.PRE_LOCAL_TOPIC, spamfilter_topiccheck)
    Hook.add(Hook.PRE_LOCAL_PART, spamfilter_partcheck)
    # Hook.add(Hook.CAN_KICK, spamfilter_kickreason_check)
    Command.add(module, cmd_spamfilter, "SPAMFILTER", 0, Flag.CMD_OPER)
    Stat.add(module, spamfilter_stats, "F", "View spamfilter entries")
