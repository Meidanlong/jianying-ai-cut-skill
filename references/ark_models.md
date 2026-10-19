# 火山方舟（豆包）模型与接入

所有调用都经 `scripts/ark_client.py` 统一封装，端点为方舟兼容 OpenAI 的接口：

```
基址: https://ark.cn-beijing.volces.com/api/v3
鉴权: Authorization: Bearer <ARK_API_KEY>  （由脚本注入，Key 只来自 .env）
```

## 默认模型（可在 ark_client.py 顶部覆盖）
| 用途 | 模型 ID | 说明 |
|---|---|---|
| 视频理解 | `doubao-seed-2-1-pro-260628` | 支持视频输入（服务端抽帧+转写） |
| 音频理解/转写 | `doubao-seed-2-0-lite-260428` | 支持音频输入，返回带时间戳 JSON |
| 对话兜底 | `doubao-seed-2-1-pro-260628` | 通用 chat 补全 |

> 模型 ID 因账号开通情况而异，以火山方舟控制台实际可用模型为准。

## 上传与轮询
- 视频上传：`client.files.create(file=..., purpose="user_data", extra_body={"preprocess_configs":{"video":{"fps":0.3}}})`（fps 0.3 控制抽帧密度，省 token）。
- 状态轮询：`files.retrieve` 直到 `status=="active"`。
- file_id 会写入 `out/upload_info.json`，供 `understand_roles.py` / `compact_understand.py` 复用，避免重复上传。

## 配额与费用
- 上传文件默认仅存储 7 天。
- 视频理解按 token/时长计费，抽帧密度越高越贵；口播类建议 fps 0.3~1。

## 安全
- Key **只**从 `.env` 读取，绝不硬编码、绝不进仓库。
- `ark_client.py` 不打印 Key；自检仅确认"Key 已就绪"。
