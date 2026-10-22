#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第一遍粗剪的「豆包理解 / 高光决策」：上传粗剪视频给豆包视频理解模型
（doubao-seed-2-1-pro-260628），输出高光段与冗余段，供后续精切使用。

产物: out/ganzehn_pass1_understand.json
格式:
{
  "summary": "...",
  "highlights": [{"start": 秒, "end": 秒, "reason": "..."}],
  "redundant":  [{"start": 秒, "end": 秒, "reason": "..."}],
  "target_duration_sec": 90
}

用法: python understand_highlights.py [视频路径] [输出json路径]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import out_dir, load_env, ensure_on_path, load_brief, inject_brief_into_prompt  # noqa: E402
ensure_on_path()
from ark_client import upload_file, video_understand, DEFAULT_VIDEO_MODEL  # noqa: E402

# 默认输入取相对名（从命令行或 config 传入绝对/相对路径）；脚本内禁止硬编码个人绝对路径
DEFAULT_VIDEO = "ganzehn_pass1.mp4"
DEFAULT_OUT = "ganzehn_pass1_understand.json"


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
    "你是一名资深短视频剪辑师。请观看这段探店 vlog（竖屏 1080x1920，约 248 秒），"
    "给出用于「精剪」的高光与冗余决策。\n\n"
    "请只输出一个 JSON 对象（不要任何额外说明文字，也不要 markdown 代码围栏），字段如下：\n"
    "{\n"
    '  "summary": "视频主题与内容概述（100字内）",\n'
    '  "highlights": [{"start": <秒,数字>, "end": <秒,数字>, "reason": "值得保留的精彩内容，如菜品特写/口味评价/门店环境/惊艳瞬间"}],\n'
    '  "redundant": [{"start": <秒,数字>, "end": <秒,数字>, "reason": "可删掉的停顿/重复/废话/冗长过渡/无信息空镜"}],\n'
    '  "target_duration_sec": <建议保留的总时长，整数，范围 60-90>\n'
    "}\n\n"
    "要求：\n"
    "- start/end 以秒为单位（浮点或整数均可），基于视频时间轴，不要用 HH:MM:SS。\n"
    "- highlights 覆盖建议保留的精华；redundant 覆盖建议删除的片段，两者时间尽量不要大量重叠。\n"
    "- 目标：把约 248 秒压到 60-90 秒，保留最吸引人的看点。"
)


def main():
    load_env()
    # 解析可选 --brief（其余位置参数保持原语义：视频路径、输出名）
    brief_path = None
    clean = []
    i = 0
    rest = sys.argv[1:]
    while i < len(rest):
        if rest[i] == "--brief":
            brief_path = rest[i + 1]
            i += 2
        else:
            clean.append(rest[i])
            i += 1
    video = clean[0] if clean else DEFAULT_VIDEO
    out_name = clean[1] if len(clean) > 1 else DEFAULT_OUT
    odir = out_dir()
    out_path = odir / out_name

    brief = load_brief(brief_path) if brief_path else None
    if brief:
        print(f"[brief] 已加载剪辑需求: topic={brief.get('topic')!r} "
              f"目标时长={brief.get('target_duration')} 画幅={brief.get('orientation')}")

    # 1) 上传视频（fps 0.3 控制抽帧密度，节省 token）
    file_id = upload_file(video, preprocess={"video": {"fps": 0.3}})

    # 2) 视频理解（提示词拼入 brief 需求；无 brief 则走默认提示词）
    print("[2/2] 豆包理解视频内容（高光/冗余决策）...")
    prompt = inject_brief_into_prompt(PROMPT, brief, default_range=(60, 90))
    text = video_understand(file_id, prompt, model=DEFAULT_VIDEO_MODEL)

    result = extract_json(text)
    result.setdefault("model", DEFAULT_VIDEO_MODEL)
    result.setdefault("video", video)
    result.setdefault("file_id", file_id)
    result.setdefault("brief_topic", (brief or {}).get("topic"))

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== 豆包高光决策 =====")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n结果已保存到 {out_path}")


if __name__ == "__main__":
    main()
