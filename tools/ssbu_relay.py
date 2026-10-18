#!/usr/bin/env python3
"""Netplay lobby for the SSBU native port: the server every player's game joins to play online.

Players' games join it at start (Play SSBU.bat). A room anyone creates in Local Wireless is listed
to every player of the same game version and lobby code, who join it from the game's Rooms List;
the lobby then carries the room's traffic between its players only. Players only send to the
lobby, so nobody needs port forwarding; the lobby's machine needs its UDP port open. The protocol
is runtime/net_relay.c's (version 2); the host player's game can run a smaller relay of its own
for a private room (Host SSBU Netplay.bat).

    python3 ssbu_relay.py [--port 39420] [--bind 0.0.0.0] [--verbose] [--banlist FILE]
    python3 ssbu_relay.py --probe HOST[:PORT] [--room CODE] [--build ID]   (is a lobby there?)

Python 3.8+, standard library only."""
import argparse
import asyncio
import collections
import ipaddress
import os
import secrets
import signal
import socket
import struct
import sys
import time

PROTOCOL = 2
JOIN, WELCOME, REJECT, PING, PONG, DATA, MEMBERS, LEAVE, LIST, LISTING, LIST_END = range(1, 12)
NAME_LEN = 32
BUILD_LEN = 40
JOIN_SIZE = 4 + 8 + 2 * NAME_LEN + BUILD_LEN
V1_JOIN_SIZE = 4 + 8 + 2 * NAME_LEN
PING_SIZE = 4 + 8 + 8 + 8 + 2
SUBNET = 0x0A0D0000
BROADCASTS = (0x0A0DFFFF, 0xFFFFFFFF)
DEFAULT_PORT = 39420
LIST_MAX = 24

# Local wireless's own messages (runtime/hle_net.c), carried in DATA between port 65511s:
# 'L', type, 0, 0, payload.
LDN_PORT = 65511
LM_ADVERTISE, LM_JOIN, LM_ACCEPT, LM_REJECT, LM_KEEP, LM_LEAVE, LM_GONE, LM_KICK = range(1, 9)
# A network's NetworkInfo, as the console lays it out (little-endian).
NI_SIZE = 0x480
NI_SESSION = 0x10
NI_POLICY = 0x62
NI_NODE_MAX = 0x66
NI_NODE_COUNT = 0x67
NI_NODES = 0x68
NI_ADV_SIZE = 0x26A
NODE_SIZE = 0x40


def header(kind, version=PROTOCOL):
    return b"SN" + bytes((version, kind))


def text(raw):
    return raw.split(b"\0", 1)[0].decode("utf-8", "replace")


def printable(s):
    return "".join(ch if ch.isprintable() else "?" for ch in s)


def ip_text(ip):
    return f"10.13.{ip >> 8 & 255}.{ip & 255}"


def ldn_packet(src, dst, kind, payload):
    """A local wireless message as a player's game would send it."""
    return (header(DATA) + struct.pack(">IIHH", src, dst, LDN_PORT, LDN_PORT) +
            bytes((ord("L"), kind, 0, 0)) + payload)


def node_name(info, i=0):
    o = NI_NODES + NODE_SIZE * i + 0xC
    return printable(text(info[o:o + NAME_LEN]))


def network_nodes(info, owner_ip):
    """The addresses of a network's stations (node 0, the host, left out), or None when the
    NetworkInfo is not one a game makes or its host is not owner_ip."""
    count, most = info[NI_NODE_COUNT], info[NI_NODE_MAX]
    if not 1 <= count <= most <= 8 or struct.unpack_from("<H", info, NI_ADV_SIZE)[0] > 0x180:
        return None
    nodes = []
    for i in range(8):
        o = NI_NODES + NODE_SIZE * i
        if not info[o + 0xB]:
            if i == 0:
                return None
            continue
        ip = struct.unpack_from("<I", info, o)[0]
        if ip & 0xFFFF0000 != SUBNET or (i == 0 and ip != owner_ip) or ip in nodes:
            return None
        nodes.append(ip)
    return frozenset(nodes[1:]) if len(nodes) == count else None


