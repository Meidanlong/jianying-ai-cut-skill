---
name: ai-jianying-cut
description: 全自动/半自动短视频剪辑流水线。用豆包(火山方舟)视频/音频理解做内容决策，CodeBuddy 精切生成剪映草稿，再由 Doubao 通过 mac_computer_use_tool 操作剪映 GUI 完成「两遍剪映 AI」粗剪与精修导出。适合「把一段长视频（口播/生活记录/活动）自动剪出竖屏短视频成片」的任务。
---

# ai-jianying-cut

把「**豆包理解 + CodeBuddy 精切 + 两遍剪映 AI**」封装成可复用流程。

- **豆包理解**：视频/音频上传方舟，多模态理解产出「内容概述 + 逐段角色标注 + 带时间戳字幕 + 情绪点」。
- **CodeBuddy 精切**：把理解层决策单（删除/保留区间）转换成**剪映草稿**（保留段拼时间轴 + 字幕轨 + 片头封面），落盘到 `~/Movies/JianyingPro/.../com.lveditor.draft/<项目名>/`。
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

> 📌 **踩坑复盘先看 `docs/pitfalls.md`**：14 条实测坑（单轨拼接、剪映打开前明文自检、音视频逐段对齐、方向自适应、保留段取高光补集、字幕重对齐成片、ffmpeg 兜底、ASR 专名校正、隐私红线等），每条含「现象→原因→正确做法」。

## 完整流程

> 标准阶段顺序：**0 环境素材 → 0.5 需求澄清/brief 定稿 → 1 第一遍剪映智能粗剪(GUI) → 2 豆包理解(消费粗剪版) → 3 决策质检 → 4 CodeBuddy 精切草稿 → 5 草稿自检 → 6 第二遍剪映 AI 精修导出**。
> 阶段 1 与 6 在剪映 App 内由 Doubao 经 `mac_computer_use_tool` 操作 GUI 完成；阶段 0.5 由 Doubao 向用户澄清需求。脚本只负责 0/2/3/4/5 的程序化部分。

### 阶段零 · 需求澄清与剪辑 brief 定稿（Doubao 监督，向用户澄清）
- **执行者**：Doubao 向用户澄清剪辑要求，形成结构化 `clip_brief.yaml`（不写真实门店名/个人路径）。
- **必填字段（5）**：`topic` / `target_duration:[min,max]` / `orientation` / `must_keep` / `must_delete`；其余选填带默认值（见 `examples/clip_brief.yaml`）。
- **产出**：`examples/clip_brief.yaml`（或用户指定路径）。
- **下游用途**：① `understand_highlights*.py` 把 brief 拼进豆包提示词（主题口径/目标时长/必保必删）；② `build_plan.py` 读 `target_duration` 区间做时长校验；③ `selfcheck_draft.py` 以该区间为自检窗口。无 brief 时脚本回退默认行为。

### 阶段一 · 第一遍剪映智能粗剪（Doubao 经 mac_computer_use_tool 操作 GUI，理解前执行）
- **执行者**：Doubao 在剪映内用「智能粗剪 / AI 成片」机械掐掉停顿、语气词、废镜头。
- **产出**：**粗剪版**视频（更短、更干净）。
- **铁律（坑 #15 相关）**：必须在豆包理解**之前**完成，严禁跳过。原因与后果见 `references/two_pass_jianying_ai.md` 流程坑。

### 阶段二 · 豆包理解（全自动，需 ARK_API_KEY，消费粗剪版）
| 步骤 | 脚本 | 产物 |
|---|---|---|
| 上传粗剪版 + 视频理解 | `scripts/understand/run_video_understand.py <粗剪版> [规则]` | `out/understand_result.json` + `out/upload_info.json`(file_id) |
| 抽音轨 + 音频转写 | `scripts/understand/audio_to_srt.py <audio.mp3>` | `out/transcript.srt` |
| 逐段角色标注 | `scripts/understand/understand_roles.py` | `out/roles_result.json` |
| （可选）快节奏可删段 | `scripts/understand/compact_understand.py` | `out/compact_raw.json` |
| 情绪/事件点派生 | `scripts/understand/understand_emotions.py` | `out/emotions_result.json` |
| 高光决策（v1 宽松 / v2 激进，拼入 brief） | `scripts/understand/understand_highlights*.py <粗剪版> --brief <brief>` | `out/ganzehn_pass1_understand*.json`（highlights/redundant/target_duration_sec） |

