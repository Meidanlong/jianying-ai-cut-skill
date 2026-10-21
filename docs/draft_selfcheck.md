# 草稿自检（selfcheck_draft.py）

> 在 `build_jianying_draft.py` 生成草稿后、交给 Doubao 打开剪映**之前**运行。
> 脚本读取**明文** `draft_info.json`（剪映打开后会加密，故必须在打开前跑）。

## 用法
```bash
# 最简：自动推导目标时长（读 plan 的 target_duration_sec 或视频总时长区间）
python scripts/bridge/selfcheck_draft.py <草稿目录>

# 显式指定目标时长窗口（秒）
python scripts/bridge/selfcheck_draft.py <草稿目录> --target 89 --tol 5

# 同时传 plan，校验字幕段是否都在保留段内
python scripts/bridge/selfcheck_draft.py <草稿目录> --plan out/compact_result.json
```

## 断言项（全部 PASS 才退出 0）
| 断言 | 含义 | 失败含义 |
|---|---|---|
| 视频轨数量 == 1 | 单轨首尾相接，无叠层多轨（坑 #1） | 出现并行多轨 |
| 总时长 ∈ [target−tol, target+tol] | 保留段总时长落在目标区间（坑 #6） | 时长超标/过短 |
| 每段音视频对齐偏差 < 50ms | 音频段与对应视频段起止对齐（坑 #4） | 音画不同步 |
| 字幕段全部落在保留段内 | 字幕未被删进删除区间（坑 #14） | 字幕飘在空隙/删除段里 |

## 退出码
- `0`：全部 PASS，可进入导出。
- `1`：存在 FAIL，打印逐项 PASS/FAIL 报告，应阻断导出并回查 `build_jianying_draft.py` / plan。

## 报告样例（节选）
```
[PASS] 视频轨数量 = 1 (期望 1)
[PASS] 总时长 = 89.37s ∈ [84, 94]
[PASS] 音频对齐：最大偏差 0.00s (< 0.05s)
[PASS] 字幕段 6/6 落在保留段内
=> 自检通过 (exit 0)
```

## 与 check_cut.py 的分工
- `selfcheck_draft.py`：结构层（轨道/时长/对齐/字幕落点），对明文草稿。
- `scripts/plan/check_cut.py`：语义层（关键信息句如「中了/赢了」不被误删）。
- 两者组合 = 导出前完整质量门。