class Bucket:
    """A token bucket: rate a second, up to burst saved."""
    __slots__ = ("rate", "burst", "level", "at")

    def __init__(self, rate, burst, now):
        self.rate, self.burst, self.level, self.at = rate, burst, burst, now

    def take(self, now, n=1.0):
        self.level = min(self.burst, self.level + (now - self.at) * self.rate)
        self.at = now
        if self.level < n:
            return False
        self.level -= n
        return True


class Client:
    def __init__(self, at, nonce, ip, name, part, now, o):
        self.at, self.nonce, self.ip, self.name, self.part = at, nonce, ip, name, part
        self.cookie = secrets.randbits(64)   # proves the address is real (it came back in a PING)
        self.verified = False
        self.seen = now
        self.ping = 0xFFFF
        self.claim = None      # the session this player asked to join (its LM_JOIN)
        self.listing = None    # the network this player hosts
        self.packets = Bucket(o.packet_rate, o.packet_rate * 2, now)
        self.bytes = Bucket(o.byte_rate, o.byte_rate * 2, now)
        self.joins = Bucket(2, 8, now)
        self.lists = Bucket(4, 8, now)


class Listing:
    """A network a player hosts, from its latest advert."""
    def __init__(self, owner, session, now):
        self.owner, self.session, self.created = owner, session, now
        self.info, self.nodes, self.updated = b"", frozenset(), 0.0
        self.distance = None   # the host's ping to the lobby in 100 ms steps, when the room opened

    @property
    def count(self):
        return self.info[NI_NODE_COUNT]

    @property
    def open(self):
        return self.info[NI_POLICY] != 1 and self.info[NI_NODE_COUNT] < self.info[NI_NODE_MAX]


def options(**overrides):
    """The lobby's settings (main's command line; tests override some)."""
    o = argparse.Namespace(port=DEFAULT_PORT, bind="0.0.0.0", verbose=False, banlist=None,
                           max_clients=2000, max_pending=1000, per_ip=8, gate_rate=5.0, gate_burst=20,
                           packet_rate=600.0, byte_rate=400_000.0, max_data=1500,
                           client_timeout=10.0, pending_timeout=3.0, listed_for=3.5, listing_timeout=10.0,
                           tick=1.0, stats=60.0)
    for k, v in overrides.items():
        setattr(o, k, v)
    return o


