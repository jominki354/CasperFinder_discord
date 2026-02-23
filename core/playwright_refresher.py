import logging
import asyncio
import time
from curl_cffi import requests

log = logging.getLogger("CasperFinder")


class TokenRefresher:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.cookies = ""
        self.ux_state_key = ""
        self.last_refresh_time = 0
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    async def _fetch_with_impersonate(self, url, method="GET", json_data=None):
        """curl_cffi를 사용하여 브라우저 지문을 모방하며 요청을 보냅니다."""
        try:
            # impersonate="chrome" 옵션이 핵심 (JA3 지문 우회)
            resp = await asyncio.to_thread(
                requests.request,
                method=method,
                url=url,
                json=json_data,
                impersonate="chrome110",  # 최신 지문 사용
                headers={
                    "User-Agent": self.user_agent,
                    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                },
                timeout=15,
            )
            return resp
        except Exception as e:
            log.error(f"[Refresher] curl_cffi 요청 중 에러: {e}")
            return None

    async def refresh_tokens(self, force=False):
        """
        curl_cffi를 사용하여 layout-sync API에서 layoutHash를 추출하고
        보안 쿠키를 획득합니다.
        """
        async with self.lock:
            now = time.time()
            if not force and (now - self.last_refresh_time) < 1200:
                return True

            log.info("[Refresher] 🚀 curl_cffi 기반 경량 토큰 갱신 시작...")

            # 1. 메인 접속하여 기본 쿠키 확보
            resp_main = await self._fetch_with_impersonate("https://casper.hyundai.com")
            if not resp_main:
                log.error("[Refresher] 메인 페이지 접속 실패")
                return False

            # 응답 쿠키 저장
            self.cookies = "; ".join([f"{k}={v}" for k, v in resp_main.cookies.items()])

            # 2. layout-sync API 호출 (Token 출처)
            sync_url = (
                "https://casper.hyundai.com/gw/wp/common/v2/common/ui/layout-sync"
            )
            resp_sync = await self._fetch_with_impersonate(sync_url)

            if resp_sync and resp_sync.status_code == 200:
                try:
                    data = resp_sync.json()
                    layout_hash = data.get("data", {}).get("layoutHash")
                    if layout_hash:
                        self.ux_state_key = layout_hash
                        log.info(
                            f"[Refresher] ✅ State-Key(layoutHash) 획득 성공: {layout_hash[:12]}..."
                        )

                        # 쿠키 업데이트 (TS01 등 보안 쿠키 확보 확인)
                        new_cookies = "; ".join(
                            [f"{k}={v}" for k, v in resp_sync.cookies.items()]
                        )
                        if new_cookies:
                            self.cookies = new_cookies

                        self.last_refresh_time = now
                        return True
                except Exception as e:
                    log.error(f"[Refresher] JSON 파싱 에러: {e}")

            log.warning("[Refresher] ⚠️ 토큰 획득 실패 (layout-sync 응답 오류)")
            return False

    def get_headers(self):
        """현재 유효한 보안 헤더 반환"""
        headers = {}
        if self.ux_state_key:
            headers["X-UX-State-Key"] = self.ux_state_key
        if self.cookies:
            headers["Cookie"] = self.cookies
        return headers


# 싱글톤
refresher = TokenRefresher()
