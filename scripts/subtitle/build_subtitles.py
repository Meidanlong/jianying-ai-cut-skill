#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕一键编排：成片抽音频 → ASR 转写 → 校正词表 → SRT→ASS → ffmpeg 烧录。

用法:
  python build_subtitles.py --video final.mp4 --out final_sub.mp4 \
      [--corrections corrections.json] [--fontname STHeiti] [--fontsize 80] [--marginv 170]

步骤:
  1) ffmpeg 抽音轨到临时 m4a
  2) audio_to_srt.py 调豆包 ASR -> <out>.srt（时间轴对齐成片本身，坑 #10）
  3) apply_corrections.py 应用 corrections.json -> <out>.corrected.srt + review_checklist.md（坑 #11）
  4) srt_to_ass.py 生成竖屏 ASS（白字黑描边，见 docs/subtitle_spec.md）
  5) ffmpeg 用 ass 滤镜烧录 -> <out>

说明: 第 2 步需要 ARK_API_KEY 且联网；若已有 srt，可用 --srt 跳过 ASR 直接走 3~5。
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import out_dir, load_env  # noqa: E402

HERE = Path(__file__).resolve().parent


def run(py_script, *cli):
    cmd = [sys.executable, str(py_script), *cli]
    print(">>>", " ".join(cmd[:4]), "...")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f"❌ {py_script.name} 失败 (rc={r.returncode})")
        sys.exit(r.returncode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="最终成片（字幕时间轴须对齐它）")
    ap.add_argument("--out", required=True, help="烧录后成片路径")
    ap.add_argument("--srt", help="已有 srt 则跳过 ASR（否则从 video 抽音转写）")
    ap.add_argument("--corrections", default=str(HERE / "corrections.json"))
    ap.add_argument("--fontname", default="STHeiti")
    ap.add_argument("--fontsize", type=int, default=80)
    ap.add_argument("--marginv", type=int, default=170)
    ap.add_argument("--audio", help="预抽好的音频（默认临时抽）")
    args = ap.parse_args()
    load_env()

    video = Path(args.video)
    base = video.stem
    work = out_dir()
    srt_path = Path(args.srt) if args.srt else (work / f"{base}.srt")
    corrected = work / f"{base}.corrected.srt"
    ass = work / f"{base}.ass"

    # 1) 抽音轨（仅在需要 ASR 时）
    audio = args.audio
    if not args.srt:
        if not audio:
            audio = str(work / f"{base}.m4a")
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                            "-i", str(video), "-vn", "-c:a", "copy", audio], check=True)
        # 2) ASR
        run(HERE / "audio_to_srt.py", audio, str(srt_path))

    # 3) 校正
    run(HERE / "apply_corrections.py", str(srt_path),
        "--corrections", args.corrections,
        "--out", str(corrected))

    # 4) SRT -> ASS
    run(HERE / "srt_to_ass.py", str(corrected), str(ass),
        "--fontname", args.fontname, "--fontsize", str(args.fontsize),
        "--marginv", str(args.marginv))

    # 5) 烧录
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                       "-i", str(video), "-vf", f"ass={ass}",
                       "-c:v", "libx264", "-b:v", "10M", "-pix_fmt", "yuv420p",
                       "-c:a", "copy", str(args.out)])
    if r.returncode == 0:
        print(f"✅ 字幕成片已生成: {args.out}")
    else:
        print("❌ 烧录失败")
        sys.exit(r.returncode)


if __name__ == "__main__":
    main()
