import logging
import asyncio
from playwright.async_api import async_playwright

log = logging.getLogger("CasperFinder")


class TokenRefresher:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.cookies = ""
        self.ux_state_key = ""
        self.last_refresh_time = 0

    async def refresh_tokens(self, force=False):
        """
        [로컬 테스트 v4 검증 방식]
        네트워크 트래픽을 직접 감시하여 WAF 보안 토큰을 획득합니다.
        """
        async with self.lock:
            now = asyncio.get_event_loop().time()
            if not force and (now - self.last_refresh_time) < 1200:
                return True

            log.info(
                "[Refresher] 🛡️ 가상 브라우저(Playwright) 기동 및 토큰 획득 시도..."
            )

            try:
                async with async_playwright() as p:
                    # 브라우저 실행
                    browser = await p.chromium.launch(
                        headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
                    )
                    context = await browser.new_context(
                        viewport={"width": 1280, "height": 800},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    )
                    page = await context.new_page()

                    intercepted_key = None

                    # 요청 헤더 감시 (테스트와 동일한 핵심 로직)
                    async def on_request(request):
                        nonlocal intercepted_key
                        key = request.headers.get("x-ux-state-key")
                        if key and not intercepted_key:
                            intercepted_key = key
                            log.info(
                                f"[Refresher] 🔑 토큰 인터셉트 성공: {key[:12]}..."
                            )

                    page.on("request", on_request)

                    # 로컬 테스트에서 성공했던 페이지 순회 전략
                    target_urls = [
                        "https://casper.hyundai.com/vehicles/car-list/promotion?exhbNo=E20260277",
                        "https://casper.hyundai.com/vehicles/car-list/promotion?exhbNo=D0003",
                        "https://casper.hyundai.com/vehicles/car-list/promotion?exhbNo=R0003",
                    ]

                    for url in target_urls:
                        if intercepted_key:
                            break

                        try:
                            log.info(
                                f"[Refresher] 페이지 접속 중: {url.split('=')[-1]}"
                            )
                            # networkidle: API 호출이 모두 끝날 때까지 대기 (가장 확실함)
                            await page.goto(
                                url, wait_until="networkidle", timeout=60000
                            )
                            await asyncio.sleep(2)

                            # 초기화 버튼 클릭 시도 (강제 API 발생)
                            try:
                                await page.click(
                                    "button:has-text('초기화')", timeout=3000
                                )
                                await asyncio.sleep(2)
                            except:
                                pass
                        except Exception as e:
                            log.warning(f"[Refresher] 접속 중 오류 발생(무시): {e}")

                    # 최종 결과 정리
                    self.ux_state_key = intercepted_key or ""

                    # 쿠키 추출
                    cookies_list = await context.cookies()
                    self.cookies = "; ".join(
                        [f"{c['name']}={c['value']}" for c in cookies_list]
                    )

                    await browser.close()

                    has_ts_cookie = "TS01" in self.cookies
                    if self.ux_state_key and has_ts_cookie:
                        log.info(
                            f"[Refresher] ✅ 보안 토큰 획득 완료 (Key: {self.ux_state_key[:8]}...)"
                        )
                        self.last_refresh_time = now
                        return True
                    else:
                        log.warning(
                            f"[Refresher] ⚠️ 획득 실패 (Key: {'O' if self.ux_state_key else 'X'}, TS01: {'O' if has_ts_cookie else 'X'})"
                        )
                        return False

            except Exception as e:
                log.error(f"[Refresher] ❌ 에러 발생: {e}")
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
