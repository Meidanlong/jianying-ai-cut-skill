#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕保护：修正剪辑决策单，任何有语音(字幕)的说话段绝不删除，只删无言停顿。
用法: python fix_plan.py [决策单.json] [字幕.srt]
  - 不传参时默认 <out>/compact_result.json 与 <out>/transcript.srt
会备份原决策单为 <决策单>.bak.json，并把受保护后的删除区间写回。
"""
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import out_dir, load_env, ts2sec, sec2ts  # noqa: E402


def srt_segments(srt_text: str) -> list:
    lines = [l.strip() for l in srt_text.splitlines() if l.strip()]
    segs = []
    for i in range(0, len(lines), 3):
        m = re.match(r"(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)", lines[i + 1])
        if m:

            def s(t):
                h, mn, r = t.split(":")
                ss, ms = r.split(",")
                return int(h) * 3600 + int(mn) * 60 + int(ss) + int(ms) / 1000

            segs.append((s(m.group(1)), s(m.group(2))))
    return segs


def protect(deletes: list, speech: list, pad: float = 0.2) -> list:
    """从每个删除区间中挖掉被语音覆盖的部分，只保留无言停顿。"""
    out = []
    for ds, de in deletes:
        cur = [(ds, de)]
        for a, b in speech:
            a, b = max(a - pad, ds), min(b + pad, de)  # 语音段外扩保护带
            nxt = []
            for s, e in cur:
                if b <= s or a >= e:
                    nxt.append((s, e))
                else:
                    if s < a:
                        nxt.append((s, a))
                    if b < e:
                        nxt.append((b, e))
            cur = nxt
        out.extend(cur)
    out.sort()
    merged = []
    for s, e in out:
        if e - s < 0.4:
            continue
        if merged and s - merged[-1][1] < 0.15:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def main():
    load_env()
    odir = out_dir()
    plan_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (odir / "compact_result.json")
    srt_path = Path(sys.argv[2]) if len(sys.argv) > 2 else (odir / "transcript.srt")

    if not plan_path.exists() or not srt_path.exists():
        print(f"缺少 {plan_path} 或 {srt_path}")
        sys.exit(2)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    speech = srt_segments(srt_path.read_text(encoding="utf-8"))

    old = plan["deletes"]
    del_ranges = [(ts2sec(p["start"]), ts2sec(p["end"])) for p in old]
    protected = protect(del_ranges, speech)
    plan["deletes"] = [{"start": sec2ts(s), "end": sec2ts(e),
                        "reason": "无言停顿(经字幕保护)"} for s, e in protected]

    bak = plan_path.with_suffix(plan_path.suffix + ".bak.json")
    shutil.copy(plan_path, bak)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"原删除区间: {len(old)} 段")
    print(f"受保护后  : {len(protected)} 段（说话段已保留）")
    for s, e in protected:
        print(f"  删 [{s:.1f}-{e:.1f}]  ({e-s:.1f}s)")
    print(f"备份: {bak}")


if __name__ == "__main__":
    main()
