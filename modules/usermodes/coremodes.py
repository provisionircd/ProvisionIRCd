"""
core user modes and snomasks
"""

from handle.core import Usermode, Snomask, Numeric, Hook
from handle.logger import logging


def umode_q_is_ok(client):
    if client.has_permission("self:protected") or 'q' in client.user.modes:
        return 1
    if client.user.oper:
        client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
    return 0


def umode_t_is_ok(client):
    if not client.local or 't' in client.user.modes:
        return 1
    return 0


def umode_x_unset(client, target, modebuf, mode):
    """ Mode 't' cannot be set without 'x'. """
    if mode == 'x' and 't' in target.user.modes:
        modebuf.append('t')


def umode_t_changed(client, target, oldmodes, newmodes):
    modes_unset = set(oldmodes).difference(newmodes)

    if 't' in modes_unset and 'x' in newmodes:
        """ Usermode 't' unset. Setting cloakhost. """
        target.set_host(host=target.user.cloakhost)


def umode_x_changed(client, target, oldmodes, newmodes):
    modes_set = set(newmodes).difference(oldmodes)
    modes_unset = set(oldmodes).difference(newmodes)

    if 'x' in modes_set:
        target.set_host(host=target.user.cloakhost)

    elif 'x' in modes_unset:
        target.set_host(host=target.user.host)


def init(module):
    # Params: mode flag, is_global (will be synced to servers), unset_on_deoper bool, can_set method, desc
    Usermode.add(module, 'i', 1, 0, Usermode.allow_all, "User does not show up in outside /WHO")
    Usermode.add(module, 'o', 1, 1, Usermode.allow_opers, "Marks the user as an IRC Operator")
    Usermode.add(module, 'q', 1, 1, umode_q_is_ok, "Protected on all channels")
    Usermode.add(module, 'r', 1, 0, Usermode.allow_all, "Identifies the nick as being logged in")
    Usermode.add(module, 's', 1, 1, Usermode.allow_opers, "Can receive server notices")
    Usermode.add(module, 't', 1, 0, umode_t_is_ok, "User is using a vHost")
    Usermode.add(module, 'x', 1, 0, Usermode.allow_all, "Hides real host with cloaked host")
    Usermode.add(module, 'z', 1, 0, Usermode.allow_all, "User is using a secure connection")
    Usermode.add(module, 'H', 1, 1, Usermode.allow_opers, "Hide IRCop status")
    Usermode.add(module, 'S', 1, 0, Usermode.allow_none, "Marks the client as a network service")

    Snomask.add(module, 'c', 0, "Can read local connect/disconnect notices")
    Snomask.add(module, 'f', 1, "See excess flood alerts")
    Snomask.add(module, 'j', 0, "See join, part, and kick messages")
    Snomask.add(module, 'k', 0, "View kill notices")
    Snomask.add(module, 'n', 0, "Can see local nick changes")
    Snomask.add(module, 'o', 1, "See oper-up notices and oper override notices")
    Snomask.add(module, 's', 0, "General server notices")
    Snomask.add(module, 'C', 0, "Can read global connect/disconnect notices")
    Snomask.add(module, 'F', 1, "View spamfilter matches")
    Snomask.add(module, 'G', 0, "View TKL usages")
    Snomask.add(module, 'L', 0, "View server notices about links")
    Snomask.add(module, 'N', 0, "Can see remote nick changes")
    Snomask.add(module, 'Q', 1, "View Q:line rejections")
    Snomask.add(module, 'S', 0, "Can see /sanick, /sajoin, and /sapart usage")
    Hook.add(Hook.UMODE_CHANGE, umode_t_changed)
    Hook.add(Hook.UMODE_CHANGE, umode_x_changed)
    Hook.add(Hook.UMODE_UNSET, umode_x_unset)
