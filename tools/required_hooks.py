"""Strict source declarations for critical hooks; no game addresses are registered here.

Immediately precede a signature and HLE_WRAP with:
  /* rollback-required: <module> <full 64-hex build ID> <64-hex file SHA256> */
The ordinary HLE_WRAP macro remains unchanged. Only the Windows all-build path can
link required hooks, after freshly generating their modules in that invocation.
"""
from pathlib import Path
import re


def declarations(runtime):
    required, counts = {}, {}
    pattern = re.compile(
        r"/\* rollback-required: ([A-Za-z_][A-Za-z0-9_]*) ([0-9a-fA-F]{64}) ([0-9a-fA-F]{64}) \*/\n"
        r"/\* signature: ([0-9a-f. ]+) \*/\nHLE_WRAP\(([0-9a-fA-F]+)\)\s*\{")
    for path in sorted(Path(runtime).glob("*.c")):
        text = path.read_text(encoding="utf-8")
        for address in re.findall(r"^HLE_WRAP\(([0-9a-fA-F]+)\)", text, re.M):
            address = int(address, 16)
            counts[address] = counts.get(address, 0) + 1
        lines = text.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if "rollback-required" not in line:
                continue
            match = pattern.match("".join(lines[index:index + 3]))
            if not match:
                raise ValueError(f"{path.name}:{index + 1}: malformed/orphan rollback-required declaration")
            module, build_id, sha256, signature, address = match.groups()
            words = signature.split()
            if not words or any(not re.fullmatch(r"[0-9a-f.]{8}", word) for word in words) or all(set(word) == {"."} for word in words):
                raise ValueError(f"{path.name}:{index + 1}: required hook needs a nonempty code signature")
            address = int(address, 16)
            if address in required:
                raise ValueError(f"duplicate required HLE_WRAP({address:x})")
            required[address] = {"module": module, "build_id": build_id.upper(), "sha256": sha256.lower(), "signature": words}
    for address in required:
        if counts.get(address) != 1:
            raise ValueError(f"required HLE_WRAP({address:x}) must have exactly one declaration")
    return required


def reject_unvalidated_builder(runtime, builder):
    if declarations(runtime):
        raise ValueError(f"required hooks are unsupported by {builder}; use the validated Windows recomp.py all path")
