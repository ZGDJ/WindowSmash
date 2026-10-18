#!/usr/bin/env python3
"""Tests for the netplay lobby (tools/ssbu_relay.py): fake players on loopback, no game.

    python -I tools/test_ssbu_relay.py [-v]"""
import asyncio
import os
import secrets
import socket
import struct
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ssbu_relay as R   # noqa: E402

BUILD = "4A3F8ED7DCCE3AD4541A3A2F7622B5B57FC8A55C"
OTHER_BUILD = "21450C647B8C5940ED5B68218EA128FD3C5D597D"
BCAST = R.BROADCASTS[0]
GAME_PORT = 12345


class Server:
    """A lobby on its own event loop and thread, with short timeouts."""
    def __init__(self, **over):
        settings = dict(bind="127.0.0.1", port=0, stats=0, tick=0.05, client_timeout=10.0, pending_timeout=0.5,
                        listed_for=3.5, listing_timeout=10.0, per_ip=1000, gate_rate=1000.0, gate_burst=1000)
        settings.update(over)   # (every player here comes from 127.0.0.1)
        o = R.options(**settings)
        self.loop = asyncio.new_event_loop()
        ready = threading.Event()

        def run():
            asyncio.set_event_loop(self.loop)
            self.transport, self.lobby = self.loop.run_until_complete(R.serve(o))
            self.task = self.loop.create_task(self.lobby.run())
            ready.set()
            self.loop.run_forever()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert ready.wait(5)
        self.port = self.transport.get_extra_info("sockname")[1]

    def stop(self):
        async def end():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.transport.close()
        asyncio.run_coroutine_threadsafe(end(), self.loop).result(5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)
        self.loop.close()


def info_of(session, owner, stations=(), most=8, policy=0, name=b"Host"):
    info = bytearray(R.NI_SIZE)
    info[R.NI_SESSION:R.NI_SESSION + 16] = session
    info[R.NI_POLICY] = policy
    info[R.NI_NODE_MAX] = most
    ips = [owner, *stations]
    info[R.NI_NODE_COUNT] = len(ips)
    for i, ip in enumerate(ips):
        o = R.NI_NODES + R.NODE_SIZE * i
        struct.pack_into("<I", info, o, ip)
        info[o + 0xA] = i
        info[o + 0xB] = 1
        info[o + 0xC:o + 0xC + len(name)] = name if i == 0 else b"Guest"
    return bytes(info)


class Player:
    def __init__(self, server, room="smash", build=BUILD, name="P"):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind(("127.0.0.1", 0))
        self.addr = ("127.0.0.1", server.port)
        self.nonce = secrets.token_bytes(8)
        self.room, self.build, self.name = room, build, name
        self.ip = self.cookie = None

    def close(self):
        self.s.close()

    def send(self, data):
        self.s.sendto(data, self.addr)

    def recv(self, wait=0.4):
        """Every packet that arrives within wait seconds."""
        out, until = [], time.monotonic() + wait
        while True:
            left = until - time.monotonic()
            if left <= 0:
                return out
            self.s.settimeout(left)
            try:
                data, _ = self.s.recvfrom(65536)
            except (socket.timeout, ConnectionResetError):
                return out
            out.append(data)

    def first(self, kind, wait=0.6):
        """The first packet of this kind within wait seconds (others are dropped)."""
        until = time.monotonic() + wait
        while True:
            left = until - time.monotonic()
            if left <= 0:
                return None
            self.s.settimeout(left)
            try:
                data, _ = self.s.recvfrom(65536)
            except (socket.timeout, ConnectionResetError):
                return None
            if data[3] == kind:
                return data

    def join_packet(self, version=R.PROTOCOL, size=R.JOIN_SIZE):
        p = (R.header(R.JOIN, version) + self.nonce + self.room.encode().ljust(32, b"\0") +
             self.name.encode().ljust(32, b"\0") + self.build.encode().ljust(40, b"\0"))
        return p[:size]

    def join(self, verify=True):
        self.send(self.join_packet())
        w = self.first(R.WELCOME)
        assert w is not None, "no WELCOME"
        self.ip, self.cookie, flags = struct.unpack_from(">IQB", w, 12)
        assert flags & 1
        if verify:
            self.ping()
        return self

    def ping(self, ms=20):
        self.send(R.header(R.PING) + self.nonce + struct.pack(">QQH", 1234, self.cookie, ms))
        return self.first(R.PONG)

    def list(self, seq=7):
        self.send(R.header(R.LIST) + struct.pack(">QI", self.cookie, seq))
        rooms, until = [], time.monotonic() + 1
        while time.monotonic() < until:
            for p in self.recv(0.1):
                if p[3] == R.LISTING:
                    assert struct.unpack_from(">I", p, 4)[0] == seq
                    rooms.append((struct.unpack_from(">I", p, 8)[0], p[12:]))
                elif p[3] == R.LIST_END:
                    assert struct.unpack_from(">I", p, 4)[0] == seq and p[8] == len(rooms)
                    return rooms
        raise AssertionError("no LIST_END")

    def data(self, dst, payload, sport=GAME_PORT, dport=GAME_PORT, src=None):
        self.send(R.header(R.DATA) + struct.pack(">IIHH", self.ip if src is None else src, dst, sport, dport) + payload)

    def ldn(self, dst, kind, payload):
        self.data(dst, b"L" + bytes((kind, 0, 0)) + payload, R.LDN_PORT, R.LDN_PORT)

    def advertise(self, session, stations=(), **kw):
        self.ldn(BCAST, R.LM_ADVERTISE, info_of(session, self.ip, stations, **kw))

    def datas(self, wait=0.4):
        """The DATA packets that arrive: (source, destination, source port, payload)."""
        return [(*struct.unpack_from(">IIH", p, 4), p[16:]) for p in self.recv(wait) if p[3] == R.DATA]


