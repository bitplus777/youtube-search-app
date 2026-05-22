"""로그인 / 회원가입 / 세션 관리"""

import hashlib
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


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


# ── 공개 API ──────────────────────────────────────────────────────────────────
def has_users() -> bool:
    return bool(_load().get("users"))


def register(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if not username or not password:
        return False, "사용자명과 비밀번호를 입력해 주세요."
    data = _load()
    users: list = data.get("users", [])
    if any(u["username"] == username for u in users):
        return False, "이미 존재하는 사용자명입니다."
    users.append({"username": username, "password": _hash(password)})
    data["users"] = users
    _save(data)
    return True, "가입 완료!"


def verify(username: str, password: str) -> bool:
    username = username.strip()
    data = _load()
    for u in data.get("users", []):
        if u["username"] == username and u["password"] == _hash(password):
            return True
    return False


def change_password(username: str, old_pw: str, new_pw: str) -> tuple[bool, str]:
    if not verify(username, old_pw):
        return False, "현재 비밀번호가 틀렸습니다."
    data = _load()
    for u in data.get("users", []):
        if u["username"] == username:
            u["password"] = _hash(new_pw)
            _save(data)
            return True, "비밀번호가 변경되었습니다."
    return False, "사용자를 찾을 수 없습니다."


def load_api_keys() -> list[str]:
    keys = _load().get("api_keys", [])
    return (keys + [""] * 5)[:5]


def save_api_keys(keys: list[str]):
    data = _load()
    data["api_keys"] = [k.strip() for k in keys]
    _save(data)
