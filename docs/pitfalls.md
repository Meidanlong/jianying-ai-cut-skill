# 踩坑复盘（实测经验）

> 来源：干蒸探店实测（8 段素材 → 粗剪 → 精切 → 字幕）全流程跑通后沉淀。
> 每条经验格式：**现象 → 原因 → 正确做法**。文末附经验总索引。
> GUI 类坑（SVIP 按钮、cu 多进程、重启弹窗）详见 `references/two_pass_jianying_ai.md`。

---

## 流程坑

### #1 视频素材必须单轨首尾相接，不能并行叠成多轨
- **现象**：曾出现「9 条视频轨、每轨 1 个 clip」，剪映里层层叠在一起。
- **原因**：上层代码对每一段保留区间各开了一条新轨（如 `VideoTrack_1/2/3…`）；pyJianYingDraft 库**本身不会自动分轨**，遇到重叠只会抛 `SegmentOverlap` 异常。
- **正确做法**：所有保留段固定用**同一个轨名**（如 `VideoTrack`），`_ensure_track` 同名只建一次 → 最终 1 条视频轨、N 个 clip 首尾相接。单轨不变量由 `scripts/bridge/selfcheck_draft.py` 断言（视频轨数 == 1）。

### #3 生成草稿后、剪映打开前必须先读明文自检
- **现象**：草稿被剪映打开一次后，`draft_info.json` 被加密（开头是 `gg20soWc…` 而非 `{`），无法再解析。
- **原因**：剪映对草稿有「打开即加密」行为，明文只存在于首次打开前。
- **正确做法**：`build_jianying_draft.py` 落盘后、交给 Doubao 开剪映前，立即跑 `python scripts/bridge/selfcheck_draft.py <草稿目录> --target <秒>` 读明文做结构自检。自检不过不要进导出。

### #4 音频必须与视频保留段逐段对齐，否则音画不同步、字幕错位
- **现象**：早期版本只有视频轨有内容，音频由剪映自动抽全片 → 音画错位；或音频段整体偏移。
- **原因**：`pyJianYingDraft` 的 `VideoSegment` 只带画面不带声音；若直接把含视频轨的 `.mov` 喂给 `AudioMaterial`，会因「含视频流」被拒、静默丢段。
- **正确做法**：视频轨 `volume=0`（静音），另用 `add_audio_safe` 为每段保留区间生成**独立纯音频**（抽离 `.m4a`），`source_timerange` 与视频段一一对应；同源文件抽一次缓存，避免重复解封装大文件。

### #5 画布方向要按素材自适应，禁止硬编码横屏
- **现象**：竖屏 1080×1920 素材被压成 1920×1080 横屏 → 黑边 + 画面居中变小。
- **原因**：早期 `media_normalizer.py` 写死 `scale=1920:1080`。
- **正确做法**：按 `h>w` 判竖屏→`1080:1920`、横屏→`1920:1080`；合法竖屏 1080×1920 不再被强制重编码。归一化触发条件放宽到「仅 codec/pix_fmt 不兼容才重编码」。

### #6 保留段应取 highlights 补集，不要直接拿 redundant 当删除区间
- **现象**：模型给的 `redundant` 列表漏标了若干 ~1s 边界缝隙，直接用 `redundant` 当 deletes 会让保留量 = 总时长 − redundant 总和，超出目标上限。
- **原因**：模型把高光与冗余之间的过渡帧既没标高光也没标冗余，留了「未覆盖缝隙」。
- **正确做法**：保留段 = **highlights 本身**；deletes = highlights 的补集（见 `scripts/plan/build_plan.py`）。这样保留时长精确等于 highlights 合计，杜绝缝隙导致的时长超标。

### #7 剪映 GUI 卡死时，用 ffmpeg 直出兜底成片
- **现象**：剪映导出弹窗卡死 / 多进程混乱，GUI 导出走不通。
- **原因**：macOS 上 jianying-editor-skill 不能自动导出，强依赖 Doubao 在 GUI 内点导出。
- **正确做法**：`python scripts/export/ffmpeg_export.py --plan out/compact_result.json --src <成片或源视频> --out final.mp4`，本地 `filter_complex` 逐段 trim/atrim→concat，H.264+AAC。详见 `docs/export_fallback.md`。

### #10 字幕时间轴必须对齐最终成片本身
- **现象**：用旧版粗剪（`pass1`）的 `transcript.srt` 给精剪后成片烧字幕，字幕整体错位。
- **原因**：成片经过精切/重拼，时间轴已变，旧 srt 不再对应。
- **正确做法**：成片出来后**重新抽音轨 → 重新 ASR**（`audio_to_srt.py`）生成对齐成片时间轴的 srt。一键编排见 `scripts/subtitle/build_subtitles.py`。

