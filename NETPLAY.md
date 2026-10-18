# Multiplayer setup

> Inherited Local Wireless transport, not rollback. SmashRollback's planned 1v1 rollback session is tracked in the [milestone ledger](milestones/README.md).

[README](README.md) · [Runtime setup](docs/RUNTIME-SETUP.md) · [Build from source](docs/BUILDING.md) · [Technical guide](docs/TECHNICAL.md)

WindowSmash carries the game's **Local Wireless** mode through a UDP relay. By default, `Play SSBU.bat` joins an **online lobby**: every Local Wireless room anyone creates appears in the Rooms List of every player with the same game version, and nobody hosts anything outside the game. For a private group, one player can run the relay inside their game, or everyone can connect to a standalone relay. Nintendo's online service is not used.

On Linux ([README-LINUX.md](README-LINUX.md)), `run.sh`, `run-offline.sh`, `host-netplay.sh` and `join-netplay.sh` do what `Play SSBU.bat`, `Play SSBU Offline.bat` and `Host/Join SSBU Netplay.bat` do. Windows and Linux players with the same game version play together.

> **Validation status:** connection/discovery paths have been exercised during development, including the online lobby with several instances on one PC, through a deployed lobby, and between a Windows and a Linux build. Full two-PC matches, all DLC interactions, and every network environment have not been comprehensively verified.

## Before either player starts

1. Install the **same WindowSmash release/build revision** on both PCs.
2. Configure your own patched game data and fonts using the [runtime setup guide](docs/RUNTIME-SETUP.md), or complete a [source build](docs/BUILDING.md). The current target is game version **11.0.0**.
3. Match game version and relevant DLC configuration. Each PC keeps its own save and its own `netplay_id.txt`; do not copy that identity file between players.
4. Test that each PC can start an offline session (`Play SSBU Offline.bat`). Close it before switching to an online or host/join session.
5. For a private room, choose one person as host and agree on a room name, for example `smash`.

There is one local player per WindowSmash instance. A private relay can hold up to eight members; the game room's rules determine the actual supported match size.

## Online lobby (default)

