"""
CasperFinder Discord Bot (casperfinder_bot)
캐스퍼 기획전 신규 차량을 감지하여 Discord 채널에 알림을 전송하는 봇.
"""

import asyncio
import logging
import random
from datetime import datetime

import aiohttp
import discord
from discord.ext import tasks

from core.config import load_config, BASE_DIR
from core.api import (
    fetch_exhibition,
    extract_vehicle_id,
    build_detail_url,
)
from core.storage import load_known_vehicles, save_known_vehicles

# ── 로깅 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("CasperFinder")

# ── 설정 로드 ──
config = load_config()
DISCORD_TOKEN = config["discord"]["token"]
INTEGRATED_CHANNEL_ID = int(config["discord"]["integratedChannelId"])
POLL_INTERVAL = 3
STATUS_LOG_CHANNEL_ID = 1471105372755333241  # 상태 보고 채널
GIT_LOG_CHANNEL_ID = 1471131944334000150  # 깃풀 로그 채널
UPDATE_LOG_PATH = "/opt/casperfinder-bot/data/update.log"

# ── 검색 대상 차종 코드 (화이트리스트) ──
# 기획전당 각 코드로 개별 API 호출 후 병합
_TARGET_CAR_CODES = ["AX05", "AX06", "AX03"]
# AX05 = 2026 캐스퍼 일렉트릭
# AX06 = 2026 캐스퍼 (가솔린)
# AX03 = 캐스퍼 일렉트릭 (기존)


def _is_target_vehicle(vehicle):
    """차량이 모니터링 대상 차종인지 판별.

    화이트리스트 방식: _TARGET_CAR_CODES에 포함된 carCode만 허용.
    carCode가 없는 경우 → 허용 (누락 방지)
    """
    car_code = vehicle.get("carCode", "")
    if not car_code:
        return True
    return car_code in _TARGET_CAR_CODES


# ── 차량 필드 추출 헬퍼 (원본 formatter.py에서 이식) ──
def _get(vehicle, *keys, default="-"):
    """차량 객체에서 여러 후보 키로 값 추출."""
    for key in keys:
        val = vehicle.get(key)
        if val is not None and val != "":
            return val
    return default


def _fmt_price(value):
    """가격을 원화 형식으로 포맷."""
    if isinstance(value, (int, float)) and value > 0:
        return f"{int(value):,}원"
    return "-"


def _get_options(vehicle):
    """옵션 이름 목록 추출."""
    option_list = _get(vehicle, "optionList", "options", default=[])
    if not isinstance(option_list, list):
        return []
    names = []
    for opt in option_list:
        if isinstance(opt, dict):
            names.append(_get(opt, "optionName", "optName", "name", default="-"))
        elif isinstance(opt, str):
            names.append(opt)
    return names


# ── Discord Embed 생성 ──
def build_embed(vehicle, label, color_hex):
    """차량 정보를 Discord Embed으로 변환."""
    model = _get(vehicle, "modelNm", "carName")
    trim = _get(vehicle, "trimNm", "trimName")
    ext_color = _get(vehicle, "extCrNm", "exteriorColorName")
    int_color = _get(vehicle, "intCrNm", "interiorColorName")
    center = _get(vehicle, "poName", "deliveryCenterName")
    price = _get(vehicle, "price", "carPrice", default=0)
    discount = _get(vehicle, "discountAmt", "crDscntAmt", default=0)
    options = _get_options(vehicle)

    detail_url = build_detail_url(vehicle)

    opt_text = ", ".join(options) if options else "없음"

    description = (
        f"**모델** {model} / {trim}\n"
        f"**외장** {ext_color}\n"
        f"**내장** {int_color}\n"
        f"**출고** {center}\n"
        f"**가격** {_fmt_price(price)}\n"
        f"**할인** {_fmt_price(discount)}\n"
        f"**옵션** {opt_text}\n\n"
        f"**[구매링크]({detail_url})**"
    )

    color = int(color_hex, 16) if isinstance(color_hex, str) else color_hex

    embed = discord.Embed(
        title=f"{label} — 신규 차량",
        description=description,
        color=color,
        timestamp=datetime.now(),
    )

    return embed


# ── Discord Bot ──
intents = discord.Intents.default()
bot = discord.Client(intents=intents)

known_vehicles = {}
poll_count = 0
last_events = []
last_api_status = {}
last_api_logs = {}


