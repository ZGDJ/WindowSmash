# Several game versions

[README](../README.md) · [Build guide](BUILDING.md) · [Later versions](UPDATES.md) · [Technical guide](TECHNICAL.md)

A checkout can hold several versions of the game side by side, each in a folder of its own,
installed and built with one command. What versions have in common is shared, not built again.

## The folders

A version's folder is laid out like the port's own tree:

| Folder | What |
| :--- | :--- |
| `dump/` | The game: `exefs/` (its program), `modules/` (`romfs.cfg` and the RomFS files, `aoc.cfg` for DLC), `nro/` (the fighter modules), `fonts/`, `shadercache/`. |
| `build/` | The recompiled game, `build/ssbu.exe`. |
| `save/` | **Its own save.** It starts as a copy of the port's `save/`; each version's game keeps its own from then on. |
| `version.txt` | Which version it is: e.g. `13.0.5`, then main's build ID, data.arc's version and the update used. |
| `install.json` | What it was installed from, for the next run. |

The port's own tree (`dump/`, `build/`, `save/`) holds the base game. The others are named after
their version, e.g. `v13.0.5/`. Name new ones `v<version>`: Git ignores those.

## Starting a version

**Play SSBU.bat** lists the versions that are built and asks which one to start. The last one
picked is the default (remembered in `last_version.txt`). With only one built, it starts that one
straight away. **Host SSBU Netplay.bat** and **Join SSBU Netplay.bat** ask the same way, then work
as before. **Every player needs the same version.**

**Unlock All Fighters.bat** asks too. It only changes a version whose save layout it knows, and
refuses the others: see the [DLC/unlock guide](DLC-AND-UNLOCKS.md).

Setting `SSBU_TREE` to a version's folder before starting a launcher skips the question.

## Installing a version

One command, from the checkout, with your own update package, DLC and keys (example paths):

```powershell
python tools/install_version.py install --tree v13.0.5 --update "D:\MyDump\update.nsp" --dlc "D:\MyDump\dlc" --keys "D:\MyKeys"
```

- Without `--update`, the base itself goes into the folder (e.g. `--tree v11.0.0`).
- Without `--dlc`, no DLC.
- The base is the port's own `dump/modules/romfs.cfg`; `--base` takes another.
- `--keys` can be left out when `SSBU_KEYS` names the keys folder.

It does, in order:

1. **exefs**: the update's program, or the base's.
2. **romfs**: the update applied over the base's RomFS (`tools/update.py`, a few minutes: see
   [later game versions](UPDATES.md)), or for the base itself its own `romfs.cfg`.
3. **aoc**: `aoc.cfg`, from the DLC packages in `--dlc` (`.nsp` files, or a registered-content
   folder).
4. **nro**: every fighter module, taken out of that version's data.arc.
5. **extras**: `dump/fonts` and `dump/shadercache` copied from the port's own `dump/`, and `save/`
   copied from the port's `save/`, each only if the folder has none yet.
6. **version**: `version.txt`.
7. **build**: `tools/recomp.py all`, which first checks every module's imports, then builds
   `build/ssbu.exe`, reusing what other versions already built.

A step whose inputs haven't changed since the last run is skipped (`install.json`), so running
the command again carries on from where it stopped, or just rebuilds.

- `--redo romfs` (or any steps, comma-separated) does steps again anyway.
- `--no-build` stops before the build.
- The command refuses the port's own tree, and a folder made before it existed, unless `--force`.

`python tools/install_version.py list` shows the versions. `describe --tree <folder>` writes
`version.txt` for a folder that has none; until then the launchers show the folder's name.

## What versions share

**Modules.** A game is several modules: `main`, `subsdk0`, `sdk`, and about 100 fighter modules
(NROs). Each has a build ID. Its recompiled code depends only on its bytes, the address it's
built for and the tools.

`sdk` and `subsdk0` are byte-identical from 11.0.0 to 13.0.5, and fighter modules can be the same
between nearby updates. When a version needs a module that another version's folder already built
(same build ID, same address), its build files are taken from there. They're hard links when the
folders are on the same drive (instant, no extra space), copies otherwise. The tools always write
a changed file as a new one, so one version never changes another's files.

