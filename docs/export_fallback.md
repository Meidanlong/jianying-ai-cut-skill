# ffmpeg 直出兜底（export_fallback）

> 当剪映 GUI 导出走不通（卡死 / 多进程混乱 / 不想开 GUI）时，用仓库脚本本地直出成片。
> 适用：已有 `compact_result.json`（保留/删除决策）或 highlights 列表，且源视频/成片可访问。

## 适用场景
- 剪映导出弹窗卡死、重复崩溃（坑 #7）。
- 自动化流程里不希望依赖 Doubao 在 GUI 内点导出。
- 做「无字幕精切版」快速预览（字幕版另走 `scripts/subtitle/build_subtitles.py`）。

## 命令
```bash
python scripts/export/ffmpeg_export.py \
  --plan out/compact_result.json \
  --src  ganzehn_pass1.mp4 \
  --out  ganzehn_v4.mp4
```
- `--plan`：决策单（含 `deletes`，或 `highlights`）。若给 highlights，脚本自动取补集作为删除。
- `--src`：源视频（粗剪版或成片均可，只要时间轴与 plan 一致）。
- `--out`：输出成片。
- `--dry-run`：只打印将要执行的 `filter_complex`，不真正编码（验证参数用）。

## 内部原理
1. 读 plan，把删除区间取补集 → 得到保留段 `[start,end]` 列表（秒）。
2. 对每段用 `trim=start=..:end=..` + `setpts=PTS-STARTPTS` 切视频，`atrim` + `asetpts` 切音频。
3. 用 `concat=n=K:v=1:a=1` 把所有段交错拼接为一条。
4. 编码 `libx264 -b:v 10M -pix_fmt yuv420p` + `aac`，加 `+faststart`。

## 与剪映导出的取舍
- 优点：稳定、可脚本化、可批量、不依赖 GUI。
- 缺点：不带剪映的 AI 调色/配乐/转场；若需要这些，仍走两遍剪映 AI（见 `references/two_pass_jianying_ai.md`）。

## 验证要点
- 输出用 `ffprobe` 确认时长 ≈ 目标、分辨率 1080×1920、含 video+audio 流。
- 抽帧肉眼确认无黑场/跳变（拼接点处时间戳连续）。
