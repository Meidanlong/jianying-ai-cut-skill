# ai-jianying-cut

用 **豆包（火山方舟）理解 + 脚本精切 + 两遍剪映 AI** 把长视频自动剪成竖屏短视频成片的开源流水线。

- 豆包理解：视频/音频上传方舟，多模态理解 → 内容概述 + 逐段角色标注 + 带时间戳字幕 + 情绪点。
- 脚本精切：把决策单（删/留区间）转成**剪映草稿**（保留段拼时间轴 + 字幕轨 + 片头封面）。
- 两遍剪映 AI：在剪映 App 内由 Doubao 通过 `mac_computer_use_tool` 操作 GUI 完成粗剪初处理与精修导出。

> 本仓库只含流程代码与文档，**不含任何 API Key、私人视频/字幕、成片或 BGM**。

## 原理

```
视频 ──ffmpeg抽音轨──> 音频 ──豆包音频理解──> 带时间戳字幕(SRT)
视频 ──豆包视频理解──> 内容概述 + 逐段角色标注(核心结果/关键动作/冗余...)
        │
        ▼ 分层决策 + 质量门（结果句强制保护 / 字幕保护）
   剪辑决策单(删/留区间) ──脚本精切──> 剪映草稿(保留段拼轴 + 字幕 + 封面)
        │
        ▼ 剪映 App 内（Doubao 经 mac_computer_use_tool 操作 GUI）
   第一遍剪映AI(智能字幕/初切) ──> 第二遍剪映AI(AI调色/配乐/一键成片) ──> 导出成片
```

## 快速开始

```bash
# 1. 建虚拟环境（避免系统 PEP 668）
python3 -m venv ./_venv && source ./_venv/bin/activate

# 2. 装依赖（已剔除 uiautomation / playwright）
pip install -r requirements.txt

# 3. ffmpeg/ffprobe 需在 PATH（brew install ffmpeg 或放置静态二进制）

# 4. 配置 Key：复制 .env.example 为 .env 并填写 ARK_API_KEY
cp .env.example .env   # 编辑填入你的火山方舟 API Key

# 5. 跑流水线
python scripts/run_pipeline.py --video /path/to/your_video.mov \
    --rule "去口误,去静默,保留高光段,竖屏" --project 我的剪辑

# 无 Key 也可以先用占位数据跑通结构：
python scripts/run_pipeline.py --dry-run
```

## 目录结构

```
ai-jianying-cut/
├── SKILL.md                      # 流程说明书（给 Agent / 协作者）
├── README.md
├── requirements.txt
├── .gitignore  / .env.example
├── scripts/
│   ├── common.py                 # 环境变量 / 输出目录 / 时间码 / 媒体探测
│   ├── ark_client.py             # 火山方舟统一客户端（上传/视频/音频/对话）
│   ├── understand/               # 视频理解、音频转写、角色标注、情绪点
│   ├── plan/                     # 分层决策、字幕保护、质量门
│   ├── cover/                    # 主角识别、封面海报
│   ├── subtitle/                 # SRT → ASS
│   ├── bridge/build_jianying_draft.py  # 决策单 → 剪映草稿（精切核心）
│   └── run_pipeline.py           # 一键编排
├── references/                   # 草稿格式 / 模型 / 两遍剪映AI 说明
├── examples/                     # 示例配置与本地跑法
└── vendor/
    ├── jianying_editor_skill_scripts/   # vendored: jianying-editor-skill v1.7 (MIT)
    │   └── vendor/pyJianYingDraft/       # Apache-2.0 (© GuanYixuan)
    └── NOTICE.md                 # 第三方许可证与出处
```

## 产物（中间文件，默认 `out/`，已被 .gitignore 排除）

- `understand_result.json` 内容概述 + 时间线 + 决策点
- `upload_info.json` 视频 file_id（供复用）
- `transcript.srt` 语音转写字幕
- `roles_result.json` 逐段角色标注
- `compact_result.json` 最终剪辑决策单（删/留）
- `subtitle.ass` 设计样式字幕
- `lead_result.json` 主角出镜时段
- `cover_34.png` / `cover_916.png` 封面海报
- `emotions_result.json` 情绪/事件触发点
- 剪映草稿：落到 `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/<项目名>/`

## 模型

- 视频理解：`doubao-seed-2-1-pro-260628`（支持视频输入）
- 音频理解/转写：`doubao-seed-2-0-lite-260428`
- 模型 ID 因账号开通情况而异，可在火山方舟控制台查看；在 `scripts/ark_client.py` 顶部调整默认值。

## 安全

- API Key 经 `.env` 读取，**不提交**（`.env` 已被 `.gitignore` 排除）。
- 上传到方舟的文件默认仅存储 7 天。
- 本仓库不含任何私人素材、字幕原文、成片或版权 BGM。
- 第三方代码许可证见 `vendor/NOTICE.md`。
