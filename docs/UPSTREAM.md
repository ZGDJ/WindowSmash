# Upstream provenance and architecture

Fork: [ZGDJ/WindowSmash](https://github.com/ZGDJ/WindowSmash). Parent: [SNO2207/WindowSmash](https://github.com/SNO2207/WindowSmash). Baseline: `4b512d2ad44f2312d47d5ba5746f96a27eda3653`.

`origin` is the fork; `upstream` is the parent. Integrate deliberately and revalidate affected fixtures. Translation, addresses, FP, threading and service changes can invalidate evidence. Never automatically reset/merge upstream.

The [preserved README](../README-UPSTREAM.md) describes upstream releases/features. This fork has no verified rollback release. The initial audit ran no game build/battle.

## Source seams

- [recomp.py](../tools/recomp.py), [lift.py](../tools/lift.py), [cc.py](../tools/cc.py): discovery, C emission, compilation.
- [recomp.h](../runtime/recomp.h), [host.c](../runtime/host.c): registers, direct guest addresses, native dispatch.
- [host.h](../runtime/host.h): HLE/HLE_WRAP interception. Upstream can omit unmatched wrappers; rollback hooks must be stricter.
- [kernel.c](../runtime/kernel.c), [hle_fiber.c](../runtime/hle_fiber.c), [hle_setjmp.c](../runtime/hle_setjmp.c): native continuation/synchronization outside RAM.
- [hle_hid.c](../runtime/hle_hid.c): player-one live input and wall-clock scripts.
- [ipc_vi.c](../runtime/ipc_vi.c): presentation, not battle tick.
- [gpu.c](../runtime/gpu.c), [gpu_d3d11.c](../runtime/gpu_d3d11.c), [ipc_audio.c](../runtime/ipc_audio.c): guest-visible writes and asynchronous effects.
- [hle_net.c](../runtime/hle_net.c), [net_relay.c](../runtime/net_relay.c): Local Wireless transport, not rollback.

See [baseline evidence](../evidence/2026-10-18-upstream-baseline.md). Preserve [NOTICE.md](../NOTICE.md): upstream does not specify a project-wide license for remaining source. Do not invent permissions or apply a blanket license. Distribution policy is a release prerequisite, separate from feasibility.
