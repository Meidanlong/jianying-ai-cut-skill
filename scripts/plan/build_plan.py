#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把豆包理解结果（understand_*.json）转成剪辑决策单 compact_result.json。

关键规则（坑 #6）：保留段直接取 highlights 本身，deletes 取 highlights 的【补集】，
而不是拿模型给的 redundant 当删除区间——模型常漏标高光与冗余之间的边界缝隙，
直接用 redundant 当 deletes 会让保留量 = 总时长 - redundant 总和，超出目标上限。

用法:
  python build_plan.py out/ganzehn_pass1_understand_v2.json --duration 248.43
  python build_plan.py out/ganzehn_pass1_understand_v2.json --out out/compact_result.json

输出 compact_result.json: {"summary":..., "highlights":[...], "deletes":[{"start","end"}...]}
（deletes 用 HH:MM:SS.mmm，供 build_jianying_draft.py / ffmpeg_export.py 直接消费）
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import out_dir, sec2ts, load_brief, brief_target_range  # noqa: E402


def complement(highlights, total):
    """highlights 补集 -> 删除区间列表 [(start,end)...] 覆盖 [0, total]。"""
    hl = sorted((float(h["start"]), float(h["end"])) for h in highlights)
    deletes = []
    cur = 0.0
    for s, e in hl:
        if s > cur + 1e-6:
            deletes.append((cur, s))
        cur = max(cur, e)
    if cur < total - 1e-6:
        deletes.append((cur, total))
    return deletes


def main():
    ap = argparse.ArgumentParser(description="highlights -> compact_result.json (补集删除)")
    ap.add_argument("understand", help="豆包理解结果 json（含 highlights）")
    ap.add_argument("--duration", type=float, default=None,
                    help="源视频总时长(秒)；省略则取 highlights 最大结束时间")
    ap.add_argument("--brief", help="剪辑需求 brief(yaml)；读取 target_duration 区间做时长校验")
    ap.add_argument("--out", help="输出路径（默认 <out>/compact_result.json）")
    args = ap.parse_args()

    data = json.loads(Path(args.understand).read_text(encoding="utf-8"))
    highlights = data.get("highlights")
    if not highlights:
        print("❌ understand json 缺少 highlights 字段")
        sys.exit(2)

    total = args.duration
    if not total or total <= 0:
        total = max(float(h["end"]) for h in highlights)
        print(f"[info] 未给 --duration，按 highlights 最大结束时间推断 total={total:.2f}s")

    deletes = complement(highlights, total)
    keep_total = sum(float(h["end"]) - float(h["start"]) for h in highlights)

    # brief 目标时长区间校验（坑 #15：brief 缺失会导致高光判断跑偏，这里兜底卡时长）
    target_sec = None
    if args.brief:
        brief = load_brief(args.brief)
        rng = brief_target_range(brief)
        if rng:
            lo, hi = rng
            target_sec = round((lo + hi) / 2)
            if not (lo - 1e-6 <= keep_total <= hi + 1e-6):
                print(f"⚠️ 保留总时长 {keep_total:.2f}s 不在 brief 目标区间 "
                      f"[{lo:.0f},{hi:.0f}]s 内，请回看 understand_highlights 提示词或 brief")
                sys.exit(1)
            print(f"[ok] 保留总时长 {keep_total:.2f}s ∈ brief 目标区间 [{lo:.0f},{hi:.0f}]s")

    out = args.out or str(out_dir() / "compact_result.json")
    result = {
        "summary": data.get("summary", ""),
        "highlights": highlights,
        "deletes": [{"start": sec2ts(s), "end": sec2ts(e)} for s, e in deletes],
    }
    if target_sec is not None:
        result["target_duration_sec"] = target_sec
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"highlights={len(highlights)}  keeps总时长={keep_total:.2f}s"
          f"  deletes={len(deletes)}  total={total:.2f}s")
    print(f"✅ 已写入: {out}")


if __name__ == "__main__":
    main()
