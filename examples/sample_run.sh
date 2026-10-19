#!/usr/bin/env bash
# 本地端到端跑法示例（视频路径用 $1 传入，不要写死真实私人路径）。
# 用法: bash examples/sample_run.sh /path/to/your_video.mov
set -euo pipefail

VIDEO="${1:-}"
if [ -z "$VIDEO" ]; then
  echo "用法: bash examples/sample_run.sh /path/to/your_video.mov"
  exit 2
fi

# 仓库根（脚本所在目录的上两级）
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 虚拟环境（如未创建可先：python3 -m venv ./_venv && ./_venv/bin/pip install -r requirements.txt）
VENV="${VENV:-./_venv}"
PY="$VENV/bin/python"
if [ ! -x "$PY" ]; then
  echo "未找到 $PY，请先创建虚拟环境并安装依赖。"
  exit 2
fi

# ARK_API_KEY 从仓库根 .env 读取（脚本内部也会读）；也可 export 注入
export PATH="/usr/local/bin:$PATH"   # 确保 ffmpeg/ffprobe 在 PATH

"$PY" scripts/run_pipeline.py \
  --video "$VIDEO" \
  --rule "去口误,去静默,保留高光段,竖屏" \
  --project "AI_JianYing_Cut" \
  --title "视频标题" \
  --subtitle ""

echo
echo "流水线结束。下一步：在剪映里打开草稿，由 Doubao 经 mac_computer_use_tool 完成两遍剪映 AI（粗剪+导出）。"
