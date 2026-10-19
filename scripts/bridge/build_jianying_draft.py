#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CodeBuddy 精切核心：把理解层产出的剪辑决策单(删除区间)转换成剪映草稿。

剪映草稿只能"拼保留段"，不能直接删段。本脚本：
  1. 读 <out>/compact_result.json（deletes 删除区间）+ 视频时长，求"保留区间"补集；
  2. 把每个保留区间作为一段视频 clip，按原始 source_timerange 偏移拼到 VideoTrack；
  3. （可选）把 <out>/transcript.srt 的字幕按保留区间重新映射到目标时间轴，作为字幕轨；
  4. （可选）把 <out>/cover_916.png 作为片头 3s 卡片放到最前；
  5. save() 落盘到剪映草稿目录（macOS 默认 ~/Movies/JianyingPro/.../com.lveditor.draft/<项目名>/）。

用法:
  python build_jianying_draft.py --video <视频> --project <项目名>
       [--out-dir <out>] [--no-subtitles] [--no-cover] [--orientation auto|portrait|landscape]

依赖：vendor/jianying_editor_skill_scripts（jianying-editor-skill v1.7，MIT + Apache pyJianYingDraft）。
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent          # <repo>
SCRIPTS = REPO / "scripts"
VENDOR_SKILL = REPO / "vendor" / "jianying_editor_skill_scripts"
VENDOR_PY = VENDOR_SKILL / "vendor"   # pyJianYingDraft 在此目录内
for p in (str(SCRIPTS), str(VENDOR_SKILL), str(VENDOR_PY)):
    if p not in sys.path:
        sys.path.insert(0, p)

from common import out_dir, load_env, probe_duration, video_size, ts2sec  # noqa: E402
from jy_wrapper import JyProject  # noqa: E402


def keep_ranges(deletes, duration):
    """deletes: [(start,end)...] 秒；返回保留区间列表（补集，覆盖 [0,duration]）。"""
    dels = sorted((float(a), float(b)) for a, b in deletes if float(b) > float(a))
    dur = float(duration)
    keeps = [(0.0, dur)]
    for ds, de in dels:
        nk = []
        for s, e in keeps:
            if de <= s or ds >= e:
                nk.append((s, e))
            else:
                if s < ds:
                    nk.append((s, ds))
                if de < e:
                    nk.append((de, e))
        keeps = nk
    return [(s, e) for s, e in keeps if e - s > 0.2]


def parse_srt_times(srt_text):
    """返回 [(start_sec, end_sec, text)]。"""
    lines = [l.strip() for l in srt_text.splitlines() if l.strip()]
    out = []
    for i in range(0, len(lines), 3):
        m = re.match(r"(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)", lines[i + 1])
        if not m:
            continue

        def s(t):
            h, mn, r = t.split(":")
            ss, ms = r.split(",")
            return int(h) * 3600 + int(mn) * 60 + int(ss) + int(ms) / 1000

        out.append((s(m.group(1)), s(m.group(2)), lines[i + 2]))
    return out


def sec_to_us(x: float) -> int:
    return int(round(x * 1_000_000))


def main():
    ap = argparse.ArgumentParser(description="决策单 -> 剪映草稿（CodeBuddy 精切）")
    ap.add_argument("--video", required=True, help="原视频路径")
    ap.add_argument("--project", default="AI_JianYing_Cut", help="剪映草稿项目名")
    ap.add_argument("--out-dir", default=None, help="中间产物目录(默认 out)")
    ap.add_argument("--no-subtitles", action="store_true", help="不加字幕轨")
    ap.add_argument("--no-cover", action="store_true", help="不生成/不加片头封面")
    ap.add_argument("--orientation", default="auto",
                    choices=["auto", "portrait", "landscape"], help="画布方向(默认按源自动)")
    ap.add_argument("--cover-size", default="916", choices=["34", "916"],
                    help="片头封面用哪张(默认 9:16)")
    args = ap.parse_args()

    load_env()
    odir = out_dir() if not args.out_dir else Path(args.out_dir)
    odir.mkdir(parents=True, exist_ok=True)

    # 1) 视频元数据
    duration = probe_duration(args.video)
    if duration <= 0:
        print("⚠️ 无法用 ffprobe 取得视频时长，尝试从理解结果补充...")
        # 退路：用 understand_result 里的 timeline 末段；这里简单提示
        print("⚠️ 时长缺失，保留区间将基于 0。建议安装 ffmpeg/ffprobe。")
        duration = 0.0
    w, h = video_size(args.video)
    if args.orientation == "portrait" or (args.orientation == "auto" and h and w and h > w):
        cw, ch = 1080, 1920
    else:
        cw, ch = 1920, 1080
    print(f"[meta] 时长={duration:.2f}s 源尺寸={w}x{h} -> 画布 {cw}x{ch}")

    # 2) 读决策单
    plan_path = odir / "compact_result.json"
    if not plan_path.exists():
        print(f"缺少 {plan_path}，请先跑 roles_to_plan.py")
        sys.exit(2)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    deletes = [(ts2sec(d["start"]), ts2sec(d["end"])) for d in plan.get("deletes", [])]
    keeps = keep_ranges(deletes, duration)
    print(f"[plan] 删除 {len(deletes)} 段 -> 保留 {len(keeps)} 段")

    # 3) 建草稿
    project = JyProject(args.project, width=cw, height=ch, overwrite=True)
    cover_offset = 0.0
    if not args.no_cover:
        cover = odir / f"cover_{args.cover_size}.png"
        if cover.exists():
            project.add_media_safe(str(cover), start_time=0, duration=3,
                                  track_name="VideoTrack")
            cover_offset = 3.0
            print(f"[cover] 片头卡片: {cover} (3s)")
        else:
            print(f"[cover] 未找到 {cover}，跳过片头（先跑 make_cover.py）")

    # 4) 拼保留段视频 clip
    target_cursor = sec_to_us(cover_offset)
    cum = cover_offset
    keep_map = []  # (ks, ke, cum_before)
    for ks, ke in keeps:
        src_start = ks
        length = ke - ks
        project.add_clip(args.video, source_start=src_start, duration=length,
                         target_start=target_cursor, track_name="VideoTrack")
        target_cursor += sec_to_us(length)
        keep_map.append((ks, ke, cum))
        cum += length
    print(f"[video] 共拼 {len(keeps)} 段视频，目标时长 {cum:.2f}s")

    # 5) 字幕轨（按保留区间重映射）
    if not args.no_subtitles:
        srt = odir / "transcript.srt"
        if srt.exists():
            for a, b, text in parse_srt_times(srt.read_text(encoding="utf-8")):
                # 仅当整条字幕落在某个保留段内才放，避免跨切点错位
                for ks, ke, cum_before in keep_map:
                    if a >= ks - 0.05 and b <= ke + 0.05:
                        tgt = cum_before + (a - ks)
                        project.add_text_simple(
                            text.strip(),
                            start_time=sec_to_us(tgt),
                            duration=sec_to_us(b - a),
                            track_name="Subtitles")
                        break
            print(f"[subtitle] 字幕已按保留区间重映射写入字幕轨")
        else:
            print(f"[subtitle] 未找到 {srt}，跳过字幕")

    result = project.save()
    print(f"\n✅ 草稿已生成: {result.get('draft_path')}")


if __name__ == "__main__":
    main()
