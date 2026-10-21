#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-jianying-cut 总编排：一键跑通「豆包理解 → 决策质检 → 脚本精切 → 剪映草稿」。

阶段：
  1) 理解层：run_video_understand + audio_to_srt + understand_roles（+ 可选 compact_understand）
  2) 决策层：roles_to_plan → fix_plan → check_cut（质量门）
  3) 字幕/封面/情绪：srt_to_ass + identify_lead + make_cover + understand_emotions
  4) 精切层：build_jianying_draft（生成剪映草稿）

两遍剪映 AI（在剪映 App 内由 Doubao 通过 mac_computer_use_tool 操作 GUI 完成）见 SKILL.md。

用法:
  python run_pipeline.py --video <视频> [--rule "..."] [--project 项目名]
       [--out-dir out] [--dry-run] [--skip-draft] [--no-cover]

  --dry-run   不调用任何 API，用占位数据跑通结构（用于无 Key / CI 演示）。
              （仍需一个本地视频才做片头/抽帧；无视频时跳过 cover/lead/draft）
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent          # <repo>
SCRIPTS = REPO / "scripts"
UNDERSTAND = SCRIPTS / "understand"
PLAN = SCRIPTS / "plan"
SUBTITLE = SCRIPTS / "subtitle"
COVER = SCRIPTS / "cover"
BRIDGE = SCRIPTS / "bridge"

# 把 scripts 加入路径，便于 import common
sys.path.insert(0, str(SCRIPTS))
from common import out_dir, load_env  # noqa: E402


def run(script: Path, *args, env=None, check=True):
    cmd = [sys.executable, str(script), *args]
    print(f"\n$ {' '.join(cmd)}")
    r = subprocess.run(cmd, env=env or os.environ, cwd=str(REPO))
    if check and r.returncode != 0:
        print(f"❌ 阶段失败: {script.name} (exit {r.returncode})")
        sys.exit(r.returncode)
    return r.returncode


def extract_audio(video: str, out_mp3: str):
    ff = os.getenv("FFMPEG") or "ffmpeg"
    print(f"\n$ ffmpeg 抽取音轨 -> {out_mp3}")
    r = subprocess.run([ff, "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
                        "-c:a", "libmp3lame", "-q:a", "4", out_mp3],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("⚠️ 音轨抽取失败，跳过字幕生成：", r.stderr[-300:])
        return False
    return True


def dry_run_stubs(odir: Path):
    """无 API Key 时写入占位数据，使下游（plan/check/ass/draft）仍能跑通结构。"""
    (odir / "upload_info.json").write_text(
        json.dumps({"video": "<dry-run>", "file_id": "dry-run", "model": "dry-run"},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (odir / "understand_result.json").write_text(
        json.dumps({"video_type": "demo", "summary": "dry-run 占位", "timeline": [],
                    "edit_points": [], "notes": "无 ARK_API_KEY 的占位数据"},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (odir / "transcript.srt").write_text("", encoding="utf-8")
    (odir / "roles_result.json").write_text(
        json.dumps({"segments": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    (odir / "compact_raw.json").write_text(
        json.dumps({"deletes": [], "highlights": [], "summary": "dry-run"},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    # 关键：决策单为空删除 -> 保留整段
    (odir / "compact_result.json").write_text(
        json.dumps({"deletes": [], "highlights": [], "keep_roles": [],
                    "summary": "dry-run: 保留整段"}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    (odir / "emotions_result.json").write_text(
        json.dumps({"points": [], "source": "dry-run", "summary": "dry-run"},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("[dry-run] 已写入占位 JSON；下游将按「保留整段」跑通结构。")


def main():
    ap = argparse.ArgumentParser(description="ai-jianying-cut 一键流水线")
    ap.add_argument("--video", default=None, help="原视频路径")
    ap.add_argument("--rule", default="去口误,去静默,保留高光段", help="剪辑规则")
    ap.add_argument("--project", default="AI_JianYing_Cut", help="剪映草稿项目名")
    ap.add_argument("--out-dir", default=None, help="中间产物目录(默认 out)")
    ap.add_argument("--dry-run", action="store_true", help="不调用 API，用占位数据跑通")
    ap.add_argument("--skip-draft", action="store_true", help="不生成剪映草稿")
    ap.add_argument("--no-cover", action="store_true", help="不生成封面/片头")
    ap.add_argument("--title", default="视频标题", help="封面标题")
    ap.add_argument("--subtitle", default="", help="封面副标题")
    args = ap.parse_args()

    load_env()
    odir = out_dir() if not args.out_dir else Path(args.out_dir)
    odir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)

    has_key = bool(os.environ.get("ARK_API_KEY"))
    if args.dry_run:
        print("=== DRY-RUN 模式（不调用任何 API）===")
        dry_run_stubs(odir)
    else:
        if not has_key:
            print("未检测到 ARK_API_KEY。请用 .env 配置后重试，或加 --dry-run 跑通结构。")
            sys.exit(2)
        if not args.video or not Path(args.video).exists():
            print("需要 --video 指向存在的本地视频（真实模式）。")
            sys.exit(2)

        # ---- 阶段 1：理解层 ----
        run(UNDERSTAND / "run_video_understand.py", args.video, args.rule, env=env)
        audio_ok = False
        if args.video:
            audio_mp3 = str(odir / "audio.mp3")
            audio_ok = extract_audio(args.video, audio_mp3)
            if audio_ok:
                run(UNDERSTAND / "audio_to_srt.py", audio_mp3, env=env)
        run(UNDERSTAND / "understand_roles.py", env=env)

    # ---- 阶段 2：决策层（无论 dry-run 还是真实都跑，纯本地） ----
    run(PLAN / "roles_to_plan.py", env=env)
    run(PLAN / "fix_plan.py", env=env)
    rc = run(PLAN / "check_cut.py", env=env, check=False)
    if rc != 0:
        print("❌ 质量门未通过：关键结果信息可能被误删，请检查决策单后重试。")
        sys.exit(1)

    # ---- 阶段 3：字幕/封面/情绪（纯本地） ----
    run(SUBTITLE / "srt_to_ass.py", str(odir / "transcript.srt"),
        str(odir / "subtitle.ass"), env=env)
    if not args.no_cover and args.video and Path(args.video).exists():
        run(COVER / "identify_lead.py", args.video, env=env)
        run(COVER / "make_cover.py", args.video, "--title", args.title,
            "--subtitle", args.subtitle, env=env)
    else:
        print("\n[cover] 跳过（--no-cover 或无本地视频）")
    run(UNDERSTAND / "understand_emotions.py", env=env)

    # ---- 阶段 4：精切层（生成剪映草稿） ----
    if args.skip_draft:
        print("\n[draft] 跳过（--skip-draft）")
    else:
        draft_args = ["--video", args.video or "<dry-run>", "--project", args.project,
                      "--out-dir", str(odir)]
        if args.no_cover:
            draft_args.append("--no-cover")
        if not args.video or not Path(args.video).exists():
            print("\n[draft] 无本地视频，跳过草稿生成（dry-run 演示到此为止）。")
        else:
            run(BRIDGE / "build_jianying_draft.py", *draft_args, env=env)

    print("\n=== 流水线结束 ===")
    print(f"中间产物: {odir}")
    print("下一步：在剪映里打开草稿，由 Doubao 通过 mac_computer_use_tool 操作 GUI "
          "完成『两遍剪映 AI』（粗剪初处理 + 精修导出）。详见 SKILL.md。")


if __name__ == "__main__":
    main()