Each module's build folder has a `module.txt` stamp: build ID, address, name, and a fingerprint of
the tools that generated it (the recompiler's sources and the runtime's list of native functions).
With the same fingerprint, the C isn't generated again; it's only checked for objects to compile.
After a change to the recompiler, the C is generated again. On Windows, each compilation batch
also has a separate `compile.txt` content stamp: source contents, runtime headers, compiler,
flags and optimization must match before its objects are reused. A changed shared compile
identity rebuilds the batch; a source-only change rebuilds affected files. Legacy folders
without this stamp rebuild objects once. Failed/interrupted batches cannot publish a valid
stamp, and rebuilding an adopted hard link leaves its donor intact.

Use `recomp.py all` (or `compile` before `link`) after changes; standalone `link` expects its
module directories already compiled. External Windows SDK/codec headers changed in place
still require a fresh build: use an isolated checkout with no donor build trees so automatic
adoption cannot restore those objects. Do not run concurrent writers against one build folder.
The separate Linux build path retains its own cache policy and is outside this Windows gate.

**Fighter module addresses.** Every module is built for a fixed address. `module_bases.txt` in
the checkout keeps one address per build ID for all versions, seeded from each folder's
`dump/nro/bases.txt`, so the same module gets the same address everywhere and can be shared.

- A new module gets an address past every other version's, so no version's modules get in
  another's way.
- Modules can't share a 16 MB slot, and fighter modules have 512 slots
  (0x7200000000-0x7400000000). Each version with all-new fighter modules takes about 100.
- When that space is used up, new modules take any slots free in their own version. That still
  works, but shares less.

**Fonts and shaders** are copied once per version. The shader cache is keyed by shader, so each
version reuses what the others compiled.

## The RomFS: exact or rebuilt

An update's RomFS is a patch over the RomFS of the game's original release. When the base **is**
that original release, unpacked as a plain NCA, the patch applies exactly. `update.py` tries that
first: it checks 256 blocks across the image against the update's hashes. If they match, every
piece is taken as the patch says.

When the base has an earlier update merged in, `update.py` finds each piece of the original in it
instead (see [later game versions](UPDATES.md)). Either way, the result is checked block by block
against the update's hashes at the end.

## Code tied to one version

- **Debug hooks in the runtime** (`HLE_WRAP(<address>)` in `runtime/hle_net.c`) wrap a guest
  function at an 11.0.0 address. Each has a code signature on the line above it: its first
  instructions, with addresses masked out. `tools/recomp.py wrap-sig <module> <address>` prints
  one.
  - In another version, the recompiler checks that the function at that address still matches.
  - If it doesn't, the recompiler looks for the signature elsewhere and wraps what it finds.
  - If it finds nothing, it leaves the hook out, and the link still works: the original's name is
    linked to a stub (`rt_wrap_missing`).
- **Unlock All Fighters** writes at save offsets worked out on 11.0.0. It reads which version a
  folder is (main's build ID) and refuses any version whose layout it doesn't know. 13.0.5 uses
  the same offsets. For a new version, add its build ID to `LAYOUTS` in `tools/unlock_all.py` and
  `$knownLayouts` in `tools/Unlock-All-Fighters.ps1`, but only after checking that its save
  matches.

## The imports check

Before compiling, `recomp.py all` lists each module's imported symbols that no module exports and
the runtime doesn't implement. `recomp.py check <exefs>` runs that check on its own. The list is
written to `build/imports.unresolved.txt`.

- A **strong** import there would trap if called, so a new version that needs a new native
  function shows up here first.
- **Weak** ones read as 0 and are normal. 11.0.0 and 13.0.5 both have 0 strong and about 410 weak.

## Disk space

Per version:
- the update's own RomFS data (`romfs_patch.bin`, 3.6 GB for 13.0.5);
- the shader cache copy (about 0.5 GB);
- the build: nothing while its files are links to another version's, about 5 GB otherwise.

Deleting a version's folder deletes only that version. Other versions keep their own links, and
its addresses stay reserved in `module_bases.txt`.
