from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# ==============================================================================
# 配置文件与环境变量加载引擎
# 优先级: 操作系统环境变量 / .env 文件 > config.json 配置文件 > 代码默认值
# ==============================================================================

_CONFIG_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CONFIG_DIR.parent


def _load_env_file(env_path: Path) -> None:
    """加载 .env 文件中的键值对到 os.environ 中（不覆盖已存在的环境变量）。"""
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path, override=False)
        return
    except ImportError:
        pass

    # 若未安装 python-dotenv，使用轻量内建解析器作为降级备选
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


def _find_json_config_path() -> Optional[Path]:
    """寻找 JSON 配置文件路径。"""
    env_cfg = os.getenv("OVERSTATS_CONFIG_FILE") or os.getenv("CONFIG_FILE")
    if env_cfg:
        p = Path(env_cfg)
        return p if p.is_file() else None

    candidates = [
        _PROJECT_ROOT / "config.json",
        _CONFIG_DIR / "config.json",
        _PROJECT_ROOT / "config.local.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _load_json_config() -> Dict[str, Any]:
    """读取 JSON 配置文件内容。"""
    path = _find_json_config_path()
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as exc:
        print(f"[overstats] 警告: 读取配置文件 {path} 失败: {exc}")
    return {}


# ----------------- 默认人设提示词 -----------------
_DEFAULT_PERSONA_PROMPT = """
【核心原则】
请保持绝对客观中立，拒绝阿谀奉承！不要因为查询指令的是焦点玩家就一味夸奖，如果焦点玩家表现平庸或拉垮请直接批评。

【人格设定】
你的说话人设是科比·布莱恩特，风格包含 [man! what can i say，mamba out] 等 meme。
""".strip()


def _get_raw(json_cfg: Dict[str, Any], key: str, default: Any = None) -> Any:
    """获取原始配置值：优先查找 os.environ (KEY 或 OVERSTATS_KEY)，然后查找 json_cfg，最后返回 default。"""
    if key in os.environ:
        return os.environ[key]
    overstats_key = f"OVERSTATS_{key}"
    if overstats_key in os.environ:
        return os.environ[overstats_key]
    if key in json_cfg:
        return json_cfg[key]
    for k, v in json_cfg.items():
        if k.lower() == key.lower():
            return v
    return default


def _get_str(json_cfg: Dict[str, Any], key: str, default: str) -> str:
    val = _get_raw(json_cfg, key, default)
    if val is None:
        return default
    return str(val)


def _get_int(json_cfg: Dict[str, Any], key: str, default: int) -> int:
    val = _get_raw(json_cfg, key, default)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _get_float(json_cfg: Dict[str, Any], key: str, default: float) -> float:
    val = _get_raw(json_cfg, key, default)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _get_bool(json_cfg: Dict[str, Any], key: str, default: bool) -> bool:
    val = _get_raw(json_cfg, key, default)
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        normalized = val.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off"):
            return False
    return default


def _resolve_accounts(json_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    # 1. 环境变量 DASHEN_ACCOUNTS 或 OVERSTATS_DASHEN_ACCOUNTS (JSON 格式)
    raw_env = os.getenv("DASHEN_ACCOUNTS") or os.getenv("OVERSTATS_DASHEN_ACCOUNTS")
    if raw_env:
        try:
            parsed = json.loads(raw_env)
            if isinstance(parsed, list) and parsed:
                return parsed
        except Exception:
            pass

    # 2. 环境变量中的单账号快捷配置 (DASHEN_ROLE_ID + DASHEN_TOKEN 或 OVERSTATS_DASHEN_*)
    role_id = os.getenv("DASHEN_ROLE_ID") or os.getenv("OVERSTATS_DASHEN_ROLE_ID")
    token = os.getenv("DASHEN_TOKEN") or os.getenv("OVERSTATS_DASHEN_TOKEN")
    if role_id and token:
        try:
            return [{
                "name": (os.getenv("DASHEN_ACCOUNT_NAME") or "primary").strip(),
                "role_id": int(str(role_id).strip()),
                "token": str(token).strip(),
            }]
        except (ValueError, TypeError):
            pass

    # 3. JSON 配置文件中的 DASHEN_ACCOUNTS 列表
    if "DASHEN_ACCOUNTS" in json_cfg and isinstance(json_cfg["DASHEN_ACCOUNTS"], list) and json_cfg["DASHEN_ACCOUNTS"]:
        return json_cfg["DASHEN_ACCOUNTS"]
    # 4. JSON 中的单账号快捷配置
    if "DASHEN_ROLE_ID" in json_cfg and "DASHEN_TOKEN" in json_cfg:
        try:
            return [{
                "name": str(json_cfg.get("DASHEN_ACCOUNT_NAME") or "primary").strip(),
                "role_id": int(json_cfg["DASHEN_ROLE_ID"]),
                "token": str(json_cfg["DASHEN_TOKEN"]).strip(),
            }]
        except (ValueError, TypeError):
            pass

    # 5. 未配置时的安全占位默认值
    return [
        {
            "name": "account-1",
            "role_id": 123456789,
            "token": "replace-with-your-token",
        }
    ]


def _resolve_netease_proxies(json_cfg: Dict[str, Any]) -> List[Optional[str]]:
    raw = _get_raw(json_cfg, "DASHEN_NETEASE_PROXIES", None)
    if raw is None:
        return [None]
    if isinstance(raw, list):
        return raw if raw else [None]
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return [None]
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
        proxies = [p.strip() for p in raw.split(",") if p.strip()]
        return proxies if proxies else [None]
    return [None]


def _resolve_asset_warmup(json_cfg: Dict[str, Any]) -> bool:
    if os.getenv("OVERSTATS_DISABLE_ASSET_WARMUP") == "1":
        return False
    return _get_bool(json_cfg, "ENABLE_ASSET_WARMUP", False)


def _resolve_max_accepted_requests(json_cfg: Dict[str, Any], accounts: List[Dict[str, Any]]) -> int:
    val = _get_raw(json_cfg, "DASHEN_MAX_ACCEPTED_REQUESTS", None)
    if val is not None and str(val).strip() != "":
        try:
            return max(1, int(val))
        except (ValueError, TypeError):
            pass
    return max(len(accounts) * 4, 1)


# ==============================================================================
# 配置加载与全局导出
# ==============================================================================
def load_all_configs() -> Dict[str, Any]:
    # 查找并按顺序加载 .env
    for candidate in (_PROJECT_ROOT / ".env", _CONFIG_DIR / ".env", Path.cwd() / ".env"):
        if candidate.is_file():
            _load_env_file(candidate)
            break

    json_cfg = _load_json_config()
    accounts = _resolve_accounts(json_cfg)

    return {
        # Core Service
        "API_HOST": _get_str(json_cfg, "API_HOST", "127.0.0.1"),
        "API_PORT": _get_int(json_cfg, "API_PORT", 18080),
        "USE_STREAM_RESPONSE": _get_bool(json_cfg, "USE_STREAM_RESPONSE", True),
        "ENABLE_DATABASE_WRITE": _get_bool(json_cfg, "ENABLE_DATABASE_WRITE", True),
        "SHOW_DASHEN_PROMO": _get_bool(json_cfg, "SHOW_DASHEN_PROMO", False),
        "HERO_MODULE_MODE": _get_int(json_cfg, "HERO_MODULE_MODE", 0),
        "ENABLE_ASSET_WARMUP": _resolve_asset_warmup(json_cfg),

        # Dashen Upstream
        "DASHEN_ACCOUNTS": accounts,
        "DASHEN_DTS": _get_int(json_cfg, "DASHEN_DTS", 2026),
        "DASHEN_SERVER": _get_int(json_cfg, "DASHEN_SERVER", 1),
        "DASHEN_ACCOUNT_MAX_REQUESTS_PER_SECOND": _get_int(json_cfg, "DASHEN_ACCOUNT_MAX_REQUESTS_PER_SECOND", 5),
        "DASHEN_ACCOUNT_RATE_LIMIT_WINDOW_SECONDS": _get_float(json_cfg, "DASHEN_ACCOUNT_RATE_LIMIT_WINDOW_SECONDS", 1.0),
        "DASHEN_CLIENT_TYPE": _get_str(json_cfg, "DASHEN_CLIENT_TYPE", "60"),
        "DASHEN_ORIGIN": _get_str(json_cfg, "DASHEN_ORIGIN", "https://act.ds.163.com"),
        "DASHEN_REFERER": _get_str(json_cfg, "DASHEN_REFERER", "https://act.ds.163.com/"),
        "DASHEN_USER_AGENT": _get_str(
            json_cfg,
            "DASHEN_USER_AGENT",
            (
                "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 "
                "app/df_client dfVersion/100111"
            ),
        ),
        "DASHEN_ACCOUNT_FAILURE_COOLDOWN_SECONDS": _get_int(json_cfg, "DASHEN_ACCOUNT_FAILURE_COOLDOWN_SECONDS", 60),
        "DASHEN_MAX_CONCURRENT_REQUESTS": _get_int(json_cfg, "DASHEN_MAX_CONCURRENT_REQUESTS", 2),
        "DASHEN_MAX_ACCEPTED_REQUESTS": _resolve_max_accepted_requests(json_cfg, accounts),
        "DASHEN_INTERNATIONAL_PROXY": _get_str(json_cfg, "DASHEN_INTERNATIONAL_PROXY", ""),
        "DASHEN_NETEASE_PROXIES": _resolve_netease_proxies(json_cfg),

        # External APIs & Assets
        "OW_ESPORTS_API_KEY": _get_str(json_cfg, "OW_ESPORTS_API_KEY", ""),
        "OW_GUESS_ASSET_ROOT": _get_str(json_cfg, "OW_GUESS_ASSET_ROOT", "ow_guess_assets"),

        # Seasons
        "DASHEN_CURRENT_SEASON": _get_int(json_cfg, "DASHEN_CURRENT_SEASON", 25),
        "DASHEN_HISTORY_START_SEASON": _get_int(json_cfg, "DASHEN_HISTORY_START_SEASON", 15),
        "OW_HERO_LEADERBOARD_CN_SEASON": _get_int(json_cfg, "OW_HERO_LEADERBOARD_CN_SEASON", 5),

        # Match Analysis
        "ANALYSIS_BASE_URL": _get_str(json_cfg, "ANALYSIS_BASE_URL", ""),
        "ANALYSIS_API_KEY": _get_str(json_cfg, "ANALYSIS_API_KEY", "replace-with-your-analysis-api-key"),
        "ANALYSIS_PROXY": _get_str(json_cfg, "ANALYSIS_PROXY", ""),
        "ANALYSIS_GOOGLE_MODEL": _get_str(json_cfg, "ANALYSIS_GOOGLE_MODEL", ""),
        "ANALYSIS_DEEPSEEK_MODEL": _get_str(json_cfg, "ANALYSIS_DEEPSEEK_MODEL", ""),
        "ANALYSIS_OPENAI_MODEL": _get_str(json_cfg, "ANALYSIS_OPENAI_MODEL", ""),

        # Patch Notes
        "PATCH_NOTES_USE_INTERNATIONAL_PROXY": _get_bool(json_cfg, "PATCH_NOTES_USE_INTERNATIONAL_PROXY", False),
        "PATCH_NOTES_INTERNATIONAL_PROXY": _get_str(json_cfg, "PATCH_NOTES_INTERNATIONAL_PROXY", ""),

        # Persona
        "ANALYSIS_PERSONA_PROMPT": _get_str(json_cfg, "ANALYSIS_PERSONA_PROMPT", _DEFAULT_PERSONA_PROMPT),
    }


def reload_config() -> None:
    """重新载入配置文件并刷新当前模块导出的全局变量。"""
    cfg = load_all_configs()
    globals().update(cfg)


# 初次导入时自动载入所有配置项
_INITIAL_CFG = load_all_configs()
globals().update(_INITIAL_CFG)
