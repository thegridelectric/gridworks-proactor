# ruff: noqa: PLR2004, ERA001

import asyncio
from typing import Type

import pytest
from gwproto import MQTTTopic

from gwproactor.links import StateName
from gwproactor_test.comm_test_helper import CommTestHelper
from gwproactor_test.wait import await_for


@pytest.mark.asyncio
class ProactorCommTimeoutTests:
    CTH: Type[CommTestHelper]

    @pytest.mark.asyncio
    async def test_response_timeout(self) -> None:
        """
        Test:
            (awaiting_peer -> response_timeout -> awaiting_peer)
            (active -> response_timeout -> awaiting_peer)
        """

        async with self.CTH(
            add_child=True,
            add_parent=True,
        ) as h:
            child = h.child
            link = child.links.link(child.upstream_client)
            stats = child.stats.link(child.upstream_client)
            parent = h.parent
            parent_link = parent.links.link(parent.primary_peer_client)

            # Timeout while awaiting setup
            # (awaiting_peer -> response_timeout -> awaiting_peer)

            # start parent
            parent.pause_acks()
            h.start_parent()
            await await_for(
                lambda: parent_link.in_state(StateName.awaiting_peer),
                3,
                "ERROR waiting for parent to connect to broker",
                err_str_f=parent.summary_str,
            )

            # start child
            child.set_ack_timeout_seconds(1)
            assert stats.timeouts == 0
            h.start_child()
            await await_for(
                lambda: link.in_state(StateName.awaiting_peer),
                3,
                "ERROR waiting for child to connect to broker",
                err_str_f=parent.summary_str,
            )
            # (awaiting_peer -> response_timeout -> awaiting_peer)
            await await_for(
                lambda: stats.timeouts > 0,
                1,
                "ERROR waiting for child to timeout",
                err_str_f=parent.summary_str,
            )
            assert link.state == StateName.awaiting_peer
            assert child.event_persister.num_pending > 0

            # release the hounds
            # (awaiting_peer -> message_from_peer -> active)
            parent.release_acks()
            await await_for(
                lambda: link.in_state(StateName.active),
                1,
                "ERROR waiting for parent to restore link #1",
                err_str_f=parent.summary_str,
            )
            # wait for all events to be acked
            await await_for(
                lambda: child.event_persister.num_pending == 0,
                1,
                "ERROR waiting for events to be acked",
                err_str_f=child.summary_str,
            )

            # Timeout while active
            # (active -> response_timeout -> awaiting_peer)
            parent.pause_acks()
            child.ping_peer()
            exp_timeouts = stats.timeouts + len(
                child.links.ack_manager._acks[child.upstream_client]  # noqa: SLF001
            )
            await await_for(
                lambda: stats.timeouts == exp_timeouts,
                1,
                "ERROR waiting for child to timeout",
                err_str_f=child.summary_str,
            )
            assert link.state == StateName.awaiting_peer
            assert child.event_persister.num_pending > 0
            await await_for(
                lambda: len(parent.needs_ack) == 2,
                1,
                "ERROR waiting for child to timeout",
                err_str_f=child.summary_str,
            )

            # (awaiting_peer -> message_from_peer -> active)
            parent.release_acks()
            await await_for(
                lambda: link.in_state(StateName.active),
                1,
                "ERROR waiting for parent to restore link #1",
                err_str_f=parent.summary_str,
            )

    @pytest.mark.skip(reason="Skipping for now")
    @pytest.mark.asyncio
    async def test_ping(self) -> None:
        """
        Test:
            ping sent peridoically if no messages sent
            ping not sent if messages are sent
            ping restores comm
        """
        child_settings = self.CTH.child_settings_t()
        parent_settings = self.CTH.parent_settings_t()
        child_settings.mqtt_link_poll_seconds = (
            parent_settings.mqtt_link_poll_seconds
        ) = 0.1
        async with self.CTH(
            add_child=True,
            add_parent=True,
            child_settings=child_settings,
            parent_settings=parent_settings,
            verbose=False,
        ) as h:
            parent = h.parent
            parent_stats = parent.stats.link(parent.primary_peer_client)
            parent_ping_topic = MQTTTopic.encode(
                "gw",
                parent.publication_name,  # noqa
                "gridworks-ping",
            )

            child = h.child
            child.disable_derived_events()
            child.set_ack_timeout_seconds(1)
            link = child.links.link(child.upstream_client)
            stats = child.stats.link(child.upstream_client)
            child_ping_topic = MQTTTopic.encode(
                "gw",
                child.publication_name,  # noqa
                "gridworks-ping",
            )

            # start parent and child
            h.start_parent()
            h.start_child()
            await await_for(
                lambda: link.in_state(StateName.active),
                3,
                "ERROR waiting for child active",
                err_str_f=child.summary_str,
            )

            # Test that ping sent peridoically if no messages sent
            start_pings_from_parent = stats.num_received_by_topic[parent_ping_topic]
            start_pings_from_child = parent_stats.num_received_by_topic[
                child_ping_topic
            ]
            start_messages_from_parent = stats.num_received
            start_messages_from_child = parent_stats.num_received
            wait_seconds = 0.5
            await asyncio.sleep(wait_seconds)
            pings_from_parent = (
                stats.num_received_by_topic[parent_ping_topic] - start_pings_from_parent
            )
            pings_from_child = (
                parent_stats.num_received_by_topic[child_ping_topic]
                - start_pings_from_child
            )
            messages_from_parent = stats.num_received - start_messages_from_parent
            messages_from_child = parent_stats.num_received - start_messages_from_child
            exp_pings_nominal = (
                wait_seconds / parent.settings.mqtt_link_poll_seconds
            ) - 1
            err_str = (
                f"pings_from_parent: {pings_from_parent}\n"
                f"messages_from_parent: {messages_from_parent}\n"
                f"pings_from_child: {pings_from_child}\n"
                f"messages_from_child: {messages_from_child}\n"
                f"exp_pings_nominal: {exp_pings_nominal}\n"
                f"\n{child.summary_str()}\n"
                f"\n{parent.summary_str()}\n"
            )
            assert (pings_from_child + pings_from_parent) >= exp_pings_nominal, err_str
            assert messages_from_child >= exp_pings_nominal, err_str
            assert messages_from_parent >= exp_pings_nominal, err_str

            # Test that ping not sent peridoically if messages are sent
            start_pings_from_parent = stats.num_received_by_topic[parent_ping_topic]
            start_pings_from_child = parent_stats.num_received_by_topic[
                child_ping_topic
            ]
            start_messages_from_parent = stats.num_received
            start_messages_from_child = parent_stats.num_received
            reps = 50
            for _ in range(reps):
                parent.send_dbg_to_peer()
                await asyncio.sleep(0.01)
            pings_from_parent = (
                stats.num_received_by_topic[parent_ping_topic] - start_pings_from_parent
            )
            pings_from_child = (
                parent_stats.num_received_by_topic[child_ping_topic]
                - start_pings_from_child
            )
            messages_from_parent = stats.num_received - start_messages_from_parent
            messages_from_child = parent_stats.num_received - start_messages_from_child
            exp_pings_nominal = 2
            err_str = (
                f"pings_from_parent: {pings_from_parent}\n"
                f"messages_from_parent: {messages_from_parent}\n"
                f"pings_from_child: {pings_from_child}\n"
                f"messages_from_child: {messages_from_child}\n"
                f"exp_pings_nominal: {exp_pings_nominal}\n"
                f"\n{child.summary_str()}\n"
                f"\n{parent.summary_str()}\n"
            )
            assert pings_from_parent <= exp_pings_nominal, err_str
            assert pings_from_child <= exp_pings_nominal, err_str
            # Allow wide variance in number of messages exchanged - we are really testing pings, which
            # Should be should be close to 0 when a lot of messages are being exchanged.
            assert messages_from_parent >= reps * 0.5, err_str
            assert messages_from_child >= reps * 0.5, err_str

            parent.pause_acks()
            await await_for(
                lambda: link.in_state(StateName.awaiting_peer),
                child.links.ack_manager.default_delay_seconds + 1,
                "ERROR waiting for for parent to be slow",
                err_str_f=child.summary_str,
            )
            parent.release_acks(clear=True)
            await await_for(
                lambda: link.in_state(StateName.active),
                1,
                "ERROR waiting for parent to respond",
                err_str_f=child.summary_str,
            )
