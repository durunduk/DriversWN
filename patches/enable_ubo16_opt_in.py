#!/usr/bin/env python3
"""
Opt-in uniformAndStorageBuffer16BitAccess for Turnip: set TU_UBO16=1.

Why: the vkd3d-proton WinNative ships (3.0.1-arm64ec-sm69, build f1338a56,
July 2026) reports D3D12 Native16BitShaderOpsSupported only when the device
has shaderFloat16, shaderInt16, uniformAndStorageBuffer16BitAccess,
shaderDenormPreserveFloat16 (with denorm independence) and
minStorageBufferOffsetAlignment <= 16. Turnip meets all of them on A8XX
except uniformAndStorageBuffer16BitAccess, which it hard-codes to false, so
every compute PSO using 16-bit operations fails with E_INVALIDARG. Seen on
Styx: Blades of Greed (UE 5.6, Adreno 840): 48 rejected PSOs.
(Newer vkd3d-proton checks storageBuffer16BitAccess instead, so this only
matters for the older builds; it is harmless with newer ones.)

Whether ir3 handles every 16-bit UBO load correctly is not verified, so the
feature stays off unless TU_UBO16=1 is set; without it the driver behaves
exactly like upstream. It is never reported without props.storage_16bit.

Three-state per MAINTENANCE.md; idempotent.
"""

import re
import sys

TU_DEVICE = "src/freedreno/vulkan/tu_device.cc"
MARK = "/* WN: TU_UBO16 opt-in */"

ANCHOR = re.compile(r"features->uniformAndStorageBuffer16BitAccess(\s*)=\s*false;")
REPLACEMENT = (
    r"features->uniformAndStorageBuffer16BitAccess\1= " + MARK + "\n"
    "      pdevice->info->props.storage_16bit &&\n"
    "      getenv(\"TU_UBO16\") && atoi(getenv(\"TU_UBO16\")) != 0;"
)
INCLUDE = "#include <stdlib.h> " + MARK + "\n"


def main() -> int:
    with open(TU_DEVICE, "r") as f:
        content = f.read()

    if MARK in content:
        print(f"  {TU_DEVICE}: TU_UBO16 opt-in already present")
        print("enable_ubo16_opt_in.py: done")
        return 0

    updated, count = ANCHOR.subn(REPLACEMENT, content, count=1)
    if count == 0:
        print(f"  WARNING: {TU_DEVICE}: anchor absent for "
              "'uniformAndStorageBuffer16BitAccess = false' - upstream changed it? skipping",
              file=sys.stderr)
        return 0

    # getenv/atoi: include <stdlib.h> before the first #include of the file.
    first_include = updated.find("#include")
    if first_include < 0:
        print(f"  WARNING: {TU_DEVICE}: no #include found - skipping", file=sys.stderr)
        return 0
    updated = updated[:first_include] + INCLUDE + updated[first_include:]

    with open(TU_DEVICE, "w") as f:
        f.write(updated)
    print(f"  {TU_DEVICE}: uniformAndStorageBuffer16BitAccess now opt-in via TU_UBO16=1")
    print("enable_ubo16_opt_in.py: done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
