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
        w, h = out.stdout.strip().split(",")
        return int(w), int(h)
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