class LobbyTest(unittest.TestCase):
    def setUp(self):
        self.server = Server(**getattr(self, "server_options", {}))
        self.players = []

    def tearDown(self):
        for p in self.players:
            p.close()
        self.server.stop()

    def player(self, join=True, **kw):
        p = Player(self.server, **kw)
        self.players.append(p)
        return p.join() if join else p

    def room(self, stations=0):
        """A host with a network, and stations that joined it (asked and were accepted)."""
        host = self.player(name="Host")
        session = secrets.token_bytes(16)
        host.advertise(session)
        joined = []
        for _ in range(stations):
            s = self.player(name="Guest")
            s.ldn(host.ip, R.LM_JOIN, session + b"Guest".ljust(32, b"\0") + b"\0\0")
            self.assertTrue(any(src == s.ip for src, *_ in host.datas()), "the JOIN did not reach the host")
            joined.append(s)
            host.advertise(session, [j.ip for j in joined])
            host.ldn(s.ip, R.LM_ACCEPT, info_of(session, host.ip, [j.ip for j in joined]))
        for p in [host, *joined]:
            p.recv(0.2)
        return host, session, joined


class Joining(LobbyTest):
    def test_old_version_told(self):
        p = self.player(join=False)
        p.send(p.join_packet(version=1, size=R.V1_JOIN_SIZE))
        r = p.first(R.REJECT)
        self.assertIsNotNone(r)
        self.assertEqual(r[2], 1)
        self.assertIn(b"different netplay version", r)

    def test_short_old_join_ignored(self):
        p = self.player(join=False)
        p.send(p.join_packet(version=1, size=20))
        self.assertEqual(p.recv(0.3), [])

    def test_unique_addresses_across_lobbies(self):
        a, b, c = self.player(), self.player(room="friends"), self.player(build=OTHER_BUILD)
        self.assertEqual(len({a.ip, b.ip, c.ip}), 3)
        for p in (a, b, c):
            self.assertEqual(p.ip >> 16, 0x0A0D)
            self.assertNotIn(p.ip & 255, (0, 255))
        self.assertGreaterEqual(a.ip & 0xFFFF, 2)

    def test_join_again_same_address(self):
        p = self.player()
        ip = p.ip
        p.send(p.join_packet())
        w = p.first(R.WELCOME)
        self.assertEqual(struct.unpack_from(">I", w, 12)[0], ip)

    def test_counts_in_pong(self):
        a = self.player()
        self.player()
        self.player(room="friends")
        pong = a.ping()
        online, rooms, flags = struct.unpack_from(">HHB", pong, 12)
        self.assertEqual((online, rooms, flags), (2, 0, 1))

    def test_wrong_cookie_not_verified(self):
        a = self.player(join=False).join(verify=False)
        b = self.player()
        a.send(R.header(R.PING) + a.nonce + struct.pack(">QQH", 1, a.cookie ^ 1, 0))
        self.assertIsNone(a.first(R.PONG, 0.3))
        a.data(b.ip, b"hello")   # (not verified: nothing is forwarded)
        self.assertEqual(b.datas(0.3), [])
        a.send(R.header(R.LIST) + struct.pack(">QI", a.cookie ^ 1, 1))
        self.assertEqual(a.recv(0.3), [])

    def test_unverified_player_expires(self):
        a = self.player(join=False).join(verify=False)
        time.sleep(0.8)
        b = self.player()
        self.assertEqual(len(self.server.lobby.by_addr), 1)
        self.assertNotEqual(a.ip, None)
        self.assertIsNotNone(b.ip)

    def test_leave(self):
        a = self.player()
        a.send(R.header(R.LEAVE) + a.nonce)
        time.sleep(0.1)
        self.assertEqual(len(self.server.lobby.by_addr), 0)


