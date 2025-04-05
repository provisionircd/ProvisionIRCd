import sys

from time import time
from dataclasses import dataclass, field
from typing import ClassVar, Union
from collections.abc import Callable

from handle.core import IRCD, Command
from classes.data import Isupport, Hook, Extban
from modules.ircv3.batch import Batch
from handle.logger import logging


class ChannelList(list):
    def __init__(self, iterable=None):
        super().__init__(iterable or [])

    def append(self, item):
        super().append(item)
        IRCD.channel_by_name[item.name.lower()] = item

    def remove(self, item):
        super().remove(item)
        IRCD.channel_by_name.pop(item.name.lower(), None)


@dataclass(eq=False)
class Channel:
    table: ClassVar[ChannelList] = ChannelList()

    modes_table: ClassVar[list] = []
    name: str = ''
    members: list = field(default_factory=list)
    member_by_client: dict = field(default_factory=dict)  # Dictionary holding Client keys and Member values.
    invites: list = field(default_factory=list)
    modes: str = ''
    membercount: int = 0
    modeparams: list = field(default_factory=list)
    topic: str = ''
    topic_author: str = None
    topic_time: int = 0
    creationtime: int = 0
    local_creationtime: int = 0
    remote_creationtime: int = 0
    List: dict = field(default_factory=dict)

    # This dict keeps track of which users have seen other users on the channel.
    seen_dict: dict = field(default_factory=dict)

    def init_lists(self):
        for mode in IRCD.get_list_modes_str():
            self.List[mode] = []

    def can_join(self, client, key: str):
        """
        Return 0 if the client is allowed to join.
        """
        if any(invite.to == client and invite.override for invite in self.invites) or client.has_permission("channel:override:join"):
            return 0
        for result, callback in Hook.call(Hook.CAN_JOIN, args=(client, self, key)):
            if result != 0:
                return result
        return 0

    def user_can_see_member(self, user, target):
        """ Check if `user` can see `target` on `channel` """

        if user == target or target.server:
            return 1

        if target.is_stealth():
            return 0

        for result, callback in Hook.call(Hook.VISIBLE_ON_CHANNEL, args=(user, target, self)):
            if result == Hook.DENY:
                return 0
        return 1

    def clients(self, client_cap=None, prefix=None) -> list:
        """ Return a filtered list of clients based on capabilities and/or rank requirements. """
        specified_rank = 0
        if prefix:
            membermodes_sorted = self.get_membermodes_sorted()
            prefix_rank_map = {obj.prefix: obj.rank for obj in membermodes_sorted}
            specified_rank = min((prefix_rank_map[pfx] for pfx in prefix if pfx in prefix_rank_map), default=0)

        if client_cap is None and prefix is None:
            return list(self.member_by_client.keys())

        return [
            client for client in self.member_by_client.keys()
            if ((client_cap is None or client.has_capability(client_cap))
                and (prefix is None or 'o' in client.user.modes or self.get_member_rank(client) >= specified_rank))
        ]

    def clients_(self, client_cap=None, prefix=None) -> list:
        specified_rank = 0
        if prefix:
            membermodes_sorted = self.get_membermodes_sorted()
            prefix_rank_map = {obj.prefix: obj.rank for obj in membermodes_sorted}
            specified_rank = min((prefix_rank_map[pfx] for pfx in prefix if pfx in prefix_rank_map), default=0)

        return [c for c in self.member_by_client if (client_cap is None or c.has_capability(client_cap))
                and (prefix is None or 'o' in c.user.modes or self.get_member_rank(c) >= specified_rank)]

    def find_member(self, client):
        return self.member_by_client.get(client, None)

    def get_membermodes_sorted(self, reverse=False, prefix=0, client=None) -> Union[list, str]:
        """
        Get sorted member modes, optionally filtered for a client and formatted.

        Parameters:
        - reverse: Whether to reverse sort order. Reverse to 1 returns from high to low.
        - prefix: If 1, returns a string of prefix characters instead of mode objects
        - client: Optional client to filter modes for (returns only modes the client has)

        Returns:
        - List of sorted ChannelMode objects if prefix=0
        - String of prefix characters if prefix=1
        """

        modes = sorted(
            [cmode for cmode in Channel.modes_table
             if cmode.type == cmode.MEMBER and cmode.prefix and cmode.rank],
            key=lambda c: c.rank,
            reverse=reverse
        )

        if client:
            modes = [m for m in modes if self.client_has_membermodes(client, m.flag)]

        return ''.join(m.prefix for m in modes) if prefix else modes

    def get_modes_of_client_str(self, client) -> str:
        return ''.join(cmode.flag for cmode in self.get_membermodes_sorted() if self.client_has_membermodes(client, cmode.flag))

    def get_member_rank(self, client, get_highest=True):
        membermodes_sorted = self.get_membermodes_sorted(reverse=not get_highest)
        return next((mode.rank for mode in membermodes_sorted
                     if mode.prefix in self.get_membermodes_sorted(client=client, prefix=1)), 0)

    def get_sjoin_prefix_sorted_str(self, client):
        return ''.join(cmode.sjoin_prefix for cmode in self.get_membermodes_sorted() if self.client_has_membermodes(client, cmode.flag))

    def client_has_membermodes(self, client, modes: str) -> bool:
        return bool(member := self.find_member(client)) and any(m in member.modes for m in modes)

    def broadcast(self, client, data):
        IRCD.new_message(client)
        batch_event = not client.uplink.server.synced
        user_can_see_member = self.user_can_see_member
        client_mtags = client.mtags

        for broadcast_to in [c for c in self.member_by_client if c.local and user_can_see_member(c, client)]:
            if batch_event:
                Batch.check_batch_event(mtags=client_mtags, started_by=client, target_client=broadcast_to, event="netjoin")
            broadcast_to.send(client_mtags, data)

    def create_member(self, client):
        if not self.find_member(client):
            member = ChannelMember()
            member.join_time = int(time())
            member.client = client
            self.member_by_client[client] = member
            self.seen_dict[client] = []
            return 1

    def client_has_seen(self, client_a, client_b) -> bool | int:
        """ Returns true if `client_a` has seen `client_b` on this channel. """
        if client_b.server:
            return 1
        return client_b in self.seen_dict[client_a]

    def member_give_modes(self, client, modes: str):
        if not (member := self.find_member(client)) or not modes:
            return
        new_modes = [m for m in modes if m not in member.modes]
        member.modes += ''.join(new_modes)
        if new_modes and (client.local or client.uplink.server.synced):
            # If there are any members on the channel that are not aware of this user,
            # show a join here.
            IRCD.new_message(client)
            for user in [c for c in self.member_by_client if not self.client_has_seen(c, member.client)]:
                self.show_join_message(client.mtags, user, member.client)

    def member_take_modes(self, client, modes: str):
        if (member := self.find_member(client)) and modes:
            member.modes = ''.join(m for m in member.modes if m not in modes)

    def add_param(self, mode, param):
        """ If it already exists, it will update it. """
        if not (pm := next((p for p in self.modeparams if p.mode == mode), None)):
            self.modeparams.append(ChannelmodeParam(mode=mode, param=param))
        else:
            pm.param = param

    def del_param(self, mode: str):
        self.modeparams = [p for p in self.modeparams if p.mode != mode]

    def get_param(self, mode: str):
        return next((p.param for p in self.modeparams if p.mode == mode), 0)

    def add_invite(self, to, by, override: int = 0):
        if not (inv := self.get_invite(to)):
            inv = Invite()
        else:
            self.invites.remove(inv)
        inv.to, inv.by, inv.override, inv.when = to, by, override, int(time())
        self.invites.append(inv)

    def del_invite(self, invite):
        if invite in self.invites:
            self.invites.remove(invite)

    def get_invite(self, to):
        return next((inv for inv in self.invites if inv.to == to), 0)

    def mask_in_list(self, mask, _list):
        return any(mask == entry.mask for entry in _list)

    def check_match(self, client, match_type, mask=None):
        if match_type not in self.List:
            return 0

        for b in self.List[match_type]:
            check_mask = b.mask if not mask else mask

            if IRCD.client_match_mask(client, check_mask):
                return 1

            if len(check_mask.split(':')) < 2:
                continue

            try:
                for extban in Extban.table:
                    if extban.is_match(client, self, check_mask):
                        return 1
            except Exception as ex:
                logging.exception(ex)
                return 0

        return 0

    def is_banned(self, client, mask=None):
        if client.has_permission("channel:override:join:ban") or any(inv.to == client and inv.override for inv in self.invites):
            return 0
        return self.check_match(client, 'b', mask)

    def is_exempt(self, client):
        return self.check_match(client, 'e')

    def is_invex(self, client):
        return self.check_match(client, 'I')

    def level(self, client):
        if client.server or client.is_uline():
            return 1000
        umode_levels = {'q': 5, 'a': 4, 'o': 3, 'h': 2, 'v': 1}
        return next((umode_levels[m] for m in umode_levels if self.client_has_membermodes(client, m)), 0)

    def add_to_list(self, client, mask, _list, setter=None, timestamp=None):
        if next((e for e in _list if mask == e.mask), 0):
            return 0
        _list.append(ListEntry(mask=mask, set_by=setter or client.name, set_time=int(timestamp or time())))
        return 1

    def remove_from_list(self, mask, _list):
        masks = [mask] if not isinstance(mask, list) else mask
        for mask in masks:
            if entry := next((e for e in _list if mask == e.mask), None):
                _list.remove(entry)
                return entry.mask

    def remove_client(self, client):
        self.membercount -= 1
        if member := self.find_member(client):
            self.member_by_client.pop(member.client, None)
        else:
            logging.debug(f"Unable to remove {client.name} (uplink={client.uplink.name}) from channel {self.name}: member not found")

        for c in self.seen_dict:
            if client in self.seen_dict[c]:
                self.seen_dict[c].remove(client)

        if self.membercount == 0:
            IRCD.destroy_channel(IRCD.me, self)

    def do_part(self, client, reason: str = ''):
        reason = reason[:128]
        data = f":{client.fullmask} PART {self.name}{' :' + reason if reason else ''}"
        for member_client in (c for c in self.member_by_client if c.local):
            if not self.user_can_see_member(member_client, client) or not self.client_has_seen(member_client, client):
                continue
            member_client.send(client.mtags, data)

        if self.name[0] != '&':
            IRCD.send_to_servers(client, client.mtags, f":{client.id} PART {self.name}{' :' + reason if reason else ''}")

        self.remove_client(client)

        if (((client.local and client.registered) or (not client.local and client.uplink.server.synced))
                and not client.is_uline() and not client.is_service()):
            event = "LOCAL_PART" if client.local else "REMOTE_PART"
            IRCD.log(client, "info", "part", event,
                     f"*** {client.name} ({client.user.username}@{client.user.realhost}) has left channel {self.name}", sync=0)

    def show_join_message(self, mtags, client, new_user) -> None:
        """ Show `new_user` join message to `client` """
        if new_user.is_stealth() or self.client_has_seen(client, new_user):
            # Don't show the join message if `new_user` is stealthed
            # or if `client` has already seen `new_user` in the channel.
            return

        if not new_user.uplink.server.synced:
            Batch.check_batch_event(mtags=mtags, started_by=new_user.uplink, target_client=client, event="netjoin")

        join_message = f":{new_user.fullmask} JOIN {self.name}"
        if client.has_capability("extended-join"):
            join_message += f" {new_user.user.account} :{new_user.info}"
        client.send(mtags, join_message)
        if not self.client_has_seen(client, new_user):
            self.seen_dict[client].append(new_user)

    def do_join(self, mtags, client):
        self.membercount += 1
        if not self.find_member(client):
            self.create_member(client)

        if invite := self.get_invite(client):
            self.del_invite(invite)

        for member_client in (c for c in self.member_by_client if c.local):
            if not self.user_can_see_member(member_client, client):
                continue
            self.show_join_message(mtags, member_client, client)

        if self.membercount == 1 and client.local:
            if self.name[0] != '+':
                self.member_give_modes(client, 'o')

        if self.name[0] != '&' and IRCD.get_clients(local=1, server=1):
            prefix = self.get_sjoin_prefix_sorted_str(client)
            IRCD.send_to_servers(client, mtags, f":{client.uplink.id} SJOIN {self.creationtime} {self.name} :{prefix}{client.id}")

        if self.membercount == 1 and client.local:
            if modes_on_join := IRCD.get_setting("modes-on-join"):
                Command.do(IRCD.me, "MODE", self.name, *modes_on_join.split(), str(self.creationtime))

        if ((client.local and client.registered) or (not client.local and client.uplink.server.synced)
                and not client.is_uline() and not client.is_service()):
            event = "LOCAL_JOIN" if client.local else "REMOTE_JOIN"
            IRCD.log(client, "info", "join", event,
                     f"*** {client.name} ({client.user.username}@{client.user.realhost}) has joined channel {self.name}", sync=0)