---

## 字幕坑

### #11 ASR 专有名词/粤语口语会谐音错，需词表 + 人工复核
- **现象**：店名「鑫粤福」被写成「新悦福」，菜品「瑶柱」被写成「摇什么」。
- **原因**：豆包 ASR 对专有名词、方言词按谐音猜测，必然出错。
- **正确做法**：维护 `scripts/subtitle/corrections.json` 错词→正词映射；`apply_corrections.py` 替换已知错词并产出 `review_checklist.md` 列出「未命中 / 待人工确认」句（如语义存疑的「这边是蒸炒」）。**注意粤语口语保护**：如「胜瓜」是粤语里「丝瓜」的正确叫法，不要误改成普通话；这类词应进 corrections 的 `protect` 列表而非 `fix`。

---

## 工程 / 隐私坑

### #13 公开仓库严禁提交密钥 / 绝对个人路径 / 工作邮箱
- **现象**：早期脚本里写死 `/Users/yourname/...` 绝对路径；`.env` 含真实 `ARK_API_KEY`。
- **原因**：个人工作目录与密钥不该进公开库。
- **正确做法**：`.gitignore` 已排除 `.env`、`out/`、`*.mp4/*.mov`、`draft_info.json`；脚本内**禁止硬编码绝对路径**，一律从命令行参数或 `config` 读取（见 `understand_highlights*.py` 的 `DEFAULT_VIDEO` 改相对名）。提交前按 `docs/pitfalls.md` 末的隐私清单 grep 一遍。

### #14 导出前要有自动化自检，自检不过不进导出
- **现象**：草稿看似生成成功，实际视频多轨 / 时长超标 / 字幕飘在删除段里。
- **原因**：缺少结构校验，问题到剪映里才暴露。
- **正确做法**：`python scripts/bridge/selfcheck_draft.py <草稿目录> --target <秒>` 作为质量门：视频轨==1、总时长∈目标区间、每段音视频对齐偏差<50ms、字幕段全部落在保留段内。另已有 `scripts/plan/check_cut.py` 校验「关键信息句不被删」。两者组合覆盖结构与语义两层。

---

## GUI 类（详见 references/two_pass_jianying_ai.md）
- **#2** SVIP 小按钮（如智能粗剪删除钮）AX 坐标定位不准点不中 → 用 `cmd+E` 打开导出框 + 回车确认绕过。
- **#8** `mac_computer_use_tool` 操作剪映时多进程并存（主进程 / TrayHelper / 子进程），必须指定 `pid`；剪映重启后 pid 会变，需先 `list_apps` 重新解析。
- **#9** 剪映重启会依次弹「联合会员 / 版本更新 / 通知提示」三个窗，自动化流程须加关闭步骤。

---

## 经验总索引

| # | 类别 | 一句话 | 落点 |
|---|---|---|---|
| 1 | 流程 | 素材单轨首尾相接，禁并行多轨 | selfcheck 断言 + pitfalls #1 |
| 2 | GUI | SVIP 小按钮点不中→cmd+E 绕过 | references/two_pass |
| 3 | 流程 | 剪映打开前先读明文自检 | selfcheck_draft.py + pitfalls #3 |
| 4 | 流程 | 音频逐段对齐视频 | media_ops（vendor 补丁）+ pitfalls #4 |
| 5 | 流程 | 画布方向自适应，禁硬编码横屏 | media_normalizer（vendor 补丁） |
| 6 | 流程 | 保留段取 highlights 补集 | build_plan.py + pitfalls #6 |
| 7 | 流程 | GUI 卡死用 ffmpeg 直出兜底 | ffmpeg_export.py + export_fallback.md |
| 8 | GUI | cu 多进程须指定 pid，重启重解析 | references/two_pass |
| 9 | GUI | 剪映重启三窗须关闭 | references/two_pass |
| 10 | 字幕 | 字幕时间轴对齐最终成片（重抽音再 ASR） | build_subtitles.py + pitfalls #10 |
| 11 | 字幕 | ASR 专名/粤语谐音错 → 词表+复核 | corrections.json + apply_corrections.py |
| 12 | 字幕 | 竖屏字幕样式规范 | srt_to_ass.py + subtitle_spec.md |
| 13 | 工程 | 禁提交 key/绝对路径/邮箱 | .gitignore + 隐私清单 |
| 14 | 工程 | 导出前自动化自检 | selfcheck_draft.py + check_cut.py |
