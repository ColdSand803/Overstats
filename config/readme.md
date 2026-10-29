# Config

本目录用于存放 `overstats` 的配置加载机制与相关说明。

## 配置加载机制与优先级

`overstats` 的配置已解耦，不再需要在代码中硬编码敏感凭据。支持以下两种配置文件形式：

1. **`.env` 文件（推荐）**：复制项目根目录的 `.env.example` 为 `.env` 并填写。
2. **`config.json` 文件**：复制项目根目录的 `config.example.json` 为 `config.json` 并填写。

### 加载优先级

配置项遵循以下加载优先级（从高到低覆盖）：

1. **操作系统环境变量 / `.env` 文件**（支持直接变量名如 `DASHEN_ROLE_ID`，亦支持 `OVERSTATS_` 前缀如 `OVERSTATS_API_PORT`）
2. **`config.json` 文件**（查找根目录或 `config/` 目录下的 `config.json`，亦可通过环境变量 `OVERSTATS_CONFIG_FILE` 指定路径）
3. **`config.py` 内建默认值**（提供安全的占位与默认配置）

### 敏感配置与版本控制

- `.env` 与 `config.json` 中包含网易大神令牌、API Key 等敏感信息，已在 `.gitignore` 中默认忽略，**切勿提交至公开代码仓库**。
- 仓库提供公开模板：
  - `.env.example`：环境变量模板与详细注释
  - `config.example.json`：JSON 配置结构模板
- 开发者与使用者仅需在本地通过复制模板创建 `.env` 或 `config.json` 即可快速生效。
