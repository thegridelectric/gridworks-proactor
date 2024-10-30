# ruff: noqa: PLR2004, ERA001
from typing import Type

import pytest

from gwproactor.links import StateName
from gwproactor_test.tree_comm_test_helper import TreeCommTestHelper
from gwproactor_test.wait import await_for


@pytest.mark.asyncio
class ProactorTreeCommBasicTests:
    CTH: Type[TreeCommTestHelper]

    async def test_tree_no_parent(self) -> None:
        async with self.CTH() as h:
            # add child 1
            h.add_child()
            child1 = h.child1
            stats1 = child1.stats
            stats1to2 = stats1.link(child1.downstream_client)
            stats1toAtn = stats1.link(child1.upstream_client)
            counts1to2 = stats1to2.comm_event_counts
            counts1toAtn = stats1toAtn.comm_event_counts
            link1to2 = child1.links.link(child1.downstream_client)
            link1toAtn = child1.links.link(child1.upstream_client)
            assert stats1.num_received == 0
            assert link1to2.state == StateName.not_started
            assert link1toAtn.state == StateName.not_started

            # start child 1
            h.start_child1()
            await await_for(
                lambda: link1to2.active_for_send() and link1toAtn.active_for_send(),
                1,
                "ERROR waiting child1 links to be active_for_send",
                err_str_f=h.summary_str,
            )
            assert link1to2.state == StateName.awaiting_peer
            assert link1toAtn.state == StateName.awaiting_peer
            assert counts1to2["gridworks.event.comm.mqtt.connect"] == 1
            assert counts1to2["gridworks.event.comm.mqtt.fully.subscribed"] == 1
            assert len(stats1to2.comm_events) == 2
            assert counts1toAtn["gridworks.event.comm.mqtt.connect"] == 1
            assert counts1toAtn["gridworks.event.comm.mqtt.fully.subscribed"] == 1
            assert len(stats1toAtn.comm_events) == 2

            # add child 2
            h.add_child2()
            child2 = h.child2
            stats2 = child2.stats
            stats2to1 = stats2.link(child2.upstream_client)
            counts2to1 = stats2to1.comm_event_counts
            link2to1 = child2.links.link(child2.upstream_client)
            assert stats2.num_received == 0
            assert link2to1.state == StateName.not_started

            # start child 2
            h.start_child2()
            await await_for(
                lambda: link1to2.active() and link2to1.active(),
                1,
                "ERROR waiting child2 links to be active",
                err_str_f=h.summary_str,
            )
            assert link1to2.state == StateName.active
            assert link2to1.state == StateName.active
            assert counts1to2["gridworks.event.comm.peer.active"] == 1
            assert len(stats1to2.comm_events) == 3
            assert counts2to1["gridworks.event.comm.peer.active"] == 1
            assert counts2to1["gridworks.event.comm.mqtt.connect"] == 1
            assert counts2to1["gridworks.event.comm.mqtt.fully.subscribed"] == 1
            assert len(stats2to1.comm_events) == 3

    async def test_tree_message_exchange(self) -> None:
        async with self.CTH(
            start_child1=True,
            start_child2=True,
        ) as h:
            child1 = h.child
            stats1 = child1.stats.link(child1.downstream_client)
            link1to2 = child1.links.link(child1.downstream_client)
            link1toAtn = child1.links.link(child1.upstream_client)

            child2 = h.child2
            stats2 = child2.stats.link(child2.upstream_client)
            link2to1 = child2.links.link(child2.upstream_client)

            # Wait for children to connect
            await await_for(
                lambda: link1to2.active()
                and link2to1.active()
                and link1toAtn.active_for_send(),
                1,
                "ERROR waiting children to connect",
                err_str_f=h.summary_str,
            )

            # exchange messages
            assert stats2.num_received_by_type["gridworks.dummy.set.relay"] == 0
            assert stats2.num_received_by_type["gridworks.dummy.report.relay"] == 0
            relay_name = "scada2.relay1"
            child1.set_relay(relay_name, True)

            # wait for response to be received
            await await_for(
                lambda: stats1.num_received_by_type["gridworks.dummy.report.relay"]
                == 1,
                1,
                "ERROR waiting child1 to receive relay report from child2",
                err_str_f=h.summary_str,
            )
            assert stats2.num_received_by_type["gridworks.dummy.set.relay"] == 1
            assert child1.relays == {relay_name: True}
            assert child2.relays == {relay_name: True}
            assert child1.relay_change_mimatches == 0

    async def test_basic_comm_child_first(self) -> None:
        async with self.CTH(add_child=True, add_parent=True) as h:
            assert h is not None
            # # unstarted child, parent
            # # start child
            # # start parent
            # # wait for link to go active
            # # wait for all events to be acked
            # # Tell client we lost comm.
            # # Wait for reconnect
            # # wait for all events to be acked

    @pytest.mark.asyncio
    async def test_tree_basic_parent_comm_loss(self) -> None:
        async with self.CTH(add_child=True, add_parent=True, verbose=False) as h:
            assert h is not None
            # # unstarted child, parent
            # # start child, parent
            # # wait for all events to be acked
            # # Tell *child* client we lost comm.
            # # Wait for reconnect
            # # wait for all events to be acked
            # # Tell *parent* client we lost comm.
            # # wait for child to get ping from parent when parent reconnects to mqtt
            # # verify no child comm state change has occurred.
            # # Tell *both* clients we lost comm.
            # # Wait for reconnect
            # # wait for all events to be acked
