# Build from your own game files

> SmashRollback targets **13.0.5** from the start. This inherited guide also describes upstream 11.0.0; follow the [version guide](VERSIONS.md) for matching 13.0.5 inputs. A successful build does not prove rollback; see [milestones](../milestones/README.md).

[README](../README.md) · [Use a runtime release](RUNTIME-SETUP.md) · [Multiplayer](../NETPLAY.md) · [Technical guide](TECHNICAL.md)

The source tree contains the recompiler and host runtime. It does not contain the game's CPU code, assets, fonts, keys, firmware, or a prepared save. Keep those inputs local.

## Requirements

| Item | Requirement |
| :--- | :--- |
| Host | Windows 10/11, 64-bit. |
| CPU | AVX2, FMA, and F16C. |
| Graphics | A Direct3D 11-capable GPU and working Windows driver. |
| Python | **3.14** for the full workflow; `arc.py` uses `compression.zstd`. |
| C toolchain | Visual Studio 2022 or newer with **Desktop development with C++**, **C++ Clang Compiler for Windows**, and a Windows SDK. |
| Inputs | Your game version **11.0.0**, update already applied to RomFS, matching ExeFS, and your own firmware fonts. Package extraction also needs your own keys. |
| Storage | Allow space for the game image, extracted modules, generated C, object files, and maps. Several tens of GB may be required; a local bundle needs additional free space. |

Use a Python 3.14 virtual environment if other Python versions are installed:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`tools/cc.py` discovers Visual Studio's `clang-cl`. Set `SSBU_CLANG` to an explicit compiler path if needed. Discovery of Clang alone does not install the Windows SDK or C++ development components.

## Expected layout

```text
WindowSmash/
  runtime/                    # checked-in Windows runtime
  tools/                      # checked-in Python / diagnostic tools
  dump/
    exefs/                    # main, sdk, subsdk0, rtld, main.npdm
    modules/
      romfs.cfg               # RomFS image path, then byte offset
      aoc.cfg                 # optional installed DLC indices
    nro/                      # fighter/item modules; later bases.txt
    fonts/                    # six firmware font files
  build/                      # generated C, objects, exe, linker map
  save/                       # created locally when playing
```

`dump/`, `build/`, saves, keys, and generated packages are ignored by Git.

## 1. Prepare matching ExeFS

Extract the program modules from the Program NCA for the installed game version:

```powershell
python tools/nca.py exefs "D:\MyDump\program.nca" --keys "D:\MyKeys" --out dump/exefs
```

For a base game plus separate update, use the updated program code. For an already merged dump, verify the actual executable/content version rather than relying on a package filename or label. Do not mix executable code from one version with data from another.

## 2. Configure an unencrypted, patched RomFS

The runtime reads the RomFS in place. It must already contain the installed update, or be a layered RomFS that `tools/update.py` makes from your base and an update package (see [later game versions](UPDATES.md)).

For an extracted, patched RomFS image:

```powershell
python tools/nca.py romfs-cfg "D:\MyDump\romfs.bin" --out dump/modules/romfs.cfg
```

For a merged Program NCA whose readable RomFS section is supported by the tool:

```powershell
python tools/nca.py romfs-cfg "D:\MyDump\program.nca" --keys "D:\MyKeys" --out dump/modules/romfs.cfg
```

For a separate base/update pair, either prepare the patched image using your own extraction workflow, or let `tools/update.py` layer the update over your base in a version folder of its own ([later game versions](UPDATES.md)). Encrypted or unmerged images are not interchangeable with the unencrypted RomFS the runtime expects.

`romfs.cfg` has exactly the runtime information needed:

```text
D:\MyDump\romfs.bin
0
```

An embedded RomFS uses its actual byte offset instead of zero. Keep the referenced file available whenever the game runs.

## 3. Extract the embedded fighter modules

```powershell
python tools/arc.py info
python tools/arc.py nro
```

`arc.py` finds `data.arc` through the configured RomFS and extracts known modules from its internal `prebuilt:/nro/release/` directory into `dump/nro/`. This is necessary because the complete fighter set is not just a collection of loose NRO files in the RomFS.

The next build assigns module bases and records them in `dump/nro/bases.txt`. Keep this file with your local build inputs. It is not a file to copy from an unrelated build/version.

## 4. Supply firmware fonts

Extract the following from your own firmware shared-font archives into `dump/fonts/`:

```text
nintendo_udsg-r_std_003.bfttf
nintendo_udsg-r_org_zh-cn_003.bfttf
nintendo_udsg-r_ext_zh-cn_003.bfttf
nintendo_udjxh-db_zh-tw_003.bfttf
nintendo_udsg-r_ko_003.bfttf
nintendo_ext_003.bfttf
```

For each relevant archive, the extraction command is:

```powershell
python tools/nca.py romfs-get "D:\MyFirmware\font-archive.nca" --keys "D:\MyKeys" --match .bfttf --flat --out dump/fonts
```

The filenames above are required inputs, not files included in this source repository or runtime release.

## 5. Optional codecs

To build with Opus audio decoding, provide your static `.lib` files through `SSBU_OPUS_LIBS`, separated by semicolons:

```powershell
$env:SSBU_OPUS_LIBS = 'D:\Codecs\opus.lib;D:\Codecs\opus_sse41.lib'
```

To build with VP9 movie decoding, set `SSBU_VPX_DIR` to a directory containing `include/` and `lib/Win64/Release/libvpx.lib`:

```powershell
$env:SSBU_VPX_DIR = 'D:\Codecs\libvpx'
```

Supply libraries compatible with the Windows x64 toolchain. Without the optional libraries, the associated decoding paths are omitted. See [`tools/cc.py`](../tools/cc.py) for the exact link configuration.

## 6. Optional installed DLC list

Generate the list from your own registered installed-content metadata:

```powershell
python tools/nca.py aoc-cfg "D:\MyDump\registered" --keys "D:\MyKeys" --out dump/modules/aoc.cfg
```

Then rerun `arc.py nro` before compiling so DLC fighter code is present. [DLC setup and save unlocking](DLC-AND-UNLOCKS.md) are separate steps.

## 7. Compile

Close the game before linking, then run:

```powershell
python tools/recomp.py all dump/exefs --out build --jobs 16
```

Use a job count that fits available CPU and memory. The driver translates modules, generates relocation images and registries, compiles objects, compiles the runtime, and links `build/ssbu.exe`. Repeated builds are incremental.

A complete initial build can take a substantial amount of time. This repository does not claim a portable build-time benchmark. A successful compile also does not prove that every game mode is compatible.

## 8. Start and verify

Run **`Play SSBU.bat`** from the root folder. Logs go to `build/play.log`; F1 toggles the overlay and F2 shows more details.

If a fighter module is harvested at runtime, extract/collect the missing module and rebuild. If the runtime traps, preserve the relevant log section and the matching build revision. Locally generated linker maps can help diagnose host frames.

For play with another person, follow the dedicated **[multiplayer setup guide](../NETPLAY.md)**.

## Tests and local packaging

Install optional test tools with `requirements-dev.txt`. The [technical guide](TECHNICAL.md#verification-and-debugging) covers source-only tests and game-backed differential checks.

`Bundle Latest SSBU.bat` packages an existing local installation; `--dry-run` validates the inputs without creating an archive. The local bundle includes game-derived content and stays out of Git. Public runtime releases use a smaller file set and require separately supplied assets, as described in [runtime setup](RUNTIME-SETUP.md).
