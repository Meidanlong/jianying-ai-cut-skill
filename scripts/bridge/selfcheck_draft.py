#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
草稿自检：在剪映打开草稿【之前】对明文 draft_info.json 做结构质量门。

用法:
  python selfcheck_draft.py <草稿目录或draft_info.json路径>
  python selfcheck_draft.py <草稿目录> --target 89 --tol 5
  python selfcheck_draft.py <草稿目录> --plan out/compact_result.json

断言项（坑 #1/#4/#6/#14）:
  1) 视频轨数量 == 1（单轨首尾相接，无叠层多轨）
  2) 视频段总时长 ∈ [target-tol, target+tol]（target 来自 --target 或 plan 的 target_duration_sec）
  3) 每段音视频对齐偏差 < 50ms（音频段与对应视频段起止对齐）
  4) 字幕段全部落在保留段内（不飘在删除/缝隙里）

退出码: 0=全部 PASS，1=存在 FAIL。
详见 docs/draft_selfcheck.md。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import ts2sec  # noqa: E402


def load_draft(path):
    p = Path(path)
    if p.is_dir():
        p = p / "draft_info.json"
    text = p.read_text(encoding="utf-8-sig")
    if not text.lstrip().startswith("{"):
        raise SystemExit(f"❌ draft_info.json 不是明文（已被剪映加密？开头: {text[:20]!r}）。"
                         " 必须在剪映打开前运行自检。")
    return json.loads(text)


def segs_of(track):
    out = []
    for s in track.get("segments", []):
        tr = s.get("target_timerange") or {}
        sr = s.get("source_timerange") or {}
        out.append({
            "t_start": tr.get("start", 0) / 1e6,
            "t_dur": tr.get("duration", 0) / 1e6,
            "s_start": sr.get("start", 0) / 1e6,
            "s_dur": sr.get("duration", 0) / 1e6,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", help="草稿目录或 draft_info.json 路径")
    ap.add_argument("--target", type=float, default=None, help="目标总时长(秒)")
    ap.add_argument("--tol", type=float, default=5.0, help="时长容差(秒)，默认 5")
    ap.add_argument("--plan", help="compact_result.json（取 target_duration_sec / keeps）")
    ap.add_argument("--av-threshold", type=float, default=0.05, help="音视频对齐阈值(秒)，默认 0.05")
    args = ap.parse_args()

    d = load_draft(args.draft)
    tracks = d.get("tracks", [])
    video = [t for t in tracks if t.get("type") == "video"]
    audio = [t for t in tracks if t.get("type") == "audio"]
    text = [t for t in tracks if t.get("type") == "text"]

    vsegs = segs_of(video[0]) if video else []
    asegs = segs_of(audio[0]) if audio else []
    tsegs = segs_of(text[0]) if text else []

    results = []
    # 1) 视频轨数量
    results.append(("视频轨数量 == 1", len(video) == 1, f"实际 {len(video)} 条"))

    # 2) 总时长
    total_v = sum(s["t_dur"] for s in vsegs)
    target = args.target
    if target is None and args.plan:
        pd = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        target = pd.get("target_duration_sec")
    if target:
        ok = abs(total_v - target) <= args.tol
        results.append((f"总时长 ∈ [{target-args.tol:.0f}, {target+args.tol:.0f}]s",
                        ok, f"实际 {total_v:.2f}s vs 目标 {target:.0f}s"))
    else:
        results.append(("总时长区间检查", True, f"实际 {total_v:.2f}s（未给 --target，跳过区间判定）"))

    # 3) 音视频对齐
    if asegs and len(asegs) == len(vsegs):
        maxoff = 0.0
        for v, a in zip(vsegs, asegs):
            maxoff = max(maxoff, abs(v["t_start"] - a["t_start"]),
                         abs((v["t_start"] + v["t_dur"]) - (a["t_start"] + a["t_dur"])))
        results.append((f"音视频对齐偏差 < {args.av_threshold:.2f}s",
                        maxoff < args.av_threshold, f"最大偏差 {maxoff:.4f}s"))
    elif asegs:
        results.append(("音视频段数一致", False,
                        f"视频 {len(vsegs)} 段 vs 音频 {len(asegs)} 段，无法逐段对齐"))
    else:
        results.append(("音频轨存在", False, "无音频轨"))

    # 4) 字幕落点
    if tsegs:
        outside = 0
        for t in tsegs:
            s, e = t["t_start"], t["t_start"] + t["t_dur"]
            inside = any((vs - 1e-3) <= s and e <= (vs + vd + 1e-3)
                         for vs, vd in ((x["t_start"], x["t_dur"]) for x in vsegs))
            if not inside:
                outside += 1
        results.append((f"字幕段全部落在保留段内", outside == 0,
                        f"{len(tsegs)-outside}/{len(tsegs)} 命中，{outside} 段飘在外面"))
    else:
        results.append(("字幕段落点", True, "无字幕轨（跳过）"))

    # 打印
    print(f"草稿: {args.draft}")
    all_pass = True
    for name, ok, detail in results:
        flag = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"[{flag}] {name}  --  {detail}")

    if all_pass:
        print("=> 自检通过 (exit 0)")
        sys.exit(0)
    else:
        print("=> 自检未通过，阻断导出 (exit 1)")
        sys.exit(1)


if __name__ == "__main__":
    main()
