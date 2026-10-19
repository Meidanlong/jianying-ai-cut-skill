#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
理解层升级：逐段内容角色标注。让豆包把整个视频切成小段，每段标注剪辑角色，
从理解层区分"核心结果/关键动作/铺垫说明/冗余空白/废镜头"，供分层剪辑使用。

用法: python understand_roles.py [file_id]
  - 不传 file_id 时，从 <out>/upload_info.json 读取（由 run_video_understand 写入）
  - 需先有 <out>/transcript.srt（音频转写结果）
产物: <out>/roles_result.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import out_dir, load_env  # noqa: E402
from ark_client import video_understand, DEFAULT_VIDEO_MODEL  # noqa: E402


def main():
    load_env()
    odir = out_dir()

    # 取 file_id：优先命令行，否则读 upload_info.json
    if len(sys.argv) > 1:
        file_id = sys.argv[1]
    else:
        info = odir / "upload_info.json"
        if not info.exists():
            print("未提供 file_id，且找不到 <out>/upload_info.json。请先跑 run_video_understand.py")
            sys.exit(2)
        file_id = json.loads(info.read_text(encoding="utf-8"))["file_id"]

    srt_path = odir / "transcript.srt"
    if not srt_path.exists():
        print(f"缺少 {srt_path}，请先跑 audio_to_srt.py 生成字幕。")
        sys.exit(2)
    srt = srt_path.read_text(encoding="utf-8")

    prompt = (
        "请结合视频画面和下方语音字幕，对视频逐段做内容角色判断（每段约2-8秒），"
        "给出精确起止时间戳。判断时务必结合语音说了什么，不要只凭画面动作。\n"
        "角色定义：\n"
        "- 核心结果：语音在宣布结果/输赢/金额——最关键，必保，绝不能删\n"
        "- 关键动作：核心动作过程\n"
        "- 铺垫说明：介绍背景/规则/玩法，有价值信息\n"
        "- 冗余语音：查手机查规则、重复解说、无效尝试的对话、犹豫迟疑——即使有语音也算冗余，可删\n"
        "- 冗余空白：无语音的停顿、发呆、重复动作\n"
        "- 废镜头：无意义画面（如拍天花板）、镜头晃动无内容\n"
        "语音字幕（带时间戳）如下：\n"
        "----------\n"
        f"{srt}\n"
        "----------\n"
        "输出纯 JSON（不要多余文字），覆盖整个视频从 0 秒到结尾，分段连续不重叠、不遗漏：\n"
        '{"segments":[{"start":"HH:MM:SS","end":"HH:MM:SS","role":"核心结果","desc":"一句话说明"}]}\n'
        "要求：时间戳精确到秒；报结果/宣布金额必须标为核心结果，绝不能标成冗余。"
    )
    text = video_understand(file_id, prompt)

    # 容错：模型可能返回带代码块或多余文字，尝试解析以校验
    try:
        json.loads(text)
    except Exception:
        print("[warn] 返回内容非纯 JSON，原样保存，下游脚本会尝试剥离代码块。")

    (odir / "roles_result.json").write_text(text, encoding="utf-8")
    print(text)
    print("\n已保存到 {}/roles_result.json".format(odir))


if __name__ == "__main__":
    main()
