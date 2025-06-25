"""
batch message tag
"""
import logging
import random
import string

from handle.core import IRCD, Capability
from modules.ircv3.messagetags import MessageTag


class Batch:
    pool = []

    def __init__(self, started_by, batch_type=None, additional_data=''):
        self.label = ''.join((random.choice(string.ascii_letters + string.digits) for x in range(10)))
        self.tag = MessageTag.find_tag("batch")(value=self.label)
        # We need to be able to refer to whoever started this batch.
        # Also keep in mind that servers can start batches too, for example with netjoin and netsplit.
        self.started_by = started_by

        self.batch_type = batch_type
        self.additional_data = additional_data
        self.users = []
        Batch.pool.append(self)
        # self.start()

    @staticmethod
    def create_new(started_by, batch_type=None, additional_data=''):
        batch = Batch(started_by=started_by, batch_type=batch_type, additional_data=additional_data)
        return batch

    @staticmethod
    def check_batch_event(mtags, started_by, target_client, event):
        """
        :param mtags:           Message tags list to add BATCH tag to.
        :param started_by:      Client that started this batch.
        :param target_client:   Target client to show this BATCH event to.
        :param event:           Batch event: netjoin or netsplit.
        """

        for batch in Batch.pool:
            if batch.started_by in [started_by, started_by.uplink, started_by.direction] and batch.batch_type == event:
                if (batch.tag.name, batch.tag.value) not in [(t.name, t.value) for t in mtags]:
                    mtags[0:0] = [batch.tag]
                if target_client not in batch.users:
                    batch.announce_to(target_client)

    # def start(self, batch_id=None):
    #     for user in [u for u in self.users if u.has_capability("batch")]:
    #         data = (f":{IRCD.me.name} BATCH +{self.label}{' ' + self.batch_type if self.batch_type else ''} "
    #                 f"{' ' + self.additional_data if self.additional_data else ''}")
    #         user.send([], data)
    #     Batch.pool.append(self)

    def end(self, batch_id=None):
        if self in Batch.pool:
            Batch.pool.remove(self)
        for user in self.users:
            user.send([], f":{IRCD.me.name} BATCH -{self.label}")
        for client in IRCD.get_clients():
            for tag in list(client.mtags):
                if not isinstance(tag, MessageTag):
                    logging.exception(f"Tag object must be MessageTag, not {type(tag)}")
                    continue
                if tag.name == "batch" and tag.value == self.label:
                    client.mtags.remove(tag)
        self.users = []

    def announce_to(self, client):
        if not self.tag.is_visible_to(client):
            return
        if client not in self.users:
            data = f":{IRCD.me.name} BATCH +{self.label} {self.batch_type}{' ' + self.additional_data if self.additional_data else ''}"
            client.send([tag for tag in client.mtags if tag.name == "label"], data)
            self.users.append(client)
            client.mtags.append(self.tag)

    @staticmethod
    def find_batch_by(started_by):
        return next((batch for batch in Batch.pool if batch.started_by == started_by), 0)

    def __repr__(self):
        return f"<Batch '{self.label} [{self.started_by.name}]'>"


class BatchTag(MessageTag):
    name = "batch"
    local = 1

    def __init__(self, value):
        super().__init__(name=BatchTag.name, value=value)

    def is_visible_to(self, to_user):
        return super().is_visible_to(to_user) and to_user.has_capability("batch")


def post_load(module):
    Capability.add("batch")
    MessageTag.add(BatchTag)
