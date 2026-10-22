#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-jianying-cut 公共工具：环境变量加载、输出目录、时间码转换、媒体探测。

所有子脚本统一从这里取：
  - load_env()        读取仓库根目录 .env（含 ARK_API_KEY）
  - out_dir()         统一的中间产物目录（默认 out/，可用 AIJC_OUT 覆盖）
  - ts2sec / sec2ts   时间码 <-> 秒
  - probe_duration()  ffprobe 取视频时长
  - video_size()      ffprobe 取宽高（用于判断横/竖屏）

注意：本文件不得包含任何真实密钥、个人路径或私人素材名。
"""
import os
import re
import subprocess
import sys
from pathlib import Path

# 仓库根目录（common.py 位于 <repo>/scripts/common.py）
REPO_ROOT = Path(__file__).resolve().parent.parent

# 火山方舟 API 基址（公开端点，非密钥）
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


# ---------------------------------------------------------------------------
# 剪辑需求 brief（步骤 0.5 产出，下游 understand_highlights / build_plan / selfcheck 读取）
# ---------------------------------------------------------------------------
def load_yaml(path: str) -> dict:
    """读取 YAML 配置文件，失败抛异常。依赖 PyYAML。"""
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_brief(path: str = None) -> dict:
    """加载剪辑需求 brief（examples/clip_brief.yaml）。

    不传 path 时返回 None（向后兼容：无 brief 走默认行为）。
    返回 dict，至少应含 必填 5 字段：topic / target_duration[min,max] /
    orientation / must_keep / must_delete。其余字段带默认值由调用方处理。
    """
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"❌ 找不到 brief 文件: {path}")
    data = load_yaml(str(p)) or {}
    return data


def brief_target_range(brief: dict):
    """从 brief 取目标保留时长区间 [min, max]，缺失返回 None。"""
    if not brief:
        return None
    td = brief.get("target_duration")
    if isinstance(td, (list, tuple)) and len(td) == 2:
        return float(td[0]), float(td[1])
    return None


def _brief_block(brief: dict) -> str:
    """把 brief 拼成一段追加到豆包提示词的需求说明。"""
    lines = ["\n【用户剪辑需求 brief（务必遵循）】"]
    if brief.get("topic"):
        lines.append(f"- 主题与口径：{brief['topic']}")
    if brief.get("orientation"):
        lines.append(f"- 画幅倾向：{brief['orientation']}")
    if brief.get("rhythm"):
        lines.append(f"- 节奏倾向：{brief['rhythm']}")
    mk = brief.get("must_keep")
    if mk:
        lines.append("- 必保内容（尽量保留）：" + "、".join(mk))
    md = brief.get("must_delete")
    if md:
        lines.append("- 必删内容（尽量剔除）：" + "、".join(md))
    if brief.get("subtitles"):
        lines.append(f"- 字幕：开启（{brief.get('subtitle_lang', 'zh-CN')}）")
    if brief.get("platform"):
        lines.append(f"- 发布平台：{brief.get('platform')}")
    fb = brief.get("forbidden")
    if fb:
        lines.append("- 特殊禁忌（不要出现）：" + "、".join(fb))
    lines.append("请严格依据上述需求做高光/冗余判断，必保内容优先保留，必删内容优先剔除。")
    return "\n".join(lines)


def inject_brief_into_prompt(prompt: str, brief: dict, default_range=(60, 90)) -> str:
    """把 brief 注入提示词：替换写死的时长/区间，并追加需求段。无 brief 原样返回。"""
    if not brief:
        return prompt
    lo, hi = [int(x) for x in (brief_target_range(brief) or default_range)]
    p = prompt.replace("约 248 秒", "本视频").replace("248 秒", "本视频")
    p = re.sub(r"\d+-\d+", f"{lo}-{hi}", p)
    return p + "\n" + _brief_block(brief)


def load_env(path=None) -> None:
    """从仓库根目录 .env 读取环境变量（ARK_API_KEY 等），仅 setdefault 不覆盖。"""
    p = Path(path) if path else (REPO_ROOT / ".env")
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def out_dir(env_var: str = "AIJC_OUT") -> Path:
    """统一中间产物目录，默认 <repo>/out，可用环境变量 AIJC_OUT 覆盖。"""
    d = os.getenv(env_var) or str(REPO_ROOT / "out")
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_on_path() -> None:
    """把 <repo>/scripts 加入 sys.path，便于子脚本 import common / ark_client。"""
    scripts = str(REPO_ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


def ts2sec(ts: str) -> float:
    """'HH:MM:SS' 或 'HH:MM:SS.mmm' -> 秒。"""
    parts = ts.split(":")
    h, m = int(parts[0]), int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s


def sec2ts(t: float) -> str:
    """秒 -> 'HH:MM:SS.ss'（保留两位小数）。"""
    t = max(0.0, float(t))
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{int(m):02d}:{s:05.2f}"


# ---------------------------------------------------------------------------
# 媒体探测（依赖 ffprobe，已在 PATH；缺失时返回 0 / None）
# ---------------------------------------------------------------------------
def _ffprobe() -> str:
    exe = os.getenv("FFPROBE") or "ffprobe"
    return exe


def probe_duration(video: str) -> float:
    """ffprobe 取视频总时长（秒），失败返回 0.0。"""
    try:
        out = subprocess.run(
            [_ffprobe(), "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video],
            capture_output=True, text=True, check=True,
        )
        return float(out.stdout.strip())
    except Exception:
        return 0.0


def video_size(video: str):
    """ffprobe 取 (width, height)，失败返回 (None, None)。"""
    try:
        out = subprocess.run(
            [_ffprobe(), "-v", "error",
             "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0", video],
            capture_output=True, text=True, check=True,
        )
        # csv=p=0 输出可能带行尾逗号/空字段，取首个非空行的前两个数值
        line = next((l for l in out.stdout.splitlines() if l.strip()), "")
        parts = [p for p in line.split(",") if p.strip()]
        if len(parts) < 2:
            return None, None
        return int(parts[0]), int(parts[1])
    except Exception:
        return None, None


def parse_json(text: str):
    """从模型返回文本中安全解析 JSON（兼容 ```json 代码块包裹）。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return __import__("json").loads(text)
    except Exception:
        # 退一步：截取第一个 { 到最后一个 }
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e != -1 and e > s:
            return __import__("json").loads(text[s:e + 1])
        raise
