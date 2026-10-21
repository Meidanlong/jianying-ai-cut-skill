#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第一遍粗剪的「豆包理解 / 高光决策」——激进版（v2）。
目标总时长 55-65 秒， aggressively 删空镜，节奏紧凑（每段 <=8s）。

产物: out/ganzehn_pass1_understand_v2.json
格式与 v1 相同:
{
  "summary": "...",
  "highlights": [{"start": 秒, "end": 秒, "reason": "..."}],
  "redundant":  [{"start": 秒, "end": 秒, "reason": "..."}],
  "target_duration_sec": 60
}

用法: python understand_highlights_v2.py [视频路径] [输出json路径]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import out_dir, load_env, ensure_on_path  # noqa: E402
ensure_on_path()
from ark_client import upload_file, video_understand, DEFAULT_VIDEO_MODEL  # noqa: E402

# 默认输入取相对名（从命令行或 config 传入绝对/相对路径）；脚本内禁止硬编码个人绝对路径
DEFAULT_VIDEO = "ganzehn_pass1.mp4"
DEFAULT_OUT = "ganzehn_pass1_understand_v2.json"


def extract_json(text: str):
    """从模型输出中稳健取出 JSON 对象（兼容 ```json 围栏或直接裸 JSON）。"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1 and e > s:
        return json.loads(text[s:e + 1])
    raise ValueError("模型输出中未找到 JSON")


PROMPT = (
    "你是一名资深短视频剪辑师，风格快节奏、信息密度高。请观看这段探店 vlog"
    "（竖屏 1080x1920，约 248 秒），给出用于「精剪」的高光与冗余决策。\n\n"
    "用户明确反馈上一版（保留 89 秒）节奏偏慢、空镜拖沓。这次要更激进：\n"
    "【优先保留】有信息量的段落：菜品特写、口味评价、惊艳反应、种草点。\n"
    "【重点删除】空镜/废片：门店外景、后厨全景、无对话的夹菜/咀嚼/扒饭镜头、"
    "面对镜头的空白停顿、重复进食、冗长转场。宁可少留，不要拖沓。\n"
    "【节奏约束】每个保留段落时长尽量不要超过 8 秒，整体紧凑。\n\n"
    "请只输出一个 JSON 对象（不要任何额外说明文字，也不要 markdown 代码围栏），字段如下：\n"
    "{\n"
    '  "summary": "视频主题与内容概述（100字内）",\n'
    '  "highlights": [{"start": <秒,数字>, "end": <秒,数字>, "reason": "值得保留的精华：菜品特写/口味评价/惊艳反应"}],\n'
    '  "redundant": [{"start": <秒,数字>, "end": <秒,数字>, "reason": "可删：空镜/无对话进食/停顿/重复/冗长过渡"}],\n'
    '  "target_duration_sec": <建议保留的总时长，整数，范围 55-65>\n'
    "}\n\n"
    "要求：\n"
    "- start/end 以秒为单位（浮点或整数均可），基于视频时间轴，不要用 HH:MM:SS。\n"
    "- highlights 与 redundant 时间尽量不重叠；若某段既有点信息又空，整体归入 redundant 更稳妥。\n"
    "- 目标：把约 248 秒激进压到 55-65 秒，只留最抓人的看点，每段尽量 <=8 秒。"
)


def main():
    load_env()
    video = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VIDEO
    out_name = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    odir = out_dir()
    out_path = odir / out_name

    file_id = upload_file(video, preprocess={"video": {"fps": 0.3}})

    print("[2/2] 豆包理解视频内容（激进版高光/冗余决策）...")
    text = video_understand(file_id, PROMPT, model=DEFAULT_VIDEO_MODEL)

    result = extract_json(text)
    result.setdefault("model", DEFAULT_VIDEO_MODEL)
    result.setdefault("video", video)
    result.setdefault("file_id", file_id)

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== 豆包高光决策 (v2 激进版) =====")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n结果已保存到 {out_path}")


if __name__ == "__main__":
    main()