class Lobby(asyncio.DatagramProtocol):
    def __init__(self, o):
        self.o = o
        self.by_addr = {}       # (host, port) -> Client
        self.by_ip = {}         # virtual address -> Client
        self.parts = {}         # (build, lobby code) -> set of Client
        self.part_rooms = {}    # (build, lobby code) -> insertion-ordered dict of Listing -> None
        self.listings = {}      # session id -> Listing
        self.per_ip = collections.Counter()   # host -> verified players from there
        self.pending = 0        # players not verified yet
        self.gates = {}         # host -> Bucket: answers to strangers' JOINs
        self.next_ip = SUBNET + 2
        self.banned, self.ban_stamp, self.ban_checked = [], None, 0.0
        self.counts = collections.Counter()
        self.drops = collections.Counter()
        self.max_data = 0
        self.transport = None

    # ---- plumbing ---------------------------------------------------------------------
    def connection_made(self, transport):
        self.transport = transport

    def error_received(self, exc):
        self.drops["socket error"] += 1

    def log(self, *what):
        if self.o.verbose:
            self.say(*what)

    @staticmethod
    def say(*what):
        print(time.strftime("%Y-%m-%d %H:%M:%S"), *what, flush=True)

    def send(self, data, at):
        self.counts["out packets"] += 1
        self.counts["out bytes"] += len(data)
        self.transport.sendto(data, at)

    def reject(self, at, nonce, reason, why, version=PROTOCOL):
        self.send(header(REJECT, version) + nonce + bytes((reason,)) + why.encode()[:63].ljust(64, b"\0"), at)

    def gate(self, at, now):
        """Whether a stranger at this address may get an answer now (rate-limited: a lobby must not
        answer floods from spoofed addresses)."""
        b = self.gates.get(at[0])
        if b is None:
            b = self.gates[at[0]] = Bucket(self.o.gate_rate, self.o.gate_burst, now)
        return b.take(now)

    def is_banned(self, host):
        if not self.banned:
            return False
        try:
            a = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(a in net for net in self.banned)

    def load_banlist(self, now):
        self.ban_checked = now
        path = self.o.banlist
        if not path:
            return
        try:
            stamp = os.stat(path).st_mtime
        except OSError:
            stamp = None
        if stamp == self.ban_stamp:
            return
        self.ban_stamp, banned = stamp, []
        if stamp is not None:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.split("#", 1)[0].strip()
                    if line:
                        try:
                            banned.append(ipaddress.ip_network(line, strict=False))
                        except ValueError:
                            self.say(f"banlist: not an address: {printable(line)}")
        self.banned = banned
        self.say(f"banlist: {len(banned)} entr{'y' if len(banned) == 1 else 'ies'}")
        for c in list(self.by_addr.values()):
            if self.is_banned(c.at[0]):
                self.drop(c, "banned")

    def new_ip(self):
        """A free virtual address, handed out in turn (a freed one is not reused at once)."""
        for _ in range(0x10000):
            ip = self.next_ip
            self.next_ip = SUBNET + 2 if ip >= SUBNET + 0xFFFE else ip + 1
            if ip & 0xFF not in (0, 255) and ip not in self.by_ip:
                return ip
        return None

    # ---- who is in which network -----------------------------------------------------
    def members(self, listing):
        """The players of a network: its host, and every station it lists that asked to join it."""
        out = [listing.owner]
        for ip in listing.nodes:
            c = self.by_ip.get(ip)
            if c is not None and c.claim == listing.session:
                out.append(c)
        return out

    def network_of(self, c):
        if c.listing is not None:
            return c.listing
        listing = self.listings.get(c.claim) if c.claim else None
        return listing if listing is not None and c.ip in listing.nodes else None

    def close(self, listing, packet=None):
        """A network is gone: tell its players (with the host's own LM_GONE if there is one)."""
        if packet is None:
            packet = ldn_packet(listing.owner.ip, BROADCASTS[0], LM_GONE, listing.session)
        for m in self.members(listing):
            if m is not listing.owner:
                self.send(packet, m.at)
                m.claim = None
        self.listings.pop(listing.session, None)
        rooms = self.part_rooms.get(listing.owner.part)
        if rooms is not None:
            rooms.pop(listing, None)
            if not rooms:
                del self.part_rooms[listing.owner.part]
        if listing.owner.listing is listing:
            listing.owner.listing = None
        self.log(f"room of {printable(listing.owner.name)} closed")

    def drop(self, c, why):
        if c.listing is not None:
            self.close(c.listing)
        if c.claim:   # tell its host at once rather than after the host's timeout
            listing = self.listings.get(c.claim)
            if listing is not None and c.ip in listing.nodes:
                self.send(ldn_packet(c.ip, listing.owner.ip, LM_LEAVE, c.claim), listing.owner.at)
        self.by_addr.pop(c.at, None)
        self.by_ip.pop(c.ip, None)
        players = self.parts.get(c.part)
        if players is not None:
            players.discard(c)
            if not players:
                del self.parts[c.part]
        if c.verified:
            self.per_ip[c.at[0]] -= 1
            if self.per_ip[c.at[0]] <= 0:
                del self.per_ip[c.at[0]]
        else:
            self.pending -= 1
        self.log(f"{printable(c.name)} ({ip_text(c.ip)}) left: {why}")

    def verify(self, c):
        if not c.verified:
            c.verified = True
            self.pending -= 1
            self.per_ip[c.at[0]] += 1

    # ---- packets ------------------------------------------------------------------------
    def datagram_received(self, p, at):
        self.counts["in packets"] += 1
        self.counts["in bytes"] += len(p)
        if len(p) < 4 or p[:2] != b"SN":
            return
        try:
            self.packet(p, at, time.monotonic())
        except Exception as e:   # (one bad packet never stops the lobby)
            self.drops["error"] += 1
            self.say(f"error on a packet from {at[0]}: {e!r}")

    def packet(self, p, at, now):
        kind = p[3]
        if p[2] != PROTOCOL:   # another version of the game's netplay: say so
            if kind == JOIN and len(p) >= V1_JOIN_SIZE and self.gate(at, now):
                self.reject(at, p[4:12], 2, f"different netplay version (lobby {PROTOCOL}, you {p[2]})", p[2])
            return
        c = self.by_addr.get(at)
        if kind == JOIN:
            self.on_join(p, at, c, now)
        elif c is None:
            return
        elif kind == PING:
            if len(p) < PING_SIZE or p[4:12] != c.nonce or struct.unpack_from(">Q", p, 20)[0] != c.cookie:
                return
            self.verify(c)
            c.seen = now
            c.ping = struct.unpack_from(">H", p, 28)[0]
            self.send(header(PONG) + p[12:20] + struct.pack(">HHB", min(len(self.parts.get(c.part, ())), 0xFFFF),
                                                            min(len(self.part_rooms.get(c.part, ())), 0xFFFF), 1), at)
        elif kind == LEAVE:
            if len(p) >= 12 and p[4:12] == c.nonce:
                self.drop(c, "left")
        elif kind == LIST:
            if len(p) < 16 or struct.unpack_from(">Q", p, 4)[0] != c.cookie:
                return
            self.verify(c)
            c.seen = now
            if not c.lists.take(now):
                self.drops["list rate"] += 1
                return
            self.on_list(c, p[12:16], now)
        elif kind == DATA:
            if len(p) < 16 or not c.verified:
                return
            c.seen = now
            if len(p) - 16 > self.o.max_data:
                self.drops["too big"] += 1
                return
            self.max_data = max(self.max_data, len(p) - 16)
            if not c.packets.take(now) or not c.bytes.take(now, len(p)):
                self.drops["rate"] += 1
                return
            src, dst, sport, dport = struct.unpack_from(">IIHH", p, 4)
            if src != c.ip:
                self.drops["not its address"] += 1
            elif sport == LDN_PORT or dport == LDN_PORT:
                self.on_ldn(c, p, dst, sport, dport, now)
            else:
                self.on_game(c, p, dst)

    def on_join(self, p, at, c, now):
        if len(p) < JOIN_SIZE:
            return
        nonce = p[4:12]
        room, name = text(p[12:12 + NAME_LEN]), text(p[12 + NAME_LEN:12 + 2 * NAME_LEN])
        build = p[12 + 2 * NAME_LEN:JOIN_SIZE].rstrip(b"\0")
        if self.is_banned(at[0]):
            self.drops["banned"] += 1
            return
        if c is not None and c.nonce != nonce:   # a new game from the same place
            self.drop(c, "restarted")
            c = None
        part = (build, room)
        if c is None:   # a player back from a new place (its router changed its port)?
            for other in self.parts.get(part, ()):
                if other.nonce == nonce and other.verified:
                    del self.by_addr[other.at]
                    self.per_ip[other.at[0]] -= 1
                    if self.per_ip[other.at[0]] <= 0:
                        del self.per_ip[other.at[0]]
                    self.per_ip[at[0]] += 1
                    other.at = at
                    self.by_addr[at] = c = other
                    break
        if c is None:   # a new player
            if not self.gate(at, now):
                self.drops["join rate"] += 1
                return
            why = ("the lobby is full" if len(self.by_addr) >= self.o.max_clients or self.pending >= self.o.max_pending
                   else f"too many players from your address ({self.o.per_ip})" if self.per_ip[at[0]] >= self.o.per_ip
                   else None)
            ip = self.new_ip() if why is None else None
            if ip is None:
                self.reject(at, nonce, 1, why or "the lobby is full")
                return
            c = Client(at, nonce, ip, name, part, now, self.o)
            self.by_addr[at], self.by_ip[ip] = c, c
            self.parts.setdefault(part, set()).add(c)
            self.pending += 1
            self.log(f"{printable(name)} joined lobby {printable(room)!r} (build {build[:8].decode('ascii', 'replace')}) "
                     f"as {ip_text(ip)} from {at[0]}:{at[1]}")
        c.seen = now
        self.send(header(WELCOME) + nonce + struct.pack(">IQB", c.ip, c.cookie, 1) + b"\0", at)

    def on_list(self, c, seq, now):
        """The rooms this player's Rooms List shows: open ones first, fuller ones first, then the
        ones whose host is closest to the lobby (in 100 ms steps, taken when the room opened: the
        list must not reorder under the player's cursor from one scan to the next), then the oldest.
        Stable sorting retains opening order when the monotonic clock gives equal timestamps."""
        rooms = sorted((r for r in self.part_rooms.get(c.part, ()) if r.owner is not c and now - r.updated <= self.o.listed_for),
                       key=lambda r: (not r.open, -r.count, 10 if r.distance is None else r.distance, r.created))[:LIST_MAX]
        for r in rooms:
            self.send(header(LISTING) + seq + struct.pack(">I", r.owner.ip) + r.info, c.at)
        self.send(header(LIST_END) + seq + bytes((len(rooms),)), c.at)

    def on_ldn(self, c, p, dst, sport, dport, now):
        """Local wireless's own messages: only the ones its protocol has, between the players they
        concern."""
        if sport != LDN_PORT or dport != LDN_PORT or len(p) < 20 or p[16] != ord("L"):
            self.drops["ldn"] += 1
            return
        kind, body = p[17], p[20:]
        if dst in BROADCASTS:
            if kind == LM_ADVERTISE:
                self.on_advertise(c, p, body, now)
            elif kind == LM_GONE and c.listing is not None and body[:16] == c.listing.session:
                self.close(c.listing, p)
            else:
                self.drops["ldn"] += 1
            return
        b = self.by_ip.get(dst)
        if b is None or b is c or b.part != c.part or not b.verified:
            self.drops["ldn"] += 1
            return
        if kind == LM_JOIN:   # asking to join b's network
            listing = b.listing
            if listing is None or body[:16] != listing.session:
                self.drops["ldn"] += 1
                return
            if not c.joins.take(now):
                self.drops["join rate"] += 1
                return
            if c.listing is not None:   # (a host cannot be joining: its network is gone)
                self.close(c.listing)
            c.claim = listing.session
        elif kind in (LM_ACCEPT, LM_REJECT, LM_KICK):   # the host answering one who asked
            if c.listing is None or b.claim != c.listing.session:
                self.drops["ldn"] += 1
                return
        elif kind in (LM_KEEP, LM_LEAVE):   # a station to its host
            if not c.claim or body[:16] != c.claim or b.listing is None or b.listing.session != c.claim:
                self.drops["ldn"] += 1
                return
            if kind == LM_LEAVE:
                self.send(p, b.at)
                c.claim = None
                return
        else:
            self.drops["ldn"] += 1
            return
        self.send(p, b.at)

    def on_advertise(self, c, p, body, now):
        if len(body) < NI_SIZE:
            self.drops["bad advert"] += 1
            return
        info = bytes(body[:NI_SIZE])
        nodes = network_nodes(info, c.ip)
        if nodes is None:
            self.drops["bad advert"] += 1
            return
        session = info[NI_SESSION:NI_SESSION + 16]
        listing = self.listings.get(session)
        if listing is not None and listing.owner is not c:
            self.drops["session taken"] += 1
            return
        if listing is None:   # a new network (one at a time: it replaces the host's last)
            if c.listing is not None:
                self.close(c.listing)
            c.claim = None
            listing = c.listing = self.listings[session] = Listing(c, session, now)
            self.part_rooms.setdefault(c.part, {})[listing] = None
            self.log(f"{printable(c.name)} opened a room ({info[NI_NODE_MAX]} players at most)")
        if listing.distance is None and c.ping != 0xFFFF:
            listing.distance = min(c.ping, 1000) // 100
        before = self.members(listing)
        listing.info, listing.nodes, listing.updated = info, nodes, now
        # (to whoever is in it, and whoever just left it, so they learn it at once)
        for m in {*before, *self.members(listing)}:
            if m is not c:
                self.send(p, m.at)

    def on_game(self, c, p, dst):
        """The game's own traffic: only within a network, between its players."""
        listing = self.network_of(c)
        if listing is None:
            self.drops["not in a room"] += 1
            return
        members = self.members(listing)
        if dst in BROADCASTS:
            for m in members:
                if m is not c:
                    self.send(p, m.at)
            return
        m = self.by_ip.get(dst)
        if m is None or m is c or m not in members:
            self.drops["not in the room"] += 1
            return
        self.send(p, m.at)

    # ---- housekeeping -------------------------------------------------------------------
    def sweep(self, now):
        for c in list(self.by_addr.values()):
            if now - c.seen > (self.o.client_timeout if c.verified else self.o.pending_timeout):
                self.drop(c, "timed out")
        for listing in list(self.listings.values()):
            if now - listing.updated > self.o.listing_timeout:
                self.close(listing)
        for host, b in list(self.gates.items()):
            if now - b.at > 60:
                del self.gates[host]
        if now - self.ban_checked >= 5:
            self.load_banlist(now)

    def report(self, secs):
        c, n = self.counts, len(self.by_addr)
        drops = ", ".join(f"{k} {v}" for k, v in sorted(self.drops.items())) or "none"
        self.say(f"{n} player{'' if n == 1 else 's'} ({self.pending} connecting) in {len(self.parts)} "
                 f"lobb{'y' if len(self.parts) == 1 else 'ies'}, {len(self.listings)} room{'' if len(self.listings) == 1 else 's'}; "
                 f"in {c['in packets'] / secs:.0f}/s {c['in bytes'] / secs / 1024:.1f} KB/s, "
                 f"out {c['out packets'] / secs:.0f}/s {c['out bytes'] / secs / 1024:.1f} KB/s; "
                 f"largest {self.max_data} B; dropped: {drops}")
        self.counts.clear()
        self.drops.clear()
        self.max_data = 0

    async def run(self):
        self.load_banlist(time.monotonic())
        last_report = time.monotonic()
        while True:
            await asyncio.sleep(self.o.tick)
            now = time.monotonic()
            self.sweep(now)
            if self.o.stats and now - last_report >= self.o.stats:
                self.report(now - last_report)
                last_report = now


