"""
API 클라이언트 모듈
현대 캐스퍼 기획전 API 호출 담당.

원본: casperfinder_python/core/api.py
변경 사항: 없음 (그대로 이식)
"""

import json
import logging
import time
import aiohttp
import asyncio

log = logging.getLogger("CasperFinder")


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


async def get_layout_hash(session, headers_base):
    """봇 탐지 우회를 위한 동적 레이아웃 해시(X-UX-State-Key) 획득.

    서버의 토큰 재사용 감지를 피하기 위해 캐싱 없이 매번 새로 요청함.
    """
    sync_url = "https://casper.hyundai.com/gw/wp/common/v2/common/ui/layout-sync"
    try:
        async with session.get(sync_url, headers=headers_base, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.json()
                h = data.get("data", {}).get("layoutHash")
                if h:
                    return h
    except Exception as e:
        log.error(f"[API] 레이아웃 해시 획득 실패: {e}")
    return None


async def fetch_exhibition(
    session, api_config, exhb_no, target_overrides=None, headers_override=None
):
    """단일 기획전 API 호출. (success, vehicles, total, error, raw_log) 반환."""
    url = build_url(api_config, exhb_no)
    payload = build_payload(api_config, exhb_no, target_overrides)

    # 헤더 복사 및 최신 우회 로직 적용
    headers = dict(headers_override or api_config.get("headers", {}))
    headers.update(
        {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://casper.hyundai.com/vehicles/car-list/promotion?exhbNo={exhb_no}",
        }
    )

    # 봇 탐지 우회 토큰 획득
    layout_hash = await get_layout_hash(session, headers)
    if layout_hash:
        headers["X-UX-State-Key"] = layout_hash

    log_lines = []
    log_lines.append(f">>> REQUEST: {url}")
    if layout_hash:
        log_lines.append(f"TOKEN: {layout_hash}")
    log_lines.append(f"PAYLOAD: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    log.info(f"[API] >>> REQUEST: {url}")
    log.info(f"[API] PAYLOAD: {json.dumps(payload, ensure_ascii=False)}")

    try:
        async with session.post(url, json=payload, headers=headers) as resp:
            status_code = resp.status
            text = await resp.text()

            log.info(f"[API] <<< RESPONSE Status: {status_code}")
            log_lines.append(f"<<< RESPONSE Status: {status_code}")

            try:
                raw = json.loads(text)
                body_str = json.dumps(raw, ensure_ascii=False, indent=2)
                log.info(f"[API] BODY: {json.dumps(raw, ensure_ascii=False)}")
                log_lines.append(f"BODY: {body_str}")

                # 가짜 성공응답(data가 아예 비어있음) 체크
                if raw.get("rspStatus", {}).get("rspCode") == "0000" and not raw.get(
                    "data"
                ):
                    log.error("[API] 가짜 응답(Bot Neutralized) 감지됨. 데이터 유실.")
                    return (
                        False,
                        [],
                        0,
                        "봇 탐지 패치 (가짜 응답)",
                        "\n".join(log_lines),
                    )

            except json.JSONDecodeError:
                log.info(f"[API] BODY: (Raw) {text[:500]}")
                log_lines.append(f"BODY: (Raw) {text[:500]}")
                return False, [], 0, "JSON 파싱 실패", "\n".join(log_lines)

            if status_code != 200:
                return False, [], 0, f"HTTP {status_code}", "\n".join(log_lines)

    except aiohttp.ClientError as e:
        log_lines.append(f"ERROR: {type(e).__name__}")
        return False, [], 0, f"요청 실패: {type(e).__name__}", "\n".join(log_lines)
    except asyncio.TimeoutError:
        log_lines.append("ERROR: 타임아웃")
        return False, [], 0, "타임아웃", "\n".join(log_lines)

    result = parse_response(raw)
    return result[0], result[1], result[2], result[3], "\n".join(log_lines)


def build_detail_url(vehicle, exhb_no=""):
    """차량 상세/구매 페이지 URL 생성 (공식 패턴).

    우선순위:
    1. criterionYearMonth + carProductionNumber → 공식 리스트 상세 페이지
    2. vehicleId → 간편 상세 페이지 (폴백)
    """
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

    # 폴백: vehicleId 기반
    vid = vehicle.get("vehicleId", vehicle) if isinstance(vehicle, dict) else vehicle
    return f"https://casper.hyundai.com/vehicles/detail?vehicleId={vid}"
