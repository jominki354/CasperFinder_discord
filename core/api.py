"""
API 클라이언트 모듈
현대 캐스퍼 기획전 API 호출 담당.

원본: casperfinder_python/core/api.py
변경 사항: 없음 (그대로 이식)
"""

import json
import logging
import aiohttp
import asyncio

log = logging.getLogger("CasperFinder")


def build_url(api_config, exhb_no):
    """API 요청 URL 생성."""
    return f"{api_config['baseUrl']}/{exhb_no}"


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
    """단일 기획전 API 호출. (success, vehicles, total, error, raw_log) 반환."""
    url = build_url(api_config, exhb_no)
    payload = build_payload(api_config, exhb_no, target_overrides)
    headers = headers_override or api_config.get("headers")

    log_lines = []
    log_lines.append(f">>> REQUEST: {url}")
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


def build_detail_url(vehicle_id):
    """차량 상세/구매 페이지 URL 생성."""
    return f"https://casper.hyundai.com/vehicles/detail?vehicleId={vehicle_id}"
