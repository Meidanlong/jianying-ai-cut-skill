# 竖屏字幕样式规范（1080×1920）

> 烧录脚本统一用 `scripts/subtitle/srt_to_ass.py` 生成 ASS，再用 ffmpeg `ass` 滤镜烧录。
> 本规范是样式基线，所有成片字幕应保持一致观感。

## 设计目标
- 白字黑描边，强光/复杂背景下都清晰可读。
- 底部安全区，不贴最底边、不挡人脸。
- 长句自动折行，单行不超画面宽度的合理比例。
- 字号适配竖屏，远看清楚、近看不笨重。

## 推荐参数（已固化进 srt_to_ass.py 默认值）

| 项 | 值 | 说明 |
|---|---|---|
| PlayRes | 1080 × 1920 | 竖屏坐标系，字号按比例计算 |
| Fontname | `STHeiti`（或 `PingFang SC`） | 必须含中文字形；无中文会出方框/豆腐块 |
| Fontsize | 80 | 竖屏 1080 基准；约 13 个全角字/行 |
| PrimaryColour | `&H00FFFFFF` | 纯白字（AA=00 不透明） |
| OutlineColour | `&H00000000` | 黑色描边 |
| BackColour | `&H96000000` | 半透明黑底阴影（AA=96） |
| Outline / Shadow | 5 / 2 | 描边粗细 + 阴影偏移 |
| Bold | 1 | 加粗提升可读性 |
| Alignment | 2 | 底部居中 |
| MarginV | 170 | 底部安全边距（约画面高 9%） |
| MarginL / MarginR | 160 | 左右留白，避免贴边 |
| WrapStyle | 3 | 智能折行 |
| ScaledBorderAndShadow | yes | 缩放时描边/阴影同步 |

## 折行规则（srt_to_ass.py 内置）
- 以「全角≈1、半角≈0.6」估算显示宽度，`max_chars ≈ (1080 − MarginL − MarginR) / Fontsize`。
- 超过 `max_chars` 处插入硬换行 `\N`，保证单行不超画面宽。

## 自检清单
- [ ] 字幕在 1080×1920 预览下不超出左右边界。
- [ ] 底部字幕距画面底边 ≥ 约 8%~10%（MarginV≈170/1920）。
- [ ] 人脸/主体未被字幕遮挡（竖屏人物偏中下时尤其注意）。
- [ ] 长句已折行，无单行溢出。
- [ ] 渲染后无方框（字体含中文；必要时换 `Fontname`）。

## 烧录命令示例
```bash
python scripts/subtitle/srt_to_ass.py in.srt out.ass --fontname STHeiti --fontsize 80 --marginv 170
ffmpeg -i final.mp4 -vf "ass=out.ass" -c:v libx264 -b:v 10M -pix_fmt yuv420p -c:a copy final_sub.mp4
```