async def serve(o):
    loop = asyncio.get_running_loop()
    return await loop.create_datagram_endpoint(lambda: Lobby(o), local_addr=(o.bind, o.port))


async def main(o):
    transport, lobby = await serve(o)
    Lobby.say(f"SSBU netplay lobby on UDP {o.bind}:{transport.get_extra_info('sockname')[1]} (protocol {PROTOCOL})")
    task = asyncio.ensure_future(lobby.run())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, task.cancel)
        except (NotImplementedError, AttributeError):   # (Windows: Ctrl+C raises KeyboardInterrupt)
            pass
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        transport.close()
        Lobby.say("stopped")


def probe(target, room, name, build, wait=3.0):
    """Join a lobby as a player would, print what it says, and leave."""
    host, _, port = target.rpartition(":")
    if not host or not port.isdigit():
        host, port = target, str(DEFAULT_PORT)
    try:
        addr = (socket.gethostbyname(host), int(port))
    except OSError as e:
        print(f"cannot find {host}: {e}")
        return 1
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.5)
    nonce = secrets.token_bytes(8)

    def answer(kinds, until):
        while time.monotonic() < until:
            try:
                data, src = s.recvfrom(65536)
            except (socket.timeout, ConnectionResetError):   # (Windows: "port unreachable" came back)
                return None
            if src == addr and data[:2] == b"SN" and data[3] in kinds:
                return data
        return None

    join = (header(JOIN) + nonce + room.encode()[:NAME_LEN].ljust(NAME_LEN, b"\0") +
            name.encode()[:NAME_LEN].ljust(NAME_LEN, b"\0") + build.encode()[:BUILD_LEN].ljust(BUILD_LEN, b"\0"))
    start = time.monotonic()
    welcome = None
    while welcome is None and time.monotonic() - start < wait:
        s.sendto(join, addr)
        got = answer((WELCOME, REJECT), time.monotonic() + 0.5)
        if got and got[3] == REJECT and got[4:12] == nonce:
            print(f"{target}: refused: {text(got[13:77])}")
            return 1
        if got and got[3] == WELCOME and got[4:12] == nonce and len(got) >= 25:
            welcome = got
    if welcome is None:
        print(f"{target} ({addr[0]}:{addr[1]}): no answer")
        return 1
    ip, cookie, flags = struct.unpack_from(">IQB", welcome, 12)
    sent = time.monotonic()
    s.sendto(header(PING) + nonce + struct.pack(">QQH", int(sent * 1000), cookie, 0xFFFF), addr)
    pong = answer((PONG,), time.monotonic() + wait)
    rtt = (time.monotonic() - sent) * 1000
    s.sendto(header(LIST) + struct.pack(">QI", cookie, 1), addr)
    rooms, until = [], time.monotonic() + wait
    while True:
        got = answer((LISTING, LIST_END), until)
        if got is None or got[3] == LIST_END:
            break
        if len(got) >= 12 + NI_SIZE:
            rooms.append(got[12:12 + NI_SIZE])
    s.sendto(header(LEAVE) + nonce, addr)
    if pong is None or len(pong) < 17:
        print(f"{target}: joined as {ip_text(ip)}, but no answer to a ping")
        return 1
    online, nrooms, flags = struct.unpack_from(">HHB", pong, 12)
    print(f"{target} ({addr[0]}:{addr[1]}): {'lobby' if flags & 1 else 'relay'} protocol {PROTOCOL}, "
          f"ping {rtt:.0f} ms; lobby {room!r}, build {build or '(none)'}: {online} player{'' if online == 1 else 's'} "
          f"(this probe included), {nrooms} room{'' if nrooms == 1 else 's'}")
    for info in rooms:
        print(f"  room of {node_name(info)}: {info[NI_NODE_COUNT]}/{info[NI_NODE_MAX]} players"
              f"{'' if info[NI_POLICY] != 1 and info[NI_NODE_COUNT] < info[NI_NODE_MAX] else ' (closed)'}")
    return 0


