# 第三方代码出处与许可证

本目录 `vendor/jianying_editor_skill_scripts/` 来自开源项目
**[jianying-editor-skill](https://github.com/luoluoluo22/jianying-editor-skill)**（v1.7）。

## 许可证
- **jianying-editor-skill** 整体：**MIT License**，Copyright (c) 2026 luoluoluo22。
- 其内 bundled 的 **pyJianYingDraft**（`vendor/.../vendor/pyJianYingDraft/`）：
  **Apache License, Version 2.0**，Copyright (c) 2024 GuanYixuan
  （见该目录内 `LICENSE`）。

## 引入方式
本仓库直接 vendored 上述 `scripts/` 目录（含 `jy_wrapper.py`、`core/`、`utils/`、`vendor/pyJianYingDraft/`），
作为 `build_jianying_draft.py` 生成剪映草稿的依赖。代码以「原样 + 适配本仓库 import 路径」方式使用，
未修改其授权许可要求；如需升级请同步上游。

## 合规说明
- 本仓库仅 vendored 代码，不含任何视频素材、API Key 或私人数据。
- 使用本仓库即表示你同意遵守上述 MIT 与 Apache-2.0 许可证条款。