class Limits(LobbyTest):
    server_options = {"per_ip": 2, "packet_rate": 20.0}

    def test_per_ip_cap(self):
        self.player()
        self.player()
        p = self.player(join=False)
        p.send(p.join_packet())
        r = p.first(R.REJECT)
        self.assertIsNotNone(r)
        self.assertIn(b"too many players", r)

    def test_rate_limit(self):
        host, session, (guest,) = self.room(1)
        for i in range(200):
            guest.data(BCAST, b"x%d" % i)
        got = host.datas(0.5)
        self.assertLess(len(got), 100)
        self.assertGreater(len(got), 10)


class Banning(LobbyTest):
    def setUp(self):
        self.ban = os.path.join(os.environ.get("TEMP", "/tmp"), f"ssbu-banlist-{os.getpid()}.txt")
        with open(self.ban, "w") as f:
            f.write("# test\n10.0.0.0/8\n")
        self.server_options = {"banlist": self.ban}
        super().setUp()

    def tearDown(self):
        super().tearDown()
        os.remove(self.ban)

    def test_banned_then_not(self):
        self.player()   # (127.0.0.1 is not banned)
        with open(self.ban, "w") as f:
            f.write("127.0.0.0/8\n")
        os.utime(self.ban, (time.time() + 10, time.time() + 10))
        self.server.lobby.ban_checked = 0
        time.sleep(0.2)
        self.assertEqual(len(self.server.lobby.by_addr), 0)
        p = self.player(join=False)
        p.send(p.join_packet())
        self.assertEqual(p.recv(0.3), [])


class ListingOrder(unittest.TestCase):
    def test_equal_timestamps_keep_advertisement_order(self):
        # A coarse monotonic clock can assign every advert the same timestamp.
        # Host addresses and session IDs must not substitute for opening order.
        lobby = R.Lobby(R.options())
        now = 100.0
        part = (BUILD.encode(), "smash")
        hosts = [R.Client(("127.0.0.1", i), bytes(8), R.SUBNET + i,
                          "Host", part, now, lobby.o) for i in range(2, 10)]
        looker = R.Client(("127.0.0.1", 10), bytes(8), R.SUBNET + 10,
                          "Looker", part, now, lobby.o)
        packets = []
        lobby.send = lambda packet, at: packets.append(packet)

        def advertise(host):
            session = host.ip.to_bytes(16, "big")
            info = info_of(session, host.ip)
            lobby.on_advertise(host, R.ldn_packet(host.ip, BCAST, R.LM_ADVERTISE, info), info, now)

        def listed():
            packets.clear()
            lobby.on_list(looker, bytes(4), now)
            return [struct.unpack_from(">I", p, 8)[0] for p in packets if p[3] == R.LISTING]

        opened = list(reversed(hosts))
        for host in opened:
            host.ping = 50
            advertise(host)
        self.assertEqual(listed(), [h.ip for h in opened])

        # Refreshes and ping jitter preserve position; reopening is a new room.
        opened[0].ping = 180
        advertise(opened[0])
        self.assertEqual(listed(), [h.ip for h in opened])
        lobby.close(opened[0].listing)
        opened[0].ping = 50
        advertise(opened[0])
        self.assertEqual(listed(), [h.ip for h in opened[1:] + opened[:1]])