def parse_args(argv=None):
    d = options()
    a = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    a.add_argument("--port", type=int, default=int(os.environ.get("SSBU_NET_PORT", d.port)), help="UDP port (default 39420)")
    a.add_argument("--bind", default=d.bind, help="the address to listen on (default: all)")
    a.add_argument("--verbose", action="store_true", help="log players and rooms coming and going")
    a.add_argument("--banlist", help="a file of IP addresses or networks (one a line, # comments) to turn away; "
                                     "re-read when it changes")
    a.add_argument("--max-clients", type=int, default=d.max_clients, help="players at most (default %(default)s)")
    a.add_argument("--per-ip", type=int, default=d.per_ip, help="players at most from one IP address (default %(default)s)")
    a.add_argument("--packet-rate", type=float, default=d.packet_rate, help="a player's packets a second (default %(default)s)")
    a.add_argument("--byte-rate", type=float, default=d.byte_rate, help="a player's bytes a second (default %(default)s)")
    a.add_argument("--max-data", type=int, default=d.max_data, help="largest game datagram (default %(default)s)")
    a.add_argument("--stats", type=float, default=d.stats, help="seconds between statistics lines (0: none; default %(default)s)")
    a.add_argument("--probe", metavar="HOST[:PORT]", help="instead of serving: check the lobby at this address")
    a.add_argument("--room", default="smash", help="(--probe) the lobby code (default: the public lobby)")
    a.add_argument("--build", default="", help="(--probe) the game build id to look at (see version.txt)")
    args = a.parse_args(argv)
    for k, v in vars(args).items():
        setattr(d, k, v)
    return d


if __name__ == "__main__":
    o = parse_args()
    if o.probe:
        sys.exit(probe(o.probe, o.room, "probe", o.build))
    try:
        asyncio.run(main(o))
    except KeyboardInterrupt:
        pass