1. `online_server.txt` names the lobby. The first line that is not a comment is `host:port`, optionally followed by a lobby code. It ships with the public lobby, `smash.recomps.wtf:39420`; to use a lobby your group runs instead, put its address there (see [Standalone relay or lobby](#standalone-relay-or-lobby)). Write `off` there to make `Play SSBU.bat` start offline.
2. Double-click **`Play SSBU.bat`**. The first time, it asks for the name other players see and keeps it in `online_name.txt`; edit or delete that file to change it.
3. If Windows Firewall asks, allow `ssbu.exe`. Players only send to the lobby, so no port forwarding is needed.
4. In the game's main menu, select **Local Wireless**. To host, select **Create a Room** and accept challengers. To join, open **Rooms List** and pick a room; open rooms come first, fuller ones before emptier ones.

Rooms are visible to everyone in the lobby with the same game version. For friends only, everyone adds the same **lobby code** after the address, for example `lobby.example.net:39420 ourcode`; the lobby lists rooms only to players with the same code. The code is not a password.

`Play SSBU Offline.bat` never goes online. If the lobby does not answer for five seconds, the game plays offline by itself and keeps trying in the background.

The overlay (**F1**) shows the connection, for example `Online: 37 players, 4 rooms - you are Alpha, ping 48 ms`, with the lobby code after `Online` when one is set. Each player's delay to another is roughly the sum of both players' pings to the lobby, so a lobby near the group plays best.

## Quick setup: host

1. Double-click **`Host SSBU Netplay.bat`**.
2. Enter your player name, agreed room name, and a UDP port. Keep **39420** unless you need another port.
3. If Windows Firewall asks, allow `ssbu.exe` on the appropriate network. A manually configured firewall must allow incoming **UDP** on the relay port.
4. The launcher attempts a UPnP port mapping. Give your friend the host address shown in `netplay_address.txt` or the game's details overlay (**F2**). An example address is `203.0.113.7:39420`.
5. In the game's main menu, select **Local Wireless**, the console-with-waves icon in the right sidebar.
6. Select **Create a Room**. When the challenger notice appears, accept your friend.

The example address above is documentation only. Use the address produced by your own host, or the VPN/LAN address described below.

## Quick setup: joining player

1. Double-click **`Join SSBU Netplay.bat`**.
2. Enter the host's address including port, your own player name, and the **exact same room name**.
3. Press **F2** in the game and check that the relay connection/player count looks correct.
4. Open **Local Wireless**, choose the host's room from **Rooms List**, and wait for acceptance.
5. If prompted for a Smash Tag, create your own tag.

Joining players make outbound connections to the relay. They do not need to forward ports on their own routers.

## Choose a reachable address

| Situation | Address for joining players | Setup |
| :--- | :--- | :--- |
| Same home network | Host's local LAN IP plus port | Permit inbound UDP in the host firewall. |
| Different networks, working UPnP | Host's reachable public IP plus port | Use the launcher's reported mapping and address. |
| Manual port forwarding | Host's reachable public IP plus port | Forward **UDP 39420** to the host PC's LAN IP; allow the same port in its firewall. |
| Shared virtual LAN / VPN | Host's VPN IP plus port | Both players join the same virtual network and permit traffic between peers. |
| Standalone relay | Relay server IP/hostname plus port | Every game instance uses the Join launcher. |

If your ISP uses carrier-grade NAT, or the router is behind another router, a home port forward may be insufficient. A shared virtual LAN or a reachable standalone relay is often the more practical route.

## Standalone relay or lobby

`tools/ssbu_relay.py` is the online lobby. It needs **Python 3.8+**, a reachable UDP port, and no game files:

```powershell
python tools/ssbu_relay.py --port 39420 --verbose
```

Allow inbound UDP 39420 on that machine and any network firewall in front of it. Then every player puts its address in `online_server.txt` and uses **Play SSBU.bat**. Using **Join SSBU Netplay.bat** with the lobby's address also works; the room name then acts as the lobby code. One player creates the Local Wireless room; the others select it.

`python tools/ssbu_relay.py --probe <address>` checks that a lobby answers. On a Linux server, `tools/deploy/deploy_lobby.sh <ssh host> install` installs it as a sandboxed systemd service (`ssbu-lobby`). The lobby logs a statistics line every minute, and `--banlist FILE` turns away the addresses or networks listed in that file, re-read when it changes.

The lobby checks message sources, rate-limits clients and carries each room's traffic only between that room's players, but it is still a transport for trusted players. Lobby codes and room names are not passwords; the protocol is not encrypted or authenticated.

## If the room does not appear

| Symptom | Check |
| :--- | :--- |
| Overlay stays on `connecting` | Host address/port, host process still running, inbound UDP rule, router mapping, and relay reachability. |
| Overlay says `no answer from … - playing offline` | The lobby in `online_server.txt` has not answered for five seconds. Check the address with `--probe`. |
| Online, a room is missing from the list | Both players need the same game version and the same lobby code (or none), and both overlays must say `Online`. The list refreshes every few seconds. |
| Both are connected but in different member groups | Room names must match exactly. |
| Relay count matches but Local Wireless room is missing | Host must create an in-game room; being connected to the relay alone does not create one. Wait for list refresh. |
| Two people look like one player | Each install needs its own identity. Close the game and **rename** the duplicated `netplay_id.txt` so a new one is generated. Keep each player's save. |
| Communication error after joining | Check packet loss, relay reachability, matching versions/configuration, and whether the host/relay closed or changed networks. |
| LAN works, internet does not | Investigate host firewall, UDP forwarding, double NAT/CGNAT, or use a virtual LAN/standalone relay. |
| Works but feels delayed | All traffic goes through the relay. Prefer a low-latency host near the other players. |

The host has no relay network hop to itself. Each joining player's path includes its connection to the relay; communication between joining players passes through that relay. The game's Local Wireless mode was designed for nearby peers, so internet latency can affect behavior.

## Logs and privacy

Launchers write `build/play.log`. For more network diagnostics, set `SSBU_NET_LOG=1` before launching; `2` logs individual calls. Logs and the overlay may contain player names, local paths, and IP addresses. Review excerpts before sharing them publicly.

## Environment reference

| Variable | Meaning |
| :--- | :--- |
| `SSBU_NET_HOST=1` | Start an integrated relay and join it locally. |
| `SSBU_NET_RELAY=address[:port]` | Join the online lobby or the relay at this address. |
| `SSBU_NET_ROOM` | Lobby code online, room name for a private relay; default `smash`, the public lobby. |
| `SSBU_NET_NAME` | Displayed player name. |
| `SSBU_NET_PORT` | Relay port; default `39420`. |
| `SSBU_NET_UPNP=0` | Disable automatic router mapping. |
| `SSBU_NET_BIND` | Restrict the integrated relay's bind address; used by local diagnostics. |
| `SSBU_NET_LOG=1` / `2` | Enable summary / more detailed network logging. |

Without a host or relay setting, the runtime stays offline. `Play SSBU Offline.bat` clears both; `Play SSBU.bat` sets the relay from `online_server.txt`, and the host and join launchers choose their corresponding modes.