class Listing(LobbyTest):
    def test_order_keeps_through_ping_jitter(self):
        far = self.player()
        far.ping(180)   # (a host far from the lobby: its room goes after near ones, though older)
        far.advertise(secrets.token_bytes(16))
        older, newer = self.player(), self.player()
        older.ping(52)
        older.advertise(secrets.token_bytes(16))
        newer.ping(47)
        newer.advertise(secrets.token_bytes(16))
        looker = self.player()
        for older_ms, newer_ms in ((49, 48), (48, 51), (99, 3)):   # (pings change; the order does not)
            older.ping(older_ms)
            newer.ping(newer_ms)
            self.assertEqual([o for o, _ in looker.list()], [older.ip, newer.ip, far.ip])

    def test_rooms_listed_to_same_build_and_code(self):
        host, session, _ = self.room()
        same, other_code, other_build = self.player(), self.player(room="friends"), self.player(build=OTHER_BUILD)
        rooms = same.list()
        self.assertEqual(len(rooms), 1)
        owner, info = rooms[0]
        self.assertEqual(owner, host.ip)
        self.assertEqual(info[R.NI_SESSION:R.NI_SESSION + 16], session)
        self.assertEqual(other_code.list(), [])
        self.assertEqual(other_build.list(), [])
        self.assertEqual(host.list(), [])   # (not its own)

    def test_order_and_cap(self):
        hosts = []
        for stations in (0, 2, 1):
            h = self.player()
            fake = [h.ip + 0x100 * (k + 1) for k in range(stations)]   # (stations it lists; not real players)
            h.advertise(secrets.token_bytes(16), fake)
            hosts.append(h)
        full = self.player()
        full.advertise(secrets.token_bytes(16), most=1)
        rooms = self.player().list()
        self.assertEqual([o for o, _ in rooms], [hosts[1].ip, hosts[2].ip, hosts[0].ip, full.ip])
        for _ in range(R.LIST_MAX + 2):
            self.player().advertise(secrets.token_bytes(16))
        self.assertEqual(len(self.player().list()), R.LIST_MAX)


    def test_gone_closes(self):
        host, session, _ = self.room()
        host.ldn(BCAST, R.LM_GONE, session)
        time.sleep(0.1)
        self.assertEqual(self.player().list(), [])

    def test_bad_adverts_ignored(self):
        h = self.player()
        h.ldn(BCAST, R.LM_ADVERTISE, info_of(secrets.token_bytes(16), h.ip + 1))   # (another host's address)
        h.ldn(BCAST, R.LM_ADVERTISE, info_of(secrets.token_bytes(16), h.ip, most=9))
        h.ldn(BCAST, R.LM_ADVERTISE, info_of(secrets.token_bytes(16), h.ip)[:100])
        self.assertEqual(self.player().list(), [])

    def test_session_cannot_be_taken(self):
        host, session, _ = self.room()
        thief = self.player()
        thief.advertise(session)
        rooms = self.player().list()
        self.assertEqual([o for o, _ in rooms], [host.ip])

    def test_one_room_per_host(self):
        h = self.player()
        h.advertise(secrets.token_bytes(16))
        second = secrets.token_bytes(16)
        h.advertise(second)
        rooms = self.player().list()
        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0][1][R.NI_SESSION:R.NI_SESSION + 16], second)


