"""인증 - Google OAuth + API 키 관리 (이메일 별 저장)"""

import json
from pathlib import Path

_KEYS_FILE = Path(__file__).parent / "keys.json"


def _load() -> dict:
    try:
        return json.loads(_KEYS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict):
    _KEYS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Google OAuth 사용자 등록/조회 ──────────────────────────────────────────────
def ensure_google_user(email: str, display_name: str = "") -> None:
    """Google 로그인 시 사용자 레코드가 없으면 자동 생성."""
    data = _load()
    users: dict = data.get("google_users", {})
    if email not in users:
        users[email] = {"display_name": display_name, "api_keys": []}
    elif display_name and not users[email].get("display_name"):
        users[email]["display_name"] = display_name
    data["google_users"] = users
    _save(data)


def get_display_name(email: str) -> str:
    data = _load()
    return data.get("google_users", {}).get(email, {}).get("display_name", email)


# ── API 키 관리 (이메일 기반) ──────────────────────────────────────────────────
def load_api_keys(email: str = "default") -> list[str]:
    data = _load()
    # 신규 구조: google_users[email]["api_keys"]
    if email in data.get("google_users", {}):
        keys = data["google_users"][email].get("api_keys", [])
    else:
        # 구버전 호환 (비밀번호 로그인 사용자)
        keys = data.get("api_keys", [])
    return (keys + [""] * 5)[:5]


def save_api_keys(keys: list[str], email: str = "default"):
    data = _load()
    clean = [k.strip() for k in keys]
    if email in data.get("google_users", {}):
        data["google_users"][email]["api_keys"] = clean
    else:
        data["api_keys"] = clean
    _save(data)
