import re

from handle.core import MessageTag, Capability, Hook, IRCD, Batch
from handle.logger import logging


class Currentcmd:
    client = None
    label = None
    buffer = []
    labeltag = None


class LabelTag(MessageTag):
    name = "label"
    local = 1

    def __init__(self, value):
        super().__init__(name=LabelTag.name, value=value)
        self.client = None

    def is_visible_to(self, to_client):
        return (super().is_visible_to(to_client) or (to_client.has_capability("labeled-response")) and to_client.has_capability("batch")) and to_client == self.client


def ircv3_label_packet(from_client, to_client, intended_to, data: list):
    if intended_to == Currentcmd.client and not intended_to.is_killed() and intended_to.registered:
        Currentcmd.buffer.append(' '.join(data))
        del data[:]


def ircv3_label_pre_command(client, recv):
    for tag in client.recv_mtags:
        if tag.name == LabelTag.name and tag.value:
            if not re.match(r"^\w{1,32}$", tag.value):
                logging.warning(f"Invalid label tag value: {tag.value}")
                return

            Currentcmd.client = client
            Currentcmd.label = tag.value
            tag.client = client
            Currentcmd.labeltag = tag


def ircv3_label_post_command(client, trigger, recv):
    # This is where we will send the buffer, if any.
    if Currentcmd.client == client:
        Currentcmd.client = None
        if Currentcmd.labeltag not in client.mtags:
            """
            Labeltag object was saved in case some module clears the mtags list.
            """
            client.mtags[0:0] = [Currentcmd.labeltag]
        batch = None
        if len(Currentcmd.buffer) == 0:
            data = f":{IRCD.me.name} ACK"
            client.send([Currentcmd.labeltag], data)
        else:
            if len(Currentcmd.buffer) > 1 and client.has_capability("batch"):
                batch = Batch.create_new(started_by=client, batch_type="labeled-response")
                batch.announce_to(client)
                """ Now send the rest as batch, and remove label tag. """
                for tag in client.mtags:
                    if tag.name == LabelTag.name and tag.value == Currentcmd.label:
                        client.mtags.remove(tag)
                        break
                client.mtags.append(batch.tag)

            for line in Currentcmd.buffer:
                client.send(client.mtags, line, call_hook=0)

        if batch:
            batch.end()

        Currentcmd.label = None
        Currentcmd.buffer = []


def init(module):
    Capability.add("labeled-response")
    Hook.add(Hook.POST_COMMAND, ircv3_label_post_command)
    Hook.add(Hook.PRE_COMMAND, ircv3_label_pre_command)
    Hook.add(Hook.PACKET, ircv3_label_packet)
    MessageTag.add(LabelTag)
