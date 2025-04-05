"""
provides spamfilter capabilities
"""

import logging
import re
from time import time

from handle.core import IRCD, Command, Numeric, Flag, Hook, Stat
from modules.m_tkl import Tkl
from handle.functions import valid_expire, is_match
from handle.validate_conf import Spamfilter


def is_valid_regex(pattern):
    try:
        return re.compile(pattern) if isinstance(pattern, str) else 0
    except re.error:
        return 0


def handle_spamfilter_match(client, spamfilter, target_cause, event=None):
    msg = (f"Spamfilter match by {client.name} ({client.user.username}@{client.user.realhost})"
           f"matching {spamfilter.match} [{target_cause}] (action: {spamfilter.action})")
    IRCD.log(client, "warn", "spamfilter", "SPAMFILTER_MATCH", msg, sync=1)

    reason = spamfilter.reason.replace('_', ' ')

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
        Tkl.add(client, 'Z', '*', client.ip, bantypes='', set_by=IRCD.me.name,
                expire=int(time()) + spamfilter.duration, set_time=int(time()), reason=f"Spamfilter match: {reason}")
        return 0

    return 1


def check_spamfilter(client, target_type, to_target, message, event=None):
    if client.has_permission("immune:spamfilter") or IRCD.is_except_client("spamfilter", client):
        return Hook.ALLOW

    for spamfilter in [s for s in IRCD.configuration.spamfilters if target_type in s.target]:
        pattern = spamfilter.match

        is_matched = False
        if spamfilter.match_type == "simple":
            is_matched = is_match(pattern.lower(), message.lower())
        elif spamfilter.match_type == "regex":
            is_matched = bool(re.search(pattern, message))

        if is_matched:
            for exempt in [e for e in IRCD.configuration.excepts if e.name == "spamfilter"]:
                for exempt_mask in exempt.mask.mask:
                    if (exempt_mask[0][0] in IRCD.CHANPREFIXES
                            and to_target[0] in IRCD.CHANPREFIXES
                            and is_match(exempt_mask[0].lower(), to_target.lower())):
                        logging.debug(f"Spamfilter match from {client.name} ignored: exception found on channel: {exempt_mask[0]}")
                        logging.debug(f"Match: {pattern}")
                        return Hook.ALLOW

            if not handle_spamfilter_match(client, spamfilter, message, event):
                return Hook.DENY

    return Hook.ALLOW


def spamfilter_message_check(client, target, msg, target_type, prefix=None, event=None):
    if isinstance(msg, list):
        msg = ' '.join(msg)

    try:
        to_target = target.name
    except (AttributeError, TypeError):
        to_target = target

    return check_spamfilter(client, target_type, to_target, msg, event=event)


def check_privmsg(client, target, msg):
    return spamfilter_message_check(client, target, msg, 'p')


def check_notice(client, target, msg):
    return spamfilter_message_check(client, target, msg, 'n')


def check_chan_msg(client, channel, msg, prefix):
    return spamfilter_message_check(client, channel, msg, 'c')


def check_chan_notice(client, channel, msg, prefix):
    return spamfilter_message_check(client, channel, msg, 'N')


def check_away(client, away_msg):
    return spamfilter_message_check(client, client.name, away_msg, 'a')


def check_topic(client, channel, topic):
    return spamfilter_message_check(client, channel, topic, 't')


def check_part(client, channel, reason):
    result = spamfilter_message_check(client, channel, reason, 'P', event="quit")
    return client.name if result == Hook.DENY else None


def check_quit(client, reason):
    """Check quit reasons against spamfilter.

    Unlike part messages which have a channel context, quit messages
    are server-wide. We use the client's name as the target.

    Args:
        client: The client quitting
        reason: The quit reason

    Returns:
        client.name if the quit is denied, otherwise None.
    """
    result = spamfilter_message_check(client, client.name, reason, 'Q')
    return client.name if result == Hook.DENY else None


