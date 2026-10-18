# Super Smash Bros. Ultimate (native port) on Linux

> Inherited documentation. SmashRollback initially targets Windows x64; Linux rollback is out of scope. See the [fork README](README.md).

The same recompiled game as the Windows build, as a native x86-64 Linux program. The renderer is
still the Direct3D 11 one, running on Vulkan through **DXVK**. Its shaders are compiled by
**vkd3d-shader** when they aren't already in the shader cache, and the cache from the Windows
build ships with this folder. The window, controllers and sound use **SDL2**.

It's the game version of the tree it was built from: the port's own (11.0.0), or an update's
folder made by `tools/update.py` (for example 13.0.5). `dump/port.txt` says which.

This folder holds the game's code and data. It's for your own machines, not for sharing.

## What you need

- 64-bit Linux with glibc 2.35 or newer: Ubuntu 22.04 or later, Debian 12 or later, Fedora 36
  or later.
- A CPU with AVX2 (Intel Haswell / AMD Excavator or newer). Virtual machines normally pass it
  through.
- A Vulkan driver. Mesa's (`mesa-vulkan-drivers`) covers AMD, Intel and, without a GPU, the
  software renderer *lavapipe*. NVIDIA needs its proprietary driver.
- About 6 GB of RAM for the game on top of the desktop, so 12 GB or more for the whole machine
  is comfortable.
- The game data: the files the Windows build reads its RomFS from (its `romfs.cfg`). That's one
  NCA or RomFS image or, for an update's folder, the base game's file and the update's
  `romfs_patch.bin`.

## Setting up

1. Copy this folder (`ssbu-linux`) to the Linux machine. Use `ssbu-linux.tar` if you have it:
   `tar xf ssbu-linux.tar`. The tar keeps the programs executable. Copying the folder also works,
   because the launchers fix that.
2. Install what the game needs from the system (SDL2, Vulkan, zenity):

       bash install-deps.sh

3. Make the game data reachable. The game reads its RomFS in place, without extracting
   anything. For an update it's pieced together from two files by the layer map
   `dump/modules/romfs.layers`, which ships with this folder.

   Either:
   - copy those files into `ssbu-linux/game/`, or
   - in a **VMware** virtual machine, share the Windows folder that holds them instead (*VM >
     Settings > Options > Shared Folders*, set to *Always enabled*). It appears under
     `/mnt/hgfs/`, and the launchers search there. If `/mnt/hgfs` is empty, mount it with
     `sudo mkdir -p /mnt/hgfs && sudo vmhgfs-fuse .host:/ /mnt/hgfs -o allow_other`.

   The launchers know each file by its name and size, as the Windows build had them when this
   folder was made, and find them on their first run. They search this folder, `game/`,
   `/mnt/hgfs`, `/media`, `/mnt` and your home folder, then note where the files are in
   `dump/modules/romfs.cfg`. If a file moves, they look for it again. If one can't be found,
   they say its name and where it was on Windows. To point at the files yourself, which also
   skips searching a large shared folder, use `SSBU_NCA=/path/to/<the game's file>` and, for an
   update, `SSBU_ROMFS_PATCH=/path/to/romfs_patch.bin`, for example
   `SSBU_ROMFS_PATCH=~/romfs_patch.bin bash run.sh`. The launchers remember them after that.
4. Play:

       bash run.sh

   The log goes to `build/play.log` and to the terminal.

   `run.sh` plays online, as `Play SSBU.bat` does on Windows. The game joins the online lobby
   named in `online_server.txt`, and Local Wireless lists every room that players of the same
   game version create, on Windows or Linux (see `NETPLAY.md`). The first time, it asks for the
   name other players see, and keeps it in `online_name.txt`. To play offline, use
   `bash run-offline.sh`, or write `off` in `online_server.txt`. If the lobby doesn't answer, the
   game plays offline by itself after a few seconds.

## In a VMware virtual machine

- Turn on **Accelerate 3D graphics** (*VM > Settings > Display*).
- VMware gives Linux guests OpenGL but, as far as Mesa's drivers go, **no Vulkan GPU driver**.
  So DXVK runs on **lavapipe**, Mesa's software Vulkan renderer, which draws on the CPU. The
  log then says `[gfx] note: this is a software renderer`. Everything works, but the frame rate
  is low, especially in matches. A real GPU with a Vulkan driver should run at full speed, as
  the same renderer path does on Windows, but that hasn't been measured on Linux yet.
- To see what holds the frame rate back, press **F2**. *Present blocked … ms/frame* is the time
  the game waits each frame for the renderer to finish drawing, and *renderer … ms/frame*
  includes that wait. When nearly all of the renderer's time is the wait, it's the software
  renderer. In `top -H`, its threads are `llvmpipe-0`, `llvmpipe-1` and so on.
- More virtual CPU cores help the software renderer most (*VM > Settings > Processors*). With 4,
  menus run at only a few frames per second. Give the VM as many as the host can spare.
- See which Vulkan device you have: `vulkaninfo --summary`.
- Give the VM enough memory. 8 GB is tight with a desktop, and 12 to 16 GB is better.
- Saving the VM's settings while *Shared Folders* is set to *Disabled* turns sharing off. Set it
  to *Always enabled*.
- **Netplay from the VM**: playing online (`run.sh`) and joining someone else's private room
  work with VMware's default NAT networking, because the game only sends to the server. Hosting
  a private room (`host-netplay.sh`) is different: other PCs can't reach a relay running inside
  the VM. Either switch the VM's network adapter to *Bridged*, or forward UDP port 39420 in
  *Edit > Virtual Network Editor > VMnet8 > NAT Settings*.

## Controls

Same as on Windows:

- **Gamepad**: the first one SDL finds, laid out by position like an Xbox pad. The bottom face
  button is the console's B, and so on.
