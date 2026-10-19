#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
角色标注 -> 分层剪辑决策。
删除: 冗余语音 / 冗余空白 / 废镜头
保留: 核心结果 / 关键动作 / 铺垫说明
再强制保护"结果句"语音(ASR关键词)不被删除区间吃掉。
写回 <out>/compact_result.json 供精切(build_jianying_draft)使用。

用法: python roles_to_plan.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import out_dir, load_env, ts2sec, sec2ts  # noqa: E402

DELETE_ROLES = {"冗余语音", "冗余空白", "废镜头"}
KEEP_ROLES = {"核心结果", "关键动作", "铺垫说明"}
# 结果句关键词（同 check_cut）：含这些的语音为"报结果"，强制保留
KEYWORDS = ["中", "赢", "百", "千", "结果", "二举", "一秀", "状元",
            "榜眼", "探花", "开仓", "放粮", "宣布", "赢了", "中了", "块钱"]


def result_speech_segments(srt_text: str) -> list:
    """返回含结果关键词的语音段时间。"""
    lines = [l.strip() for l in srt_text.splitlines() if l.strip()]
    out = []
    for i in range(0, len(lines), 3):
        m = re.match(r"(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)", lines[i + 1])
        if not m:
            continue

        def s(t):
            h, mn, r = t.split(":")
            ss, ms = r.split(",")
            return int(h) * 3600 + int(mn) * 60 + int(ss) + int(ms) / 1000

        text = lines[i + 2]
        if any(k in text for k in KEYWORDS):
            out.append((s(m.group(1)) - 0.3, s(m.group(2)) + 0.3))
    return out


def protect(deletes: list, protected: list) -> list:
    """从删除区间中挖掉被保护(结果句)覆盖的部分。"""
    out = []
    for ds, de in deletes:
        cur = [(ds, de)]
        for a, b in protected:
            nxt = []
            for x, y in cur:
                if b <= x or a >= y:
                    nxt.append((x, y))
                else:
                    if x < a:
                        nxt.append((x, a))
                    if b < y:
                        nxt.append((b, y))
            cur = nxt
        out.extend(cur)
    out.sort()
    merged = []
    for x, y in out:
        if y - x < 0.4:
            continue
        if merged and x - merged[-1][1] < 0.15:
            merged[-1] = (merged[-1][0], max(merged[-1][1], y))
        else:
            merged.append((x, y))
    return merged


def main():
    load_env()
    odir = out_dir()
    roles_path = odir / "roles_result.json"
    srt_path = odir / "transcript.srt"
    if not roles_path.exists():
        print(f"缺少 {roles_path}，请先跑 understand_roles.py")
        sys.exit(2)
    if not srt_path.exists():
        print(f"缺少 {srt_path}，请先跑 audio_to_srt.py")
        sys.exit(2)

    raw = roles_path.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    roles = json.loads(raw)
    segs = roles["segments"]

    # 1) 角色标注生成删除区间
    deletes = [(ts2sec(s["start"]), ts2sec(s["end"]))
               for s in segs if s["role"] in DELETE_ROLES]
    keeps = [s for s in segs if s["role"] in KEEP_ROLES]

    # 2) 强制保护结果句语音
    protected = result_speech_segments(srt_path.read_text(encoding="utf-8"))
    final_del = protect(deletes, protected)

    plan = {
        "deletes": [{"start": sec2ts(a), "end": sec2ts(b),
                     "reason": "冗余(经结果句保护)"} for a, b in final_del],
        "highlights": [{"start": s["start"], "end": s["end"],
                        "reason": s.get("desc", "")} for s in keeps],
        "keep_roles": sorted({s["role"] for s in keeps}),
        "summary": "分层剪辑：核心结果/关键动作/铺垫保留，冗余删除，结果句强制保护",
    }
    (odir / "compact_result.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"角色删除 {len(deletes)} 段 -> 经结果句保护后 {len(final_del)} 段")
    for a, b in final_del:
        print(f"  删 [{sec2ts(a)}-{sec2ts(b)}]  ({b-a:.1f}s)")
    print(f"保留 {len(keeps)} 段（核心结果 {sum(1 for s in keeps if s['role']=='核心结果')} / 关键动作 {sum(1 for s in keeps if s['role']=='关键动作')} / 铺垫 {sum(1 for s in keeps if s['role']=='铺垫说明')}）")
    print(f"决策单已写入 {odir/'compact_result.json'}")


if __name__ == "__main__":
    main()