def cmd_spamfilter(client, recv):
    """View or modify the spamfilter by adding or removing entries.
    Syntax:
-          /SPAMFILTER add|+ <simple|regex> <target(s)> <action> <duration> <reason> <match>
-          /SPAMFILTER del|- <id|match>
-
    You can combine multiple targets as a single string.
    Valid targets are:
        * private (p)
        * channel (c)
        * private-notice (n)
        * channel-notice (N)
        * away (a)
        * topic (t)
        * part reason (P)
        * quit reason (Q)
-
    When specifying the <reason>, replace spaces with underscores (_).
-
    To view the spamfilter list, use /SPAMFILTER without any arguments.
    """

    valid_targets = "pcnNat"
    valid_actions = ["warn", "block", "kill", "gzline"]

    if len(recv) == 1:
        if not client.has_permission("server:spamfilter:view"):
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

        Command.do(client, "STATS", 'F')
        if client.has_permission("server:spamfilter:del"):
            IRCD.server_notice(client, "To view info about removing spamfilter entries, use: /SPAMFILTER del")
        return

    # Invalid command
    if recv[1] not in ["add", "del", '+', '-']:
        return IRCD.server_notice(client, "Syntax: SPAMFILTER <add|+|del|-> <simple|regex>"
                                          "<target(s)> <action> <duration> <reason> <match> [id]")

    # Handle add command
    if recv[1] in ["add", '+']:
        handle_spamfilter_add(client, recv)

    # Handle delete command
    if recv[1] in ["del", '-']:
        handle_spamfilter_del(client, recv)