- **Keyboard** (while the window has focus):
  - Arrow keys move.
  - Z / X / C / V are A / B / X / Y.
  - A / S are L / R, and Q / W are ZL / ZR.
  - Enter is +, Backspace is -.
  - I / J / K / L move the right stick.
- **F1** overlay, **F2** details, **F3** screenshot (`screenshots/`), **F4** log a frame,
  **F5** depth sampling on/off, **F6** 10-second profile (`build/profile_*.txt`).
- **F11** or **Alt+Enter**: full screen.

When the game asks for text (a name, a Smash Tag), a `zenity` text box opens.

## Other launchers

- `run-offline.sh`: the game without going online, as `Play SSBU Offline.bat` on Windows.
- `host-netplay.sh` and `join-netplay.sh`: a private room, as `Host/Join SSBU Netplay.bat` on
  Windows (see `NETPLAY.md`). Every player needs the same game version: 13.0.5 can't play with
  11.0.0.
- `unlock-all-fighters.sh`: the unlock tool, on this folder's save. Run it with the game
  closed. Like `Unlock All Fighters.bat` on Windows, it knows the save layouts of 11.0.0 and
  13.0.5 (it reads which one this folder's game is) and changes nothing for another version.

## Saves

`save/` is a copy of the Windows save of the same game tree (its `save\` folder), taken when this
folder was made. The two don't sync with each other: copy `save/` back to that folder on Windows
to carry progress back. Unpacking a newer `ssbu-linux.tar` over this folder replaces `save/`
too, so keep a copy of it first. It also replaces `online_server.txt`, while `online_name.txt`
stays.

## If something goes wrong

- **"Some libraries the game needs are not installed"**: run `bash install-deps.sh`.
- **Black window, or `cannot create the window` / DXVK errors in the log**: run
  `vulkaninfo --summary`. If it lists no device, install `mesa-vulkan-drivers`.
- **No sound**: SDL uses PulseAudio or PipeWire. Check the log for `[audio]`.
- **A crash**: the log's last lines name the guest function and host frames (`*** host
  exception`). Keep `build/play.log` for a report.
- `SSBU_WRITE_WATCH=protect` makes the renderer track CPU writes with page protection instead
  of the kernel's write tracking (`userfaultfd` + `PAGEMAP_SCAN`, Linux 6.7 and later). Use it
  only to rule that out. The log's first lines say which one is in use.

## Building it

The Linux program is cross-compiled on Windows, next to the Windows build. It compiles the same
generated C again, so build the game tree for Windows first (`tools/recomp.py`; for an update's
folder, `--tree`). You also need Visual Studio's Clang (`clang.exe` and `ld.lld.exe`; or name
their folder in `SSBU_LLVM_BIN`) and Python 3.

The third-party parts go in `linux-toolchain/`, next to the checkout (or the folder named in
`SSBU_LINUX_TOOLCHAIN`):

| Folder | What goes there |
|---|---|
| `sysroot/` | These Ubuntu 22.04 (jammy) amd64 packages, each `.deb`'s data archive extracted into it: `libc6`, `libc6-dev`, `linux-libc-dev`, `libgcc-s1`, `libgcc-11-dev`, `libstdc++6`, `libsdl2-2.0-0`, `libsdl2-dev`, `libopus-dev`, `libvpx-dev`. Linking against 22.04's glibc keeps the program runnable on 22.04 and anything newer. |
| `dxvk-native/` | DXVK's native Linux build, version 3.1.1 (`dxvk-native-3.1.1-steamrt-sniper.tar.gz` from DXVK's releases), so that `dxvk-native/usr/lib` holds `libdxvk_d3d11.so.0` and `libdxvk_dxgi.so.0`. |
| `dxvk-headers/include/native/` | `include/native` from the DXVK 3.1.1 source, with mingw-directx-headers in its `directx/` folder (the commit DXVK 3.1.1 uses, `9df86f2`). |
| `src/vkd3d-2.1/` | The vkd3d 2.1 source. |
| `src/SPIRV-Headers-<version>/` | SPIRV-Headers, for example `vulkan-sdk-1.4.363.0`. |
| `winflexbison/` | win_flex_bison 2.5.25 (`win_bison.exe`, `win_flex.exe` and `data/`), for vkd3d's parsers. |
| `dxvk-win/dxvk-3.1.1/` | Optional: DXVK 3.1.1 for Windows, for `tools/linux/wintest.py`. |

Then, from the checkout:

```bash
python tools/linux/build_vkd3d.py linux
```

```bash
python tools/linux/build_linux.py --jobs 16
```

```bash
python tools/linux/package_linux.py --tar
```

- `build_vkd3d.py` builds vkd3d-shader once.
- `build_linux.py` builds the game tree it finds (a built `v13.0.5` folder first, else the
  port's own) into `build-linux/ssbu`, about 1.2 GB, with `ssbu.syms` for the profiler.
  `--port <tree>` names another tree. Each output folder holds one tree's game, so build another
  tree's into its own `--out` (for example `build-linux-11.0.0`). The first build compiles every
  game file again, about 25 minutes with 20 jobs. Later builds only redo what changed.
- `package_linux.py` makes `dist-linux/ssbu-linux` from it, and `ssbu-linux.tar` with `--tar`.
  `--build` and `--out` package another tree's build.

To check the Linux renderer path without a Linux machine, `python tools/linux/wintest.py --vkd3d`
builds the Windows program with this runtime drawing through DXVK and compiling its shaders with
vkd3d-shader. `tools/linux/wintest_run.sh <program> <name>` runs it through the menus (no
match) with copies of the save and shader cache, and `tools/linux/compare_shots.py` compares two
such runs' captures.