class Rooms(LobbyTest):
    def test_join_handshake(self):
        host = self.player()
        session = secrets.token_bytes(16)
        host.advertise(session)
        guest = self.player()
        guest.ldn(host.ip, R.LM_JOIN, session + b"G".ljust(32, b"\0") + b"\0\0")
        got = host.datas()
        self.assertEqual([(s, p[1]) for s, d, sp, p in got], [(guest.ip, R.LM_JOIN)])
        host.ldn(guest.ip, R.LM_ACCEPT, info_of(session, host.ip, [guest.ip]))
        host.advertise(session, [guest.ip])
        got = guest.datas()
        self.assertEqual([p[1] for s, d, sp, p in got], [R.LM_ACCEPT, R.LM_ADVERTISE])

    def test_game_traffic_stays_in_room(self):
        host, session, (a, b) = self.room(2)
        other_host, _, (c,) = self.room(1)
        stranger = self.player()
        a.data(BCAST, b"hello room")
        self.assertEqual([p for *_, p in host.datas()], [b"hello room"])
        self.assertEqual([p for *_, p in b.datas(0.1)], [b"hello room"])
        self.assertEqual(c.datas(0.1) + other_host.datas(0.1) + stranger.datas(0.1), [])
        a.data(b.ip, b"to b")
        self.assertEqual([p for *_, p in b.datas()], [b"to b"])
        a.data(c.ip, b"to c")   # (another room)
        stranger.data(host.ip, b"hi")   # (not in the room)
        stranger.data(BCAST, b"all")
        self.assertEqual(c.datas(0.2) + host.datas(0.2), [])

    def test_joiner_not_accepted_gets_no_game_traffic(self):
        host, session, _ = self.room()
        guest = self.player()
        guest.ldn(host.ip, R.LM_JOIN, session + bytes(34))
        host.recv(0.2)
        host.data(BCAST, b"game")   # (the guest is not in the host's advert yet)
        host.data(guest.ip, b"game")
        self.assertEqual(guest.datas(0.3), [])

    def test_spoofed_source_dropped(self):
        host, session, (a,) = self.room(1)
        b = self.player()
        b.data(a.ip, b"x", src=host.ip)
        b.ldn(BCAST, R.LM_GONE, session)
        self.assertEqual(a.datas(0.3), [])

    def test_forged_ldn_messages_dropped(self):
        host, session, (a,) = self.room(1)
        evil = self.player()
        evil.ldn(a.ip, R.LM_GONE, session)                 # (GONE only as the host's broadcast)
        evil.ldn(a.ip, R.LM_ADVERTISE, info_of(session, evil.ip))
        evil.ldn(a.ip, R.LM_ACCEPT, info_of(session, host.ip))   # (evil hosts nothing a asked to join)
        evil.ldn(a.ip, R.LM_KICK, session)
        evil.ldn(host.ip, R.LM_KEEP, session)             # (evil never joined)
        evil.data(a.ip, b"L\x07\0\0" + session, sport=GAME_PORT, dport=R.LDN_PORT)
        self.assertEqual(a.datas(0.3) + host.datas(0.1), [])

    def test_station_leaves(self):
        host, session, (a, b) = self.room(2)
        a.ldn(host.ip, R.LM_LEAVE, session)
        self.assertEqual([p[1] for s, d, sp, p in host.datas()], [R.LM_LEAVE])
        a.data(BCAST, b"still here?")
        self.assertEqual(b.datas(0.3), [])

    def test_kicked_station_hears_the_advert(self):
        host, session, (a, b) = self.room(2)
        host.ldn(a.ip, R.LM_KICK, session)
        host.advertise(session, [b.ip])
        self.assertEqual([p[1] for s, d, sp, p in a.datas()], [R.LM_KICK, R.LM_ADVERTISE])




class Timeouts(LobbyTest):
    server_options = {"client_timeout": 1.0, "listing_timeout": 2.0, "listed_for": 0.5}

    def test_listing_goes_stale_then_away(self):
        host, session, _ = self.room()
        looker = self.player()
        self.assertEqual(len(looker.list()), 1)
        until = time.monotonic() + 0.8   # (both stay, but the host stops advertising for longer than listed_for)
        while time.monotonic() < until:
            host.ping()
            looker.ping()
            time.sleep(0.1)
        self.assertEqual(looker.list(), [])
        self.assertIn(session, self.server.lobby.listings)   # (still routed until listing_timeout)

    def test_host_timeout_tells_stations(self):
        host, session, (a,) = self.room(1)
        until = time.monotonic() + 1.6
        gone = []
        while time.monotonic() < until and not gone:   # (the station keeps itself alive; the host goes silent)
            a.ping()
            gone = [p for s, d, sp, p in a.datas(0.2) if p[1] == R.LM_GONE]
        self.assertTrue(gone, "no LM_GONE after the host timed out")
        self.assertEqual(gone[0][4:20], session)

    def test_station_timeout_tells_host(self):
        host, session, (a,) = self.room(1)
        until = time.monotonic() + 1.6
        left = []
        while time.monotonic() < until and not left:
            host.ping()
            host.advertise(session, [a.ip])
            left = [(s, p) for s, d, sp, p in host.datas(0.2) if p[1] == R.LM_LEAVE]
        self.assertTrue(left, "no LM_LEAVE after the station timed out")
        self.assertEqual(left[0][0], a.ip)


if __name__ == "__main__":
    unittest.main()
