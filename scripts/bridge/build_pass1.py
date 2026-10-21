#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第一遍粗剪（pass1）：把若干素材按文件名顺序**原样**拼到同一条视频轨上。
不做精切 / 不做高光筛选 / 不写字幕轨 / 不封面，画布固定竖屏 1080x1920。
每个素材的原声通过独立音频轨与视频段对齐（视频轨静音，避免双重音轨）。

用法:
  python build_pass1.py --clips IMG_3404.mov IMG_3405.mov ... --project ganzehn_pass1
"""
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent          # <repo>
SCRIPTS = REPO / "scripts"
VENDOR_SKILL = REPO / "vendor" / "jianying_editor_skill_scripts"
VENDOR_PY = VENDOR_SKILL / "vendor"   # pyJianYingDraft 在此目录内
for p in (str(SCRIPTS), str(VENDOR_SKILL), str(VENDOR_PY)):
    if p not in sys.path:
        sys.path.insert(0, p)

from jy_wrapper import JyProject  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", nargs="+", required=True, help="素材路径（按顺序拼接）")
    ap.add_argument("--project", default="ganzhen_pass1")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    args = ap.parse_args()

    # 按文件名自然顺序排序（素材名为定宽数字，字典序即数字序）
    clips = sorted(args.clips, key=lambda p: Path(p).name)

    # overwrite=True 覆盖同名的旧草稿，保证每次都是干净的一遍粗剪
    project = JyProject(args.project, width=args.width, height=args.height, overwrite=True)

    for path in clips:
        # 视频：整段原样拼到 VideoTrack（target_start=None 自动续接上一段）
        project.add_clip(path, source_start=0, duration=None,
                         target_start=None, track_name="VideoTrack")
        # 音频：抽离与原声对齐的纯音频，落到 AudioTrack，与视频段同起点同长度
        project.add_audio_safe(path, start_time=None, duration=None,
                               source_start=0, track_name="AudioTrack")
        print(f"[pass1] + {Path(path).name}")

    result = project.save()
    print(f"\n✅ pass1 草稿已生成: {result.get('draft_path')}")


if __name__ == "__main__":
    main()