@dataclass
class Channelmode:
    table: ClassVar[list] = Channel.modes_table
    MEMBER: ClassVar[int] = 1
    LISTMODE: ClassVar[int] = 2
    CHK_PARAM: ClassVar[int] = 3
    CHK_ACCESS: ClassVar[int] = 4

    flag: str = ''
    prefix: str = ''
    rank: int = None
    type: int = 0
    level: int = 2
    sjoin_prefix: str = ''
    paramcount: int = 0
    unset_with_param: int = 0
    is_global: int = 1

    """
    is_ok() callable return values:
    1   - Allows the channel mode.
    0   - Deny the channel mode. Returns feedback.
    -1  - Denies the channel mode silently. Moduels are responsible to provide feedback.

    Booleans, truthy and falsy are converted to integers.
    """
    is_ok: Callable = None

    get_param: callable = lambda p: None
    conv_param: callable = lambda p: p
    module: "Module" = None  # noqa: F821
    desc: str = ''
    param_help: str = ''

    @staticmethod
    def add(module, cmode):
        if exists := next((cm for cm in Channel.modes_table if cm.flag == cmode.flag), 0):
            logging.error(f"[{module.name}] Attempting to add channel mode '{cmode.flag}' "
                          f"but it has already been added before by {exists.module.name}")
            if IRCD.rehashing:
                sys.exit()
            return
        cmode.module = module
        Channel.modes_table.append(cmode)

        Isupport.add("CHANMODES", IRCD.get_chmodes_str_categorized(), server_isupport=1)

        if prefix_sorted := sorted([m for m in Channel.modes_table if m.prefix and m.rank and m.type == Channelmode.MEMBER],
                                   key=lambda c: c.rank, reverse=True):
            Isupport.add("PREFIX", f"({''.join(cm.flag for cm in prefix_sorted)}){''.join(cm.prefix for cm in prefix_sorted)}",
                         server_isupport=1)

        if not hasattr(cmode, "is_ok") or not cmode.is_ok:
            """
            is_ok() callable return values:
            1   - Allows the channel mode.
            0   - Deny the channel mode. Returns feedback.
            -1  - Denies the channel mode silently. Moduels are responsible to provide feedback.
            
            Booleans, truthy and falsy are converted to integers.
            """
            cmode.is_ok = Channelmode.allow_halfop

    @staticmethod
    def add_generic(flag: str, cat=4):
        cmode = Channelmode(module=None, flag=flag, is_ok=Channelmode.allow_none)
        if cat in [2, 3]:
            cmode.paramcount, cmode.conv_param = 1, lambda x: x
        if cat == 2:
            cmode.unset_with_param = 1
        logging.debug(f"Adding generic support for missing channel mode: {flag}")
        Channelmode.add(module=None, cmode=cmode)

    @staticmethod
    def allow_halfop(client, channel, *args):
        return channel.client_has_membermodes(client, "hoaq") or client.has_permission("channel:override:mode")

    @staticmethod
    def allow_chanop(client, channel, *args):
        return channel.client_has_membermodes(client, "oaq") or client.has_permission("channel:override:mode")

    @staticmethod
    def allow_chanadmin(client, channel, *args):
        return channel.client_has_membermodes(client, "aq") or client.has_permission("channel:override:mode")

    @staticmethod
    def allow_chanowner(client, channel, *args):
        return channel.client_has_membermodes(client, 'q') or client.has_permission("channel:override:mode")

    @staticmethod
    def allow_opers(client, channel, *args):
        return 'o' in client.user.modes

    @staticmethod
    def allow_none(client, channel, *args):
        return client.server or not client.local

    def level_help_string(self):
        levels = {
            Channelmode.allow_halfop: "+h",
            Channelmode.allow_chanop: "+o",
            Channelmode.allow_chanadmin: "+a",
            Channelmode.allow_chanowner: "+q",
            Channelmode.allow_opers: "IRCops only",
            Channelmode.allow_none: "Settable by servers",
            2: "+h", 3: "+o", 4: "+a", 5: "+q",
            6: "IRCops only", 7: "Settable by servers"
        }
        return levels.get(self.is_ok) or levels.get(self.level, "Unknown")

    def is_member_type(self):
        return self.type == Channelmode.MEMBER

    def is_listmode_type(self):
        return self.type == Channelmode.LISTMODE


@dataclass
class ChannelmodeParam:
    mode: str = ''
    param: str = ''


@dataclass
class ChannelMember:
    client = None
    modes: str = ''


@dataclass
class ListEntry:
    mask: str = ''
    set_by: str = ''
    set_time: int = 0


@dataclass
class Invite:
    table: ClassVar[list] = []
    by = None
    to = None
    when: int = 0