def handle_spamfilter_add(client, recv):
    valid_targets = "pcnNat"
    valid_actions = ["warn", "block", "kill", "gzline"]

    if not client.has_permission("server:spamfilter:add"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if len(recv) < 8:
        cmd_parts = [recv[1]]
        if len(recv) > 2:
            cmd_parts.append(recv[2])
        if len(recv) > 3:
            cmd_parts.append(recv[3])
        if len(recv) > 4:
            cmd_parts.append(recv[4])
        if len(recv) > 5:
            cmd_parts.append(recv[5])

        syntax = f"Syntax: SPAMFILTER {' '.join(cmd_parts)}"

        if len(recv) == 2:
            return IRCD.server_notice(client, f"Syntax: SPAMFILTER {recv[1]} <simple|regex> <target(s)>"
                                              f"<action> <duration> <reason> <match>")

        if len(recv) == 3:
            if recv[2] not in ["simple", "regex"]:
                return IRCD.server_notice(client, "Supported spamfilter types are: simple, regex")
            return IRCD.server_notice(client, f"{syntax} <target(s)> <action> <duration> <reason> <match>")

        if len(recv) == 4:
            return IRCD.server_notice(client, f"{syntax} <action> <duration> <reason> <match>")

        if len(recv) == 5:
            return IRCD.server_notice(client, f"{syntax} <duration> <reason> <match>")

        if len(recv) == 6:
            return IRCD.server_notice(client, f"{syntax} <reason> <match>")

        if len(recv) == 7:
            return IRCD.server_notice(client, f"{syntax} <match>")

    match_type = recv[2]
    if match_type not in ["simple", "regex"]:
        return IRCD.server_notice(client, "Supported spamfilter types are: simple, regex")

    targets = recv[3]
    for target in targets:
        if target not in valid_targets:
            IRCD.server_notice(client, f"Invalid target: {target}")
            IRCD.server_notice(client, "Supported targets are: p (private), c (channel), n (private-notice), N (channel-notice),"
                                       "a (away), t (topic), P (part reason), q (quit reason)")
            IRCD.server_notice(client, "You can chain multiple targets together. Example: pcN")
            return

    action = recv[4]
    if action not in valid_actions:
        IRCD.server_notice(client, f"Invalid action: {action}")
        IRCD.server_notice(client, f"Supported actions are: {', '.join(valid_actions)}")
        return

    if action == "gzline":
        duration = valid_expire(recv[5])
        if not duration:
            IRCD.server_notice(client, f"Invalid duration for action gzline: {recv[5]}")
            IRCD.server_notice(client, "Examples: 1m, 3d, 24h. Stacking is not supported.")
            return
    else:
        duration = 0

    reason = recv[6]
    match = ' '.join(recv[7:])

    if next((s for s in IRCD.configuration.spamfilters if s.match == match), 0):
        return IRCD.server_notice(client, f"Duplicate spamfilter match found: {match}")

    if len(match.replace('*', '')) <= 3:
        return IRCD.server_notice(client, "Spamfilter match too broad.")

    if match_type == "regex" and not is_valid_regex(match):
        return IRCD.server_notice(client, f"Invalid regex pattern: {match}")

    reason_formatted = reason.replace('_', ' ')
    spamfilter = Spamfilter(match_type, action, duration, match, targets, reason_formatted, conf_file=None, conf=0)
    spamfilter.set_by = client.fullrealhost

    msg = (f"Spamfilter object added by {client.name} ({client.user.username}@{client.user.realhost})"
           f"[{match_type} {action} {targets}: {match}]. Reason: {reason_formatted}")
    IRCD.log(client, "info", "spamfilter", "SPAMFILTER_ADD", msg, sync=1)
    IRCD.server_notice(client, f"Spamfilter added successfully: {match}")


def handle_spamfilter_del(client, recv):
    if not client.has_permission("server:spamfilter:del"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if len(recv) < 3:
        non_conf_filters = [s for s in IRCD.configuration.spamfilters if not s.conf]
        if not non_conf_filters:
            return client.sendnumeric(Numeric.RPL_TEXT, "No entries found to be removed.")

        for spamfilter in non_conf_filters:
            client.sendnumeric(Numeric.RPL_STATSSPAMF, spamfilter.match_type, spamfilter.target,
                               spamfilter.action, spamfilter.duration,
                               spamfilter.active_time(), spamfilter.set_time,
                               spamfilter.set_by, spamfilter.reason,
                               spamfilter.match)

            if spamfilter.conf:
                client.sendnumeric(Numeric.RPL_TEXT, "This spamfilter is stored in the configuration file"
                                                     "and cannot be removed with /SPAMFILTER del")
            else:
                client.sendnumeric(Numeric.RPL_TEXT, f"To remove this spamfilter entry, use: /SPAMFILTER del {spamfilter.entry_num}")
        return

    try:
        filter_id = int(recv[2])
        for spamfilter in list(IRCD.configuration.spamfilters):
            if spamfilter.entry_num == filter_id and not spamfilter.conf:
                IRCD.configuration.spamfilters.remove(spamfilter)
                reason = spamfilter.reason.replace('_', ' ')
                msg = (f"Spamfilter entry removed by {client.name} ({client.user.username}@{client.user.realhost}):"
                       f"[{spamfilter.match_type}, {spamfilter.action} {''.join(spamfilter.target)}: {spamfilter.match}]. "
                       f"Reason: {reason}")
                IRCD.log(client, "info", "spamfilter", "SPAMFILTER_DEL", msg, sync=1)
                IRCD.server_notice(client, f"Spamfilter entry {filter_id} removed successfully")
                return

        IRCD.server_notice(client, "Could not find a spamfilter entry with that ID.")
    except ValueError:
        IRCD.server_notice(client, "Invalid filter ID. Use a numeric ID.")


def spamfilter_stats(client):
    if not client.has_permission("server:spamfilter:view"):
        client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
        return -1

    for f in IRCD.configuration.spamfilters:
        if not f.set_by:
            f.set_by = IRCD.me.name
        client.sendnumeric(Numeric.RPL_STATSSPAMF, f.match_type, f.target, f.action, f.duration,
                           f.active_time(), f.set_time, f.set_by, f.reason, f.match)


def init(module):
    Hook.add(Hook.PRE_LOCAL_USERMSG, check_privmsg)
    Hook.add(Hook.PRE_LOCAL_CHANMSG, check_chan_msg)
    Hook.add(Hook.PRE_LOCAL_USERNOTICE, check_notice)
    Hook.add(Hook.PRE_LOCAL_CHANNOTICE, check_chan_notice)
    Hook.add(Hook.PRE_AWAY, check_away)
    Hook.add(Hook.PRE_LOCAL_TOPIC, check_topic)
    Hook.add(Hook.PRE_LOCAL_PART, check_part)
    Hook.add(Hook.PRE_LOCAL_QUIT, check_quit)
    # Hook.add(Hook.CAN_KICK, spamfilter_kickreason_check)
    Command.add(module, cmd_spamfilter, "SPAMFILTER", 0, Flag.CMD_OPER)
    Stat.add(module, spamfilter_stats, 'F', "View spamfilter entries")
