---
name: ai-jianying-cut
description: 全自动/半自动短视频剪辑流水线。用豆包(火山方舟)视频/音频理解做内容决策，脚本精切生成剪映草稿，再由 Doubao 通过 mac_computer_use_tool 操作剪映 GUI 完成「两遍剪映 AI」粗剪与精修导出。适合「把一段长视频（口播/生活记录/活动）自动剪出竖屏短视频成片」的任务。
---

# ai-jianying-cut

把「**豆包理解 + 脚本精切 + 两遍剪映 AI**」封装成可复用流程。

- **豆包理解**：视频/音频上传方舟，多模态理解产出「内容概述 + 逐段角色标注 + 带时间戳字幕 + 情绪点」。
- **脚本精切**：把理解层决策单（删除/保留区间）转换成**剪映草稿**（保留段拼时间轴 + 字幕轨 + 片头封面），落盘到 `~/Movies/JianyingPro/.../com.lveditor.draft/<项目名>/`。
- **两遍剪映 AI**：在剪映 App 内，**由 Doubao 通过 `mac_computer_use_tool` 操作剪映 GUI** 完成两遍 AI 处理与导出（见下）。

## 适用场景
- 用户给了一段长视频，想自动剪出节奏紧凑的竖屏短视频成片。
- 需要「保核心结果/删冗余」这类语义级剪辑，而不是机械切镜头。
- 最终成片要在剪映里做 AI 字幕/调色/配乐并导出。

## 环境前置（务必先确认）
1. **Python 虚拟环境**（避免系统 PEP 668 限制）：
   `python3 -m venv ./_venv && source ./_venv/bin/activate`
2. **依赖**：`pip install -r requirements.txt`（已剔除 uiautomation / playwright）。
3. **ffmpeg / ffprobe** 在 `PATH`（媒体抽帧、时长/尺寸探测、音轨抽取）。缺失会导致字幕轨重映射与封面抽取失败。
4. **剪映专业版**已安装并登录；草稿目录默认 `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/`。
5. **ARK_API_KEY**：复制 `.env.example` 为 `.env` 填写（脚本自动读取）。无 Key 时 `run_pipeline.py --dry-run` 可用占位数据跑通结构。

> ⚠️ macOS 兼容要点：jianying-editor-skill v1.7 在 macOS **只生成草稿、不能自动导出**（自动导出仅 Windows）。因此「两遍剪映 AI」必须在剪映 App 内由 Doubao 通过 `mac_computer_use_tool` 操作 GUI 完成——这是有意为之的自动化边界，不是缺失功能。

## 完整流程

### 阶段一 · 豆包理解（全自动，需 ARK_API_KEY）
| 步骤 | 脚本 | 产物 |
|---|---|---|
| 上传视频 + 视频理解 | `scripts/understand/run_video_understand.py <视频> [规则]` | `out/understand_result.json` + `out/upload_info.json`(file_id) |
| 抽音轨 + 音频转写 | `scripts/understand/audio_to_srt.py <audio.mp3>` | `out/transcript.srt` |
| 逐段角色标注 | `scripts/understand/understand_roles.py` | `out/roles_result.json` |
| （可选）快节奏可删段 | `scripts/understand/compact_understand.py` | `out/compact_raw.json` |
| 情绪/事件点派生 | `scripts/understand/understand_emotions.py` | `out/emotions_result.json` |

### 阶段二 · 决策与质检（全自动，纯本地）
| 步骤 | 脚本 | 产物 / 作用 |
|---|---|---|
| 角色 → 分层决策 | `scripts/plan/roles_to_plan.py` | `out/compact_result.json`（删/留区间，结果句强制保护） |
| 字幕保护 | `scripts/plan/fix_plan.py` | 重写决策单，说话段绝不删，只删无言停顿（备份 `.bak.json`） |
| 关键信息质量门 | `scripts/plan/check_cut.py` | 退出码 0/1：结果/输赢句被删则报错阻断 |

### 阶段三 · 脚本精切（全自动，生成剪映草稿）
| 步骤 | 脚本 | 产物 |
|---|---|---|
| 主角识别 | `scripts/cover/identify_lead.py <视频>` | `out/lead_result.json` |
| 封面海报 | `scripts/cover/make_cover.py <视频>` | `out/cover_34.png` / `out/cover_916.png` |
| SRT → ASS | `scripts/subtitle/srt_to_ass.py` | `out/subtitle.ass` |
| **决策单 → 剪映草稿** | `scripts/bridge/build_jianying_draft.py --video <视频> --project <名>` | 剪映草稿文件夹（落草稿目录） |

> 剪映草稿只能「拼保留段」不能直接删段：`build_jianying_draft` 对删除区间取补集得到保留段，每段用 `source_timerange` 偏移拼到 VideoTrack；字幕按保留段重映射到目标时间轴；封面作为片头 3s 卡片。画布方向按源视频自动判定（竖屏 1080×1920 / 横屏 1920×1080）。

### 阶段四 · 两遍剪映 AI（Doubao 通过 mac_computer_use_tool 操作剪映 GUI）
> 这一段**不是脚本**，而是 Doubao 在剪映桌面端里用 `mac_computer_use_tool` 操控 GUI 完成。脚本只负责把精确草稿准备好；最终 AI 处理与导出由 Doubao 在剪映内执行。

- **第一遍剪映 AI（粗剪 / 初处理）**
  - 打开 脚本生成的草稿（或导入原素材）。
  - 用剪映的「智能字幕 / 文稿匹配」补齐并校验语音字幕；如对节奏不满意，可触发「剪口播 / AI 成片」做一次镜头初切。
  - 目的：让字幕与镜头初版就位，作为后续精修底稿。

- **第二遍剪映 AI（精修 / 导出）**
  - 在初稿上套「AI 调色 / 智能配乐 / 一键成片」做最终润色。
  - 检查封面、字幕、节奏，确认无误后**点击导出**成片（macOS 无自动导出，必须由 Doubao 在 GUI 内点导出）。
  - 目的：产出最终短视频成片。

## 一键运行
```bash
# 真实模式
source ./_venv/bin/activate
python scripts/run_pipeline.py --video /path/to/your_video.mov \
    --rule "去口误,去静默,保留高光段,竖屏" --project 我的剪辑

# 无 Key 演示结构
python scripts/run_pipeline.py --dry-run
```
`run_pipeline.py` 按上述四个阶段顺序调用各脚本；任一阶段失败会中断并给出提示。`--skip-draft` 可只跑到决策/封面不生成草稿；`--no-cover` 跳过封面。

## 安全与开源合规
- 本仓库**不含**任何 API Key、私人视频/字幕内容、成片或 BGM（见 `.gitignore`）。
- `vendor/jianying_editor_skill_scripts/` 来自 `jianying-editor-skill`（MIT，© luoluoluo22），其内 `pyJianYingDraft` 为 Apache-2.0（© GuanYixuan），许可证见 `vendor/NOTICE.md`。
- 不要把带真实素材路径、人名、地址的中间产物提交进仓库。
