#!/usr/bin/env python3
"""
A8XX: emit CP_WAIT_FOR_ME for barriers whose destination is vertex/index fetch.

tu_flush_for_stage() already emits CP_WAIT_FOR_ME right away on a8xx when the
destination stage is TU_STAGE_BV_CP (indirect parameters), because a8xx dropped
the implicit wait earlier GPUs had. The same is needed when the destination is
TU_STAGE_BV (vertex input, index fetch, pre-raster shaders): the WFI alone does
not stop BV from reading data written before the barrier.

Seen on Styx: Blades of Greed (UE 5.6 through vkd3d-proton 0bb64c56, Adreno 840):
the second level renders shattered geometry; TU_DEBUG=flushall hides it.
Bisected by adding waits per barrier category:
  CP_WAIT_FOR_ME at barriers with dst TU_STAGE_BV        clean
  CP_WAIT_MEM_WRITES at the same barriers                broken
  waits only for dst TU_STAGE_BV_CP or TU_STAGE_BR       broken
  waits only at barriers outside a render pass           clean
  waits only at barriers inside a render pass            broken
CP_WAIT_FOR_ME only stalls the CP, so the cost is small. Older GPUs unchanged.

Three-state per MAINTENANCE.md; idempotent.
"""

import re
import sys

TU_CMD = "src/freedreno/vulkan/tu_cmd_buffer.cc"
MARK = "WN: a8xx BV wait-for-ME"

ANCHOR = re.compile(
    r"(?P<indent>[ \t]*)if \(dst_stage == TU_STAGE_BV_CP\) \{\n"
    r"(?P<body>[ \t]*if \(CHIP >= A8XX\)\n"
    r"[ \t]*cache->flush_bits \|= TU_CMD_FLAG_WAIT_FOR_ME;\n"
    r"[ \t]*else\n"
    r"[ \t]*cache->pending_flush_bits \|= TU_CMD_FLAG_WAIT_FOR_ME;\n)"
    r"(?P=indent)\}\n"
)


def main() -> int:
    with open(TU_CMD, "r") as f:
        content = f.read()

    if MARK in content:
        print(f"  {TU_CMD}: a8xx BV wait-for-ME already present")
        print("fix_a8xx_bv_wait_for_me.py: done")
        return 0

    m = ANCHOR.search(content)
    if not m:
        print(f"  WARNING: {TU_CMD}: anchor absent for the TU_STAGE_BV_CP "
              "wait-for-ME block in tu_flush_for_stage() - upstream changed or "
              "absorbed it? skipping", file=sys.stderr)
        return 0

    ind = m.group("indent")
    added = (
        f"{ind}}} else if (CHIP >= A8XX) {{\n"
        f"{ind}   /* {MARK}: the WFI alone does not keep BV's vertex/index\n"
        f"{ind}    * fetch from reading data written before the barrier\n"
        f"{ind}    * (UE5 through vkd3d-proton, Adreno 840).\n"
        f"{ind}    */\n"
        f"{ind}   cache->flush_bits |= TU_CMD_FLAG_WAIT_FOR_ME;\n"
        f"{ind}}}\n"
    )
    replacement = (
        f"{ind}if (dst_stage == TU_STAGE_BV_CP) {{\n" + m.group("body") + added
    )
    content = content[:m.start()] + replacement + content[m.end():]

    with open(TU_CMD, "w") as f:
        f.write(content)
    print(f"  {TU_CMD}: CP_WAIT_FOR_ME for barriers into TU_STAGE_BV on a8xx")
    print("fix_a8xx_bv_wait_for_me.py: done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
