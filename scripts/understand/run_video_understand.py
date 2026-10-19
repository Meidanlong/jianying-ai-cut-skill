#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用豆包视频理解 API 分析一段本地视频：上传(服务端抽帧+转写) -> 输出
内容概述 + 分段时间线 + 剪辑决策点(带时间戳)。

用法: python run_video_understand.py <视频路径> [剪辑规则]
产物: <out>/understand_result.json + <out>/upload_info.json (video, file_id)
"""
import json
import sys
from pathlib import Path

# 把 <repo>/scripts 加入路径，便于 import common / ark_client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import out_dir, load_env, ensure_on_path  # noqa: E402
ensure_on_path()
from ark_client import upload_file, video_understand, DEFAULT_VIDEO_MODEL  # noqa: E402

USAGE = "用法: python run_video_understand.py <视频路径> [剪辑规则]"


def main():
    load_env()
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(2)
    video = sys.argv[1]
    rule = sys.argv[2] if len(sys.argv) > 2 else "识别内容并给出剪辑建议"
    odir = out_dir()

    # 1) 上传视频（fps 0.3 即每约3秒抽一帧，控制 token 成本）
    file_id = upload_file(video, preprocess={"video": {"fps": 0.3}})

    # 记录上传信息，供 understand_roles / compact_understand 复用 file_id
    (odir / "upload_info.json").write_text(
        json.dumps({"video": video, "file_id": file_id,
                    "model": DEFAULT_VIDEO_MODEL}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    # 2) 调用视频理解
    print("[2/3] 豆包理解视频内容...")
    prompt = (
        "请完整理解这段视频。输出纯 JSON（不要多余文字），格式：\n"
        "{\n"
        '  "video_type": "视频类型(口播/录屏教程/生活记录/带货/采访/其他)",\n'
        '  "summary": "内容概述(100字内)",\n'
        '  "timeline": [{"start":"HH:MM:SS","end":"HH:MM:SS","desc":"该时间段发生了什么"}],\n'
        '  "edit_points": [{"start":"HH:MM:SS","end":"HH:MM:SS","type":"删除|保留|高光|静默","reason":"一句话"}],\n'
        '  "notes": "剪辑建议"\n'
        "}\n"
        f"剪辑规则参考：{rule}"
    )
    text = video_understand(file_id, prompt)

    print("[3/3] 分析结果：")
    print(text)

    (odir / "understand_result.json").write_text(text, encoding="utf-8")
    print(f"\n结果已保存到 {(odir / 'understand_result.json')}")
    print(f"上传信息已保存到 {(odir / 'upload_info.json')}（file_id 供后续复用）")


if __name__ == "__main__":
    main()
