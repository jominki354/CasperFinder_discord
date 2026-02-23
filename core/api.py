"""
API 클라이언트 모듈 (curl_cffi 기반 최적화)
현대 캐스퍼 기획전 API 호출 담당.
TLS Fingerprint 위장을 통해 WAF 우회를 보장합니다.
"""

import json
import logging
import time
import asyncio
from curl_cffi import requests

log = logging.getLogger("CasperFinder")

from core.playwright_refresher import refresher


def build_url(api_config, exhb_no):
    """API 요청 URL 생성 (Cache-Busting 타임스탬프 추가)."""
    ts = int(time.time() * 1000)
    return f"{api_config['baseUrl']}/{exhb_no}?t={ts}"


def build_payload(api_config, exhb_no, target_overrides=None):
    """API 요청 body 생성."""
    payload = {**api_config["defaultPayload"], "exhbNo": exhb_no}
    if target_overrides:
        for key in [
            "carCode",
            "deliveryAreaCode",
            "deliveryLocalAreaCode",
            "subsidyRegion",
            "deliveryCenterCode",
        ]:
            if key in target_overrides:
                payload[key] = target_overrides[key]
    return payload


def parse_response(raw):
    """API 응답 JSON 파싱. (success, vehicles, total, error) 반환."""
    data = raw.get("data", raw)
    rsp = raw.get("rspStatus", {})

    if rsp.get("rspCode") != "0000":
        return False, [], 0, rsp.get("rspMessage", "unknown error")

    vehicles = data.get("list", data.get("discountsearchcars", []))
    total = data.get("totalCount", 0)
    return True, vehicles, total, None


def extract_vehicle_id(vehicle):
    """차량 객체에서 고유 ID 추출."""
    return vehicle.get("vehicleId", vehicle.get("vin", ""))


async def fetch_exhibition(
    session, api_config, exhb_no, target_overrides=None, headers_override=None
):
    """
    단일 기획전 API 호출. (success, vehicles, total, error, raw_log) 반환.
    curl_cffi를 사용하여 브라우저 통신을 완벽히 모방합니다.
    """
    url = build_url(api_config, exhb_no)
    payload = build_payload(api_config, exhb_no, target_overrides)

    # 기본 헤더 설정
    headers = dict(headers_override or api_config.get("headers", {}))
    headers.update(
        {
            "Cache-Control": "no-cache",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://casper.hyundai.com/vehicles/car-list/promotion?exhbNo={exhb_no}",
            "Origin": "https://casper.hyundai.com",
            "User-Agent": refresher.user_agent,
        }
    )

    # 보안 토큰 갱신된 값 적용
    valid_headers = refresher.get_headers()
    headers.update(valid_headers)

    log_lines = []
    log_lines.append(f">>> REQUEST: {url}")
    if "X-UX-State-Key" in headers:
        log_lines.append(f"TOKEN: {headers['X-UX-State-Key']}")

    log.info(f"[API] >>> REQUEST: {url}")

    try:
        # curl_cffi를 사용하여 Chrome 지문 위장 요청 (동기 함수이므로 to_thread 사용)
        resp = await asyncio.to_thread(
            requests.post,
            url=url,
            json=payload,
            headers=headers,
            impersonate="chrome110",
            timeout=20,
        )

        status_code = resp.status_code
        text = resp.text

        log.info(f"[API] <<< RESPONSE Status: {status_code}")
        log_lines.append(f"<<< RESPONSE Status: {status_code}")

        try:
            raw = resp.json()
            body_str = json.dumps(raw, ensure_ascii=False, indent=2)
            log_lines.append(f"BODY: {body_str}")

            # 가짜 성공응답(data가 비어있음) 체크
            if raw.get("rspStatus", {}).get("rspCode") == "0000" and (
                not raw.get("data") or raw.get("data") == {}
            ):
                log.error(
                    "[API] 가짜 응답(Bot Neutralized) 감지됨. TLS 지문 혹은 토큰 확인 필요."
                )
                return (
                    False,
                    [],
                    0,
                    "봇 탐지 패치 (가짜 응답)",
                    "\n".join(log_lines),
                )

        except Exception:
            log.info(f"[API] BODY: (Raw) {text[:500]}")
            log_lines.append(f"BODY: (Raw) {text[:500]}")
            return False, [], 0, "JSON 파싱 실패", "\n".join(log_lines)

        if status_code != 200:
            return False, [], 0, f"HTTP {status_code}", "\n".join(log_lines)

    except Exception as e:
        log.error(f"[API] 요청 에러: {e}")
        log_lines.append(f"ERROR: {type(e).__name__} - {e}")
        return False, [], 0, f"요청 실패: {type(e).__name__}", "\n".join(log_lines)

    result = parse_response(raw)
    return result[0], result[1], result[2], result[3], "\n".join(log_lines)


def build_detail_url(vehicle, exhb_no=""):
    """차량 상세/구매 페이지 URL 생성 (공식 패턴)."""
    yymm = vehicle.get("criterionYearMonth", "") if isinstance(vehicle, dict) else ""
    prod_no = (
        vehicle.get("carProductionNumber", "") if isinstance(vehicle, dict) else ""
    )

    if yymm and prod_no:
        base = "https://casper.hyundai.com/vehicles/car-list/detail"
        url = f"{base}?criterionYearMonth={yymm}&carProductionNumber={prod_no}"
        if exhb_no:
            url += f"&exhbNo={exhb_no}"
        return url

    vid = vehicle.get("vehicleId", vehicle) if isinstance(vehicle, dict) else vehicle
    return f"https://casper.hyundai.com/vehicles/detail?vehicleId={vid}"
