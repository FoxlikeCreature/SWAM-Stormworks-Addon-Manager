"""Check the property tracer against real Lua.

Runs every installed addon's script in a Lua interpreter with property.*
stubbed, once per property with the value changed, and diffs the resulting
g_savedata. Whatever moves is where the addon really keeps that setting.
That is the ground truth the static tracer in swam/properties.py has to
agree with.

Needs a lua binary (any 5.x). Dev tool, not part of SWAM itself.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from swam import paths, properties

PROBE = Path(__file__).with_name("trace_probe.lua")
LUA = os.environ.get("LUA", "lua5.4")


def run(script, overrides):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".ov") as f:
        for k, v in overrides.items():
            f.write(f"{k}\1{v}\n")
        ov = f.name
    try:
        r = subprocess.run(
            [LUA, str(PROBE), str(script), ov],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return None
    finally:
        os.unlink(ov)
    out = {}
    for line in r.stdout.splitlines():
        if "\1" in line:
            k, v = line.split("\1", 1)
            out[k] = v
    return out


def other_value(p):
    if p.kind == "checkbox":
        return "false" if p.default else "true"
    if p.kind == "slider":
        return str(p.maximum if float(p.default) != float(p.maximum) else p.minimum)
    return "SWAM_PROBE_VALUE"


def main():
    missions = paths.sw_root() / "data" / "missions"
    tally = {"agree": 0, "wrong": 0, "missed": 0, "extra": 0, "not stored": 0}
    for d in sorted(missions.iterdir()):
        script = d / "script.lua"
        if not script.is_file() or script.stat().st_size == 0:
            continue
        props = properties.parse_schema(script.read_text(errors="replace"))
        if not props:
            continue
        base = run(script, {})
        if base is None:
            print(
                f"  skipped {d.name}: the script does not terminate "
                f"outside the game"
            )
            continue
        for p in props:
            after = run(script, {p.label: other_value(p)})
            if after is None:
                continue
            real = {
                tuple(k.lstrip(".").split("."))
                for k in set(base) | set(after)
                if base.get(k) != after.get(k)
            }
            mine = (
                tuple(str(x) for x in p.saved_path)
                if p.saved_path is not None
                else None
            )
            if not real:
                if mine is None:
                    tally["not stored"] += 1
                else:
                    tally["extra"] += 1
                    print(
                        f"  EXTRA  {d.name} | {p.label} -> {mine} "
                        f"(nothing moves at world creation; it may still "
                        f"be a value the addon persists later)"
                    )
            elif mine is None:
                tally["missed"] += 1
                print(
                    f"  MISSED {d.name} | {p.label} really lives at " f"{sorted(real)}"
                )
            elif mine in real:
                tally["agree"] += 1
            else:
                tally["wrong"] += 1
                print(
                    f"  WRONG  {d.name} | {p.label}: traced {mine}, "
                    f"really {sorted(real)}"
                )
    print()
    for k, v in tally.items():
        print(f"  {k:11} {v}")
    return 1 if tally["wrong"] or tally["missed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
