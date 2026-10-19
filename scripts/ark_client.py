#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
火山方舟（豆包）统一客户端。

把各子脚本里重复的「读 ARK_API_KEY / 建 OpenAI 客户端 / 上传文件轮询 / 视频理解 /
音频转写 / 对话」收敛到一处，避免密钥与端点散落。

用法（被其他脚本 import）：
    from ark_client import load_env, get_client, upload_file,
                         video_understand, audio_transcribe, chat

依赖：openai, requests（上传大文件走 REST 更稳，这里统一用 openai SDK 的 files API）。
"""
import json
import os
import sys
import time
from pathlib import Path

# 让本文件既可被直接运行，也可被子脚本 import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_env, ARK_BASE_URL  # noqa: E402

# 默认模型（按账号实际可用模型调整；可在调用时覆盖）
DEFAULT_VIDEO_MODEL = "doubao-seed-2-1-pro-260628"   # 支持视频输入
DEFAULT_AUDIO_MODEL = "doubao-seed-2-0-lite-260428"  # 支持音频输入/转写
DEFAULT_CHAT_MODEL = "doubao-seed-2-1-pro-260628"

_client = None


def load_env_and_key() -> str:
    """加载 .env 并返回 ARK_API_KEY（缺失时抛错，给出友好提示）。"""
    load_env()
    key = os.environ.get("ARK_API_KEY", "")
    if not key:
        raise RuntimeError(
            "未找到 ARK_API_KEY。请在仓库根目录放置 .env（复制 .env.example 填写），"
            "或 export ARK_API_KEY=...。无 Key 时可用 run_pipeline.py --dry-run 跑通结构。"
        )
    return key


def get_client():
    """懒加载、缓存 OpenAI 客户端（指向火山方舟兼容端点）。"""
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(
            api_key=load_env_and_key(),
            base_url=ARK_BASE_URL,
        )
    return _client


def upload_file(path: str, purpose: str = "user_data", preprocess: dict = None) -> str:
    """
    上传本地文件到方舟，轮询直到 active，返回 file_id。
    preprocess 用于视频抽帧控制，如 {"video": {"fps": 0.3}}。
    """
    client = get_client()
    extra = {}
    if preprocess:
        extra["preprocess_configs"] = preprocess
    print(f"[upload] 上传 {Path(path).name} ...")
    with open(path, "rb") as f:
        file = client.files.create(file=f, purpose=purpose, extra_body=extra)
    print(f"[upload]   file_id={file.id} status={file.status}")
    while True:
        file = client.files.retrieve(file.id)
        if file.status != "processing":
            break
        time.sleep(5)
    if file.status != "active":
        raise RuntimeError(f"文件处理失败: {file.status}")
    return file.id


def _responses_text(resp) -> str:
    if hasattr(resp, "output_text"):
        return resp.output_text
    # 兼容 chat.completions 结构
    try:
        return resp.choices[0].message.content
    except Exception:
        return str(resp)


def video_understand(file_id: str, prompt: str, model: str = None) -> str:
    """对视频 file_id 做多模态理解，返回文本。"""
    client = get_client()
    model = model or DEFAULT_VIDEO_MODEL
    resp = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_video", "file_id": file_id},
                {"type": "input_text", "text": prompt},
            ],
        }],
    )
    return _responses_text(resp)


def audio_transcribe(file_id: str, prompt: str, model: str = None) -> str:
    """对音频 file_id 做转写（带时间戳），返回文本（应为 JSON）。"""
    client = get_client()
    model = model or DEFAULT_AUDIO_MODEL
    resp = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_audio", "file_id": file_id},
                {"type": "input_text", "text": prompt},
            ],
        }],
    )
    return _responses_text(resp)


def chat(messages: list, model: str = None) -> str:
    """通用对话补全（messages 形如 [{"role","content"}]）。"""
    client = get_client()
    model = model or DEFAULT_CHAT_MODEL
    resp = client.chat.completions.create(model=model, messages=messages)
    return resp.choices[0].message.content


if __name__ == "__main__":
    # 自检：打印客户端是否就位（不泄露 key）
    try:
        load_env_and_key()
        print("ARK_API_KEY 已就绪；client 延迟到首次调用时创建。")
    except RuntimeError as e:
        print(f"自检失败: {e}")
