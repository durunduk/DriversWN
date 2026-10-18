#!/usr/bin/env python3
"""
Append the build version to the Vulkan deviceName, e.g.
"Adreno (TM) 840 [WN dev-1018-0330]".

Why: WinNative's Vulkan wrapper and the game logs (UE: "Found D3D12 adapter
0: Wrapper(...)") show the device name, so the tag proves which driver build
is actually loaded. Without it a stale or not-reinstalled driver looks the
same as a new one. D3D12/Vulkan translation layers key their workarounds on
vendor/device IDs, not the name, so the suffix is harmless.

The tag comes from BUILD_VERSION (set by build_wn_turnip.sh / setup_and_build.sh).
Three-state per MAINTENANCE.md; idempotent.
"""

import os
import re
import sys

TU_DEVICE = "src/freedreno/vulkan/tu_device.cc"
MARK = "WN_DEVNAME_SUFFIX"

tag = os.environ.get("BUILD_VERSION", "").strip()
tag = re.sub(r"[^A-Za-z0-9._-]", "", tag)[:40] or "local"

ANCHOR = 'snprintf(props->deviceName, sizeof(props->deviceName), "%s",'
REPLACEMENT = 'snprintf(props->deviceName, sizeof(props->deviceName), "%s" WN_DEVNAME_SUFFIX,'
DEFINE = f'#define WN_DEVNAME_SUFFIX " [WN {tag}]"\n'


def main() -> int:
    with open(TU_DEVICE, "r") as f:
        content = f.read()

    if MARK in content:
        print(f"  {TU_DEVICE}: device name tag already present")
        print("wn_device_name_tag.py: done")
        return 0

    if ANCHOR not in content:
        print(f"  WARNING: {TU_DEVICE}: anchor absent for deviceName snprintf - skipping",
              file=sys.stderr)
        return 0

    content = content.replace(ANCHOR, REPLACEMENT, 1)
    first_include = content.find("#include")
    content = content[:first_include] + DEFINE + content[first_include:]

    with open(TU_DEVICE, "w") as f:
        f.write(content)
    print(f"  {TU_DEVICE}: deviceName suffix ' [WN {tag}]'")
    print("wn_device_name_tag.py: done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
