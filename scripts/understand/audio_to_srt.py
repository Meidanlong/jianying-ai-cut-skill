#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用火山方舟"音频理解"把音频转写成带时间戳的字幕(SRT)。
用法: python audio_to_srt.py <音频路径> [输出srt路径]
产物: 默认 <out>/transcript.srt
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import out_dir, load_env  # noqa: E402
from ark_client import upload_file, audio_transcribe  # noqa: E402


def to_srt_time(ts: str) -> str:
    m, s = ts.split(":")
    s = float(s)
    mm = int(s)
    ms = int(round((s - mm) * 1000))
    return f"00:{int(m):02d}:{mm:02d},{ms:03d}"


def main():
    load_env()
    if len(sys.argv) < 2:
        print("用法: python audio_to_srt.py <音频路径> [输出srt路径]")
        sys.exit(2)
    audio = sys.argv[1]
    odir = out_dir()
    out_srt = sys.argv[2] if len(sys.argv) > 2 else str(odir / "transcript.srt")

    file_id = upload_file(audio)
    print("[2/3] 豆包转写...")
    prompt = (
        "请把这段音频中的人声按自然的说话停顿拆成短句，一句一条，逐句输出，"
        "并且每条给出该句语音真正的起止时间戳。\n"
        "非常重要：不要合并多个句子成一个长段；每句话必须独立成条；"
        "start/end 必须精确对应该句话的说话起止（从第一个字到最后一个字），而不是整段平均。\n"
        "只输出合法 JSON（不要多余文字）：\n"
        '{"segments":[{"start":"MM:SS.mmm","end":"MM:SS.mmm","text":"一句话"}]}\n'
        "要求：时间戳精确到毫秒；中文文本去掉语气词和重复；按实际停顿切分。"
    )
    text = audio_transcribe(file_id, prompt)
    print("[3/3] 转写完成")
    print(text)

    data = json.loads(text)
    segs = data.get("segments", [])
    lines = []
    for i, seg in enumerate(segs, 1):
        lines.append(str(i))
        lines.append(f"{to_srt_time(seg['start'])} --> {to_srt_time(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")

    Path(out_srt).parent.mkdir(parents=True, exist_ok=True)
    Path(out_srt).write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSRT 已保存: {out_srt}（{len(segs)} 句）")


if __name__ == "__main__":
    main()
