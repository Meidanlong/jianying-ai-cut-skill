# 剪映草稿格式要点（jianying-editor-skill v1.7）

本项目的 `build_jianying_draft.py` 借助 vendored 的 `jianying-editor-skill` 生成草稿，无需手动拼 JSON。

## 关键事实
- **草稿目录（macOS 自动探测）**：`~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/<项目名>/`
- 一个项目 = 一个文件夹，内含 `draft_info.json`、`draft_meta_info.json`、`draft_settings`、`key_value.json` 与自包含媒体副本（v1.7 媒体丢失修复：源媒体被拷进草稿目录）。
- **macOS 只生成草稿、不能自动导出**（自动导出仅 Windows + 剪映 5.9 及以下）。导出由 Doubao 经 `mac_computer_use_tool` 在剪映 GUI 内完成。

## 画布
- 竖屏：width=1080, height=1920
- 横屏：width=1920, height=1080
- `build_jianying_draft` 默认按源视频方向自动判定。

## 时间轴模型
- 所有时间单位为**微秒**（秒 × 1,000,000）。
- `JyProject.add_clip(media, source_start=秒, duration=秒, target_start=微秒, track_name="VideoTrack")`
  - `source_start`：从源媒体的哪一秒开始取
  - `duration`：取多长（秒）
  - `target_start`：拼到时间轴的哪一微秒
- 字幕用 `add_text_simple(text, start_time=微秒, duration=微秒, track_name="Subtitles")`。

## 为什么"删段"要转成"保留段"
剪映草稿是"往时间轴加 clip"，没有"删除区间"概念。因此本流程对决策单的 `deletes` 取补集得到 `keeps`，逐段 `add_clip`，并把字幕按保留段重映射到目标时间轴。

## 自包含副本的磁盘代价
源视频会被复制进草稿目录（v1.7 行为）。大视频会占用双倍空间，注意磁盘；若要保原画质可后续改为引用外部路径（进阶）。
