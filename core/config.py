"""
설정 관리 모듈 (Linux 호환)

원본: casperfinder_python/core/config.py
변경 사항:
- Windows %LOCALAPPDATA% 경로 → 프로젝트 내 상대 경로
- Windows 전용 코드 제거
"""

import json
import logging
from pathlib import Path

log = logging.getLogger("CasperFinder")

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
DATA_DIR = BASE_DIR / "data"
KNOWN_VEHICLES_PATH = DATA_DIR / "known_vehicles.json"


def load_json(path, default=None):
    """JSON 파일 로드. 없으면 default 반환."""
    if default is None:
        default = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    """JSON 파일 저장. 디렉토리 자동 생성."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"저장 실패 ({path}): {e}")


def load_config():
    """config.json 로드."""
    if not CONFIG_PATH.exists():
        log.error(f"설정 파일이 없습니다: {CONFIG_PATH}")
        raise FileNotFoundError(f"{CONFIG_PATH}")
    return load_json(CONFIG_PATH)


def save_config(config):
    """config.json 저장."""
    save_json(CONFIG_PATH, config)
