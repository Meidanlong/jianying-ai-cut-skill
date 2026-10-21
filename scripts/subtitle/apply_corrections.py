#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对 ASR 出的 SRT 应用专有名词/粤语口语校正词表，并产出人工复核清单。

词表: scripts/subtitle/corrections.json
  - fix:     已知错词 -> 正词，脚本自动替换
  - protect: 粤语口语正确写法（如『胜瓜』=粤语『丝瓜』），仅提示、不自动改
  - review:  语义存疑词，含这些词的句子会被列入 review_checklist.md 待人工确认

用法:
  python apply_corrections.py input.srt --corrections corrections.json \
      --out input.corrected.srt --checklist review_checklist.md

产物:
  - <out>.srt            校正后的字幕
  - <checklist>.md       人工复核清单（已改项 + 待确认项 + 保护词提示）
详见 docs/pitfalls.md #11。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def parse_srt(text):
    """返回 [("1", "00:00:02,510 --> 00:00:07,930", "文本"), ...]。"""
    blocks = re.split(r"\n\s*\n", text.strip())
    segs = []
    for b in blocks:
        lines = [l for l in b.splitlines() if l.strip() != ""]
        if len(lines) < 2:
            continue
        idx, time_line, *content = lines
        if "-->" not in time_line:
            continue
        segs.append((idx.strip(), time_line.strip(), "\n".join(content).strip()))
    return segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("srt", help="待校正 SRT")
    ap.add_argument("--corrections", default=str(Path(__file__).with_name("corrections.json")),
                    help="校正词表 json")
    ap.add_argument("--out", help="输出 SRT（默认 <输入>.corrected.srt）")
    ap.add_argument("--checklist", help="复核清单 md（默认 <输入>.review_checklist.md）")
    args = ap.parse_args()

    corr = json.loads(Path(args.corrections).read_text(encoding="utf-8"))
    fix = corr.get("fix", {})
    protect = corr.get("protect", [])
    review = corr.get("review", [])

    segs = parse_srt(Path(args.srt).read_text(encoding="utf-8"))
    changed, protected_hits, review_hits = [], [], []

    out_segs = []
    for idx, time_line, text in segs:
        new_text = text
        for wrong, right in fix.items():
            if wrong in new_text:
                new_text = new_text.replace(wrong, right)
                changed.append((wrong, right, text, new_text))
        for p in protect:
            if p in new_text:
                protected_hits.append((p, new_text))
        for r in review:
            if r in new_text:
                review_hits.append((r, new_text))
        out_segs.append((idx, time_line, new_text))

    out_srt = args.out or (str(Path(args.srt).with_suffix("")) + ".corrected.srt")
    with open(out_srt, "w", encoding="utf-8") as f:
        for idx, time_line, text in out_segs:
            f.write(f"{idx}\n{time_line}\n{text}\n\n")

    checklist = args.checklist or (str(Path(args.srt).with_suffix("")) + ".review_checklist.md")
    lines = ["# 字幕人工复核清单", ""]
    lines.append(f"源文件: `{args.srt}`  校正后: `{out_srt}`", )
    lines.append("")
    lines.append(f"## 已自动修正（{len(changed)} 处）")
    if changed:
        for wrong, right, old, new in changed:
            lines.append(f"- `{wrong}` → `{right}`  （原：「{old}」→ 改：「{new}」）")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("## 待人工确认（含存疑词）")
    if review_hits:
        for r, t in review_hits:
            lines.append(f"- 含「{r}」：{t}")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("## 保护词提示（粤语口语，请勿误改）")
    if protected_hits:
        for p, t in protected_hits:
            lines.append(f"- 保留「{p}」：{t}")
    else:
        lines.append("- 未命中（如『胜瓜』=粤语丝瓜，属正确写法，不应改成普通话）")
    Path(checklist).write_text("\n".join(lines), encoding="utf-8")

    print(f"✅ 已写出校正字幕: {out_srt}")
    print(f"✅ 已写出复核清单: {checklist}")
    print(f"   自动修正 {len(changed)} 处，待确认 {len(review_hits)} 句，保护词命中 {len(protected_hits)} 句")


if __name__ == "__main__":
    main()