### 阶段三 · 决策与质检（全自动，纯本地）
| 步骤 | 脚本 | 产物 / 作用 |
|---|---|---|
| 角色 → 分层决策 | `scripts/plan/roles_to_plan.py` | `out/compact_result.json`（删/留区间，结果句强制保护） |
| 字幕保护 | `scripts/plan/fix_plan.py` | 重写决策单，说话段绝不删，只删无言停顿（备份 `.bak.json`） |
| 关键信息质量门 | `scripts/plan/check_cut.py` | 退出码 0/1：结果/输赢句被删则报错阻断 |
| 高光 → 决策单（补集删除，读 brief 时长校验） | `scripts/plan/build_plan.py <understand.json> --duration <总秒> --brief <brief>` | `out/compact_result.json`（deletes=高光补集，杜绝 redundant 漏标缝隙导致时长超标，见 pitfalls #6/#15） |

### 阶段四 · CodeBuddy 精切（全自动，生成剪映草稿）
| 步骤 | 脚本 | 产物 |
|---|---|---|
| 主角识别 | `scripts/cover/identify_lead.py <粗剪版>` | `out/lead_result.json` |
| 封面海报 | `scripts/cover/make_cover.py <粗剪版>` | `out/cover_34.png` / `out/cover_916.png` |
| SRT → ASS | `scripts/subtitle/srt_to_ass.py` | `out/subtitle.ass`（竖屏白字黑描边，见 `docs/subtitle_spec.md`） |
| 原始素材顺序拼接（可选，生成 highlights 决策的 pass1 输入） | `scripts/bridge/build_pass1.py --clips <8段...> --project <名>` | 草稿（无精切/无字幕/无封面，仅按文件名顺序拼单轨） |
| **决策单 → 剪映草稿** | `scripts/bridge/build_jianying_draft.py --video <粗剪版> --project <名>` | 剪映草稿文件夹（落草稿目录） |

> 剪映草稿只能「拼保留段」不能直接删段：`build_jianying_draft` 对删除区间取补集得到保留段，每段用 `source_timerange` 偏移拼到 VideoTrack；字幕按保留段重映射到目标时间轴；封面作为片头 3s 卡片。画布方向按源视频自动判定（竖屏 1080×1920 / 横屏 1920×1080）。

### 阶段五 · 草稿结构自检（打开剪映前必跑）
| 步骤 | 脚本 | 产物 |
|---|---|---|
| **草稿结构自检（打开剪映前必跑）** | `scripts/bridge/selfcheck_draft.py <草稿目录> --brief <brief>`（或 `--target <秒>`） | 逐项 PASS/FAIL（单轨/时长/音视频对齐/字幕落点），退出码 0/1 |

> 🔤 **成片字幕必须对齐最终成片本身**（坑 #10）：精切/重拼后时间轴已变，务必对成片**重新抽音轨 → 重新 ASR**，不要用旧粗剪的 srt。一键编排：`scripts/subtitle/build_subtitles.py --video <成片> --out <字幕成片>`（抽音→ASR→校正→烧录）。ASR 专有名词/粤语谐音错用 `scripts/subtitle/corrections.json` 词表校正（`apply_corrections.py` 产出复核清单，含「胜瓜=粤语丝瓜」类保护词与待确认项，见 `docs/pitfalls.md` #11）。

### 阶段六 · 第二遍剪映 AI（Doubao 通过 mac_computer_use_tool 操作剪映 GUI，精修 + 导出）
> 这一段**不是脚本**，而是 Doubao 在剪映桌面端里用 `mac_computer_use_tool` 操控 GUI 完成。CodeBuddy 只负责把精确草稿准备好；最终 AI 处理与导出由 Doubao 在剪映内执行。
> 注：**第一遍智能粗剪已在阶段一完成（理解前）**；阶段六在 CodeBuddy 生成的草稿上做精修与导出。

- **第二遍剪映 AI（精修 / 导出）**
  - 打开 CodeBuddy 生成的草稿，用「智能字幕 / 文稿匹配」补齐并校验语音字幕（如阶段一粗剪后字幕需重对齐，见坑 #10）。
  - 套「AI 调色 / 智能配乐 / 一键成片」做最终润色；检查封面、字幕、节奏。
  - 确认无误后**点击导出**成片（macOS 无自动导出，必须由 Doubao 在 GUI 内点导出，或 ⌘E 唤起导出框 + 回车）。
  - 目的：产出最终短视频成片。

> 💡 **导出兜底（坑 #7）**：若剪映 GUI 导出卡死 / 多进程混乱，可跳过 GUI，用 `scripts/export/ffmpeg_export.py --plan <决策单> --src <成片或源视频> --out <final.mp4>` 本地 `filter_complex` 直出（H.264+AAC）。缺点是不带剪映 AI 调色/配乐，见 `docs/export_fallback.md`。

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