@tasks.loop(seconds=POLL_INTERVAL)
async def poll():
    """주기적으로 각 기획전 API를 호출하고 신규 차량을 감지."""
    global poll_count
    poll_count += 1

    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for target in config["targets"]:
            exhb_no = target["exhbNo"]
            label = target["label"]
            api_config = config["api"]
            headers = api_config["headers"]

            # ── 각 carCode별로 개별 호출 후 병합 (누락 방지) ──
            all_vehicles = []
            total = 0
            last_error = None
            any_success = False
            code_results = []
            all_raw_logs = []

            for car_code in _TARGET_CAR_CODES:
                overrides = dict(target) if target else {}
                overrides["carCode"] = car_code
                try:
                    success, vehicles, cnt, error, raw_log = await fetch_exhibition(
                        session,
                        api_config,
                        exhb_no,
                        target_overrides=overrides,
                        headers_override=headers,
                    )
                    all_raw_logs.append(f"--- {car_code} ---\n{raw_log}")
                    if success:
                        any_success = True
                        all_vehicles.extend(vehicles)
                        total = max(total, cnt)
                        code_results.append(f"{car_code}:{len(vehicles)}대")
                    else:
                        last_error = error
                        code_results.append(f"{car_code}:실패")
                except Exception as e:
                    log.error(f"[{label}] {car_code} API 호출 실패: {e}")
                    code_results.append(f"{car_code}:ERR")
                    all_raw_logs.append(f"--- {car_code} ---\nERROR: {e}")

            last_api_logs[label] = "\n".join(all_raw_logs)

            if not any_success:
                log.warning(f"[{label}] 전체 실패 — {last_error}")
                last_api_status[label] = f"FAIL: {last_error}"
                continue

            # 중복 제거 + 화이트리스트 필터
            current = {}
            for v in all_vehicles:
                if _is_target_vehicle(v):
                    vid = extract_vehicle_id(v)
                    if vid and vid not in current:
                        current[vid] = v

            codes_summary = " | ".join(code_results)
            last_api_status[label] = f"{codes_summary} → {len(current)}대"
            log.info(f"[{label}] {codes_summary} → 합계 {len(current)}대")

            # 초기 실행: 기존 목록 등록만 하고 알림 없음
            if exhb_no not in known_vehicles:
                known_vehicles[exhb_no] = list(current.keys())
                save_known_vehicles(known_vehicles)
                log.info(f"[{label}] 초기화 — {len(current)}대 등록 (total: {total})")
                continue

            # Diff 비교
            prev_ids = set(known_vehicles.get(exhb_no, []))
            new_ids = set(current.keys()) - prev_ids

            if new_ids:
                log.info(f"[{label}] 신규 {len(new_ids)}대 발견!")

                color = target.get("color", "0x3B82F6")
                integrated_ch = bot.get_channel(INTEGRATED_CHANNEL_ID)
                target_ch = bot.get_channel(int(target["channelId"]))

                for vid in new_ids:
                    vehicle = current[vid]
                    embed = build_embed(vehicle, label, color)

                    # 통합 채널 전송
                    if integrated_ch:
                        try:
                            await integrated_ch.send(content="@everyone", embed=embed)
                        except Exception as e:
                            log.error(f"[통합] 메시지 전송 실패: {e}")

                    # 개별 기획전 채널 전송
                    if target_ch:
                        try:
                            await target_ch.send(content="@everyone", embed=embed)
                        except Exception as e:
                            log.error(f"[{label}] 메시지 전송 실패: {e}")

                # 저장
                known_vehicles[exhb_no] = list(current.keys())
                save_known_vehicles(known_vehicles)
                last_events.append(
                    f"{datetime.now().strftime('%H:%M:%S')} [{label}] 신규 {len(new_ids)}대"
                )
            else:
                log.info(f"[{label}] 변경 없음 ({len(current)}대, total: {total})")

    # 랜덤 지터 (3초 + 0~0.99초)
    jitter = random.uniform(0, 0.99)
    await asyncio.sleep(jitter)


