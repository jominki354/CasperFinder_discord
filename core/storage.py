"""
데이터 저장 모듈
known_vehicles.json 관리.

원본: casperfinder_python/core/storage.py
변경 사항: 경로만 변경 (data/ 디렉토리 사용)
"""

from core.config import KNOWN_VEHICLES_PATH, load_json, save_json


def load_known_vehicles():
    """기존에 확인된 vehicleId 목록 로드."""
    return load_json(KNOWN_VEHICLES_PATH, {})


def save_known_vehicles(data):
    """vehicleId 목록 저장."""
    save_json(KNOWN_VEHICLES_PATH, data)


def reset_known_vehicles():
    """vehicleId 데이터 초기화 (파일 삭제)."""
    if KNOWN_VEHICLES_PATH.exists():
        import os

        os.remove(KNOWN_VEHICLES_PATH)
