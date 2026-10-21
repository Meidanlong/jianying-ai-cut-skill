#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ffmpeg 直出兜底成片（不依赖剪映 GUI 导出）。

读 compact_result.json（含 deletes 或 highlights），把保留段从源视频中
用 filter_complex 逐段 trim/atrim -> concat 拼成一条，H.264 + AAC 输出。

用法:
  python ffmpeg_export.py --plan out/compact_result.json --src video.mp4 --out final.mp4
  python ffmpeg_export.py --plan out/xxx.json --src video.mp4 --out final.mp4 --dry-run

plan 解析优先级:
  - 有 "deletes"  -> 保留段 = 删除区间的补集（覆盖 [0, 源时长]）
  - 有 "highlights" -> 保留段 = highlights 本身
  - 有 "redundant" -> 同 deletes 处理
详见 docs/export_fallback.md（坑 #7）。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import out_dir, ts2sec, probe_duration  # noqa: E402


def to_sec(x):
    """数字按秒；字符串按 'HH:MM:SS[.mmm]' 解析。"""
    if isinstance(x, (int, float)):
        return float(x)
    return ts2sec(str(x).strip())


def complement(deletes, total):
    """删除区间补集 -> 保留段列表 [(start,end)...]，覆盖 [0, total]。"""
    dels = sorted((to_sec(s), to_sec(e)) for s, e in deletes)
    keeps = []
    cur = 0.0
    for s, e in dels:
        if s > cur + 1e-6:
            keeps.append((cur, s))
        cur = max(cur, e)
    if cur < total - 1e-6:
        keeps.append((cur, total))
    return keeps


def build_keeps(plan, total):
    if "deletes" in plan:
        return complement([(d["start"], d["end"]) for d in plan["deletes"]], total)
    if "redundant" in plan:
        return complement([(d["start"], d["end"]) for d in plan["redundant"]], total)
    if "highlights" in plan:
        return sorted((to_sec(h["start"]), to_sec(h["end"])) for h in plan["highlights"])
    raise ValueError("plan 必须含 deletes / redundant / highlights 之一")


def build_filter(keeps):
    parts = []
    for i, (s, e) in enumerate(keeps):
        parts.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]")
    fc = ",".join(parts)
    concat_ins = "".join(f"[v{i}][a{i}]" for i in range(len(keeps)))
    fc += f";{concat_ins}concat=n={len(keeps)}:v=1:a=1[vout][aout]"
    return fc


def main():
    ap = argparse.ArgumentParser(description="ffmpeg 直出兜底成片")
    ap.add_argument("--plan", required=True, help="compact_result.json / understand json")
    ap.add_argument("--src", required=True, help="源视频（时间轴须与 plan 一致）")
    ap.add_argument("--out", help="输出成片（默认 <out>/export.mp4）")
    ap.add_argument("--dry-run", action="store_true", help="只打印 filter_complex 不编码")
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    total = probe_duration(args.src)
    if total <= 0:
        print("[WARN] 无法探测源视频时长，请用完整路径或检查 ffmpeg")
    keeps = build_keeps(plan, total)
    # 健壮性：夹断到 total，并丢弃亚 20ms 的退化片段（避免浮点取整产生 0 时长段）
    if total > 0:
        keeps = [(s, min(e, total)) for (s, e) in keeps]
    keeps = [(s, e) for (s, e) in keeps if e - s > 0.02]
    total_keep = sum(e - s for s, e in keeps)
    print(f"保留段数={len(keeps)}  保留总时长≈{total_keep:.2f}s (源时长={total:.2f}s)")

    fc = build_filter(keeps)
    out = args.out or str(out_dir() / "export.mp4")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", args.src, "-filter_complex", fc,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-b:v", "10M", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", out,
    ]
    if args.dry_run:
        print("[dry-run] filter_complex:\n" + fc)
        print("[dry-run] cmd:\n" + " ".join(cmd[:6]) + " ...(截断)")
        return
    r = subprocess.run(cmd)
    if r.returncode == 0:
        print(f"✅ 成片已生成: {out}")
    else:
        print("❌ ffmpeg 失败，返回码", r.returncode)
        sys.exit(r.returncode)


if __name__ == "__main__":
    main()