@tasks.loop(minutes=5)
async def status_report():
    """5분마다 서버 로그 채널에 상태 요약 전송."""
    log_ch = bot.get_channel(STATUS_LOG_CHANNEL_ID)
    if not log_ch:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 각 기획전 현재 매물 수 + API 상태
    lines = [f"**[상태 보고]** {now}"]
    for target in config["targets"]:
        exhb_no = target["exhbNo"]
        label = target["label"]
        count = len(known_vehicles.get(exhb_no, []))
        api_st = last_api_status.get(label, "-")
        lines.append(f"**{label}** {count}대 | {api_st}")
    lines.append(f"폴링 횟수: {poll_count}회")

    # 최근 이벤트
    if last_events:
        lines.append("\n**최근 이벤트**")
        for ev in last_events[-10:]:
            lines.append(ev)

    try:
        await log_ch.send("\n".join(lines))
    except Exception as e:
        log.error(f"[로그채널] 전송 실패: {e}")

    # 최신 API 로그 (기획전별 개별 코드 블록)
    for label, raw in list(last_api_logs.items()):
        # 메시지 길이 제한(2000자) 대응 및 가독성 개선
        content = raw if len(raw) < 1900 else raw[:1900] + "\n...(중략)"
        msg = f"**[{label} 로그]**\n```json\n{content}\n```"
        try:
            await log_ch.send(msg)
            await asyncio.sleep(1)  # 전송 안정성을 위한 딜레이
        except Exception as e:
            log.error(f"[로그채널] {label} 로그 전송 실패: {e}")


async def check_git_update():
    """업데이트 로그를 확인하여 변경사항이 있으면 디스코드에 보고."""
    import os

    if not os.path.exists(UPDATE_LOG_PATH):
        log.info(f"[Git로그] 로그 파일 없음: {UPDATE_LOG_PATH}")
        return

    try:
        with open(UPDATE_LOG_PATH, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content or "Already up to date." in content:
            return

        log.info(
            f"[Git로그] 새로운 업데이트 로그 발견 (길이: {len(content)}). 전송 시도..."
        )

        # 로그 채널 전송
        try:
            channel = await bot.fetch_channel(GIT_LOG_CHANNEL_ID)
        except Exception as e:
            log.warning(f"[Git로그] fetch_channel 실패, get_channel 시도: {e}")
            channel = bot.get_channel(GIT_LOG_CHANNEL_ID)

        if channel:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 커밋 해시 및 메시지 추출 시도 (git pull 결과 기반)
            commit_hash = "Unknown"
            import subprocess

            try:
                # 현재 최신 커밋 해시와 메시지 가져오기
                commit_hash = (
                    subprocess.check_output(
                        ["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR
                    )
                    .decode()
                    .strip()
                )
                commit_msg = (
                    subprocess.check_output(
                        ["git", "log", "-1", "--pretty=%B"], cwd=BASE_DIR
                    )
                    .decode()
                    .strip()
                )
                display_content = commit_msg if commit_msg else content
            except Exception:
                display_content = content

            # 디스코드 메시지 빌드
            github_url = f"https://github.com/jominki354/CasperFinder_discord/commit/{commit_hash}"

            msg = (
                f"### 🚀 **자동 업데이트 감지** ({now})\n"
                f"**커밋 번호:** [{commit_hash}]({github_url})\n"
                f"```\n{display_content[:1800]}\n```"
            )
            await channel.send(msg)
            log.info("[Git로그] 디스코드 보고 성공.")

            # 읽은 로그 비우기 (중복 방지)
            with open(UPDATE_LOG_PATH, "w", encoding="utf-8") as f:
                f.write("Already up to date. (Reported)")
        else:
            log.error(f"[Git로그] 채널을 찾을 수 없음: {GIT_LOG_CHANNEL_ID}")
    except Exception as e:
        log.error(f"[Git로그] 처리 실패: {e}")


@status_report.before_loop
async def before_status_report():
    await bot.wait_until_ready()


@poll.before_loop
async def before_poll():
    """봇이 ready 상태가 될 때까지 대기."""
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    global known_vehicles
    known_vehicles = load_known_vehicles()
    log.info(f"[casperfinder_bot] 로그인 완료: {bot.user}")
    log.info(
        f"[casperfinder_bot] 감시 대상: {', '.join(t['label'] for t in config['targets'])}"
    )
    log.info(f"[casperfinder_bot] 폴링 간격: ~{POLL_INTERVAL}초 + 랜덤 지터")

    # 업데이트 로그 체크
    await check_git_update()

    poll.start()
    status_report.start()


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
# Auto-update test
# Another test at 22:31
# Final robust test 22:36
# Silent update test
