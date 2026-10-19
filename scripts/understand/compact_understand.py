#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快节奏版：复用已上传的视频 file_id，让豆包按"短视频快节奏"标准细粒度识别
可删除的低信息段(停顿/重复/无意义动作)，输出细粒度剪辑点。

用法: python compact_understand.py [file_id]
  - 不传 file_id 时从 <out>/upload_info.json 读取
产物: <out>/compact_raw.json （注意：与 roles_to_plan 产出的 compact_result.json 不同，
        本文件是"原始可删段建议"，最终决策单由 roles_to_plan 生成）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import out_dir, load_env  # noqa: E402
from ark_client import video_understand  # noqa: E402


def main():
    load_env()
    odir = out_dir()

    if len(sys.argv) > 1:
        file_id = sys.argv[1]
    else:
        info = odir / "upload_info.json"
        if not info.exists():
            print("未提供 file_id，且找不到 <out>/upload_info.json。请先跑 run_video_understand.py")
            sys.exit(2)
        file_id = json.loads(info.read_text(encoding="utf-8"))["file_id"]

    prompt = (
        "这是要剪成短视频的素材。请逐段精确识别所有可删除的低信息、冗余、拖节奏内容，"
        "包括但不限于：1) 查看手机/查规则、犹豫、停顿 2) 重复的准备工作或平淡过程 "
        "3) 静止空档、无意义晃动。\n"
        "规则：节奏要快，只保留有信息量或情绪看点的片段。\n"
        "输出纯 JSON（不要多余文字）：\n"
        "{\n"
        '  "deletes": [{"start":"HH:MM:SS","end":"HH:MM:SS","reason":"为何删"}],\n'
        '  "highlights": [{"start":"HH:MM:SS","end":"HH:MM:SS","reason":"必留看点"}],\n'
        '  "summary": "成片节奏建议一句话"\n'
        "}\n"
        "要求：deletes 区间尽量精确到秒；不要删除开场和结局，不要删除有情绪反应的关键时刻。"
    )
    text = video_understand(file_id, prompt)

    (odir / "compact_raw.json").write_text(text, encoding="utf-8")
    print(text)
    print("\n已保存到 {}/compact_raw.json".format(odir))


if __name__ == "__main__":
    main()
