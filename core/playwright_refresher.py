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
        Playwright를 헤드리스 모드로 실행하여
        현대차 WAF 보안 쿠키와 X-UX-State-Key를 획득합니다.
        """
        async with self.lock:
            # 기본 갱신 주기 20분 (1200초)
            now = asyncio.get_event_loop().time()
            if not force and (now - self.last_refresh_time) < 1200:
                return True

            log.info(
                "[Refresher] 🛡️ 가상 브라우저(Playwright)를 기동하여 보안 토큰 갱신 시작..."
            )
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
                    )
                    context = await browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                        extra_http_headers={
                            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                        },
                    )
                    page = await context.new_page()

                    intercepted_key = None

                    async def handle_request(request):
                        nonlocal intercepted_key
                        # 모든 요청 헤더를 감시하여 X-UX-State-Key가 담긴 패턴을 찾습니다.
                        headers = request.headers
                        for k, v in headers.items():
                            if k.lower() == "x-ux-state-key":
                                intercepted_key = v
                                # log.debug(f"[Refresher] Intercepted Key from {request.url[:50]}...")

                    page.on("request", handle_request)

                    # 브라우저 XMLHttpRequest 후킹 스크립트 주입
                    await page.add_init_script("""
                        window.capturedReqs = [];
                        const originalOpen = XMLHttpRequest.prototype.open;
                        const originalSetHeader = XMLHttpRequest.prototype.setRequestHeader;
                        XMLHttpRequest.prototype.open = function(method, url) { this._url = url; this._headers = {}; return originalOpen.apply(this, arguments); };
                        XMLHttpRequest.prototype.setRequestHeader = function(k, v) { this._headers[k] = v; return originalSetHeader.apply(this, arguments); };
                        
                        const originalFetch = window.fetch;
                        window.fetch = async function(...args) {
                            let url = (typeof args[0] === 'string') ? args[0] : (args[0].url || "");
                            let response = await originalFetch.apply(this, args);
                            if (url.includes('cars') || url.includes('promotion')) {
                                let headers = {};
                                try {
                                    if(args[1] && args[1].headers) headers = args[1].headers;
                                } catch(e){}
                                window.capturedReqs.push({url: url, headers: headers});
                            }
                            return response;
                        };
                    """)

                    # 1. 먼저 메인 페이지 접속 (자연스러운 유동 유도)
                    log.info("[Refresher] 1단계: 현대차 캐스퍼 메인 접속...")
                    await page.goto(
                        "https://casper.hyundai.com",
                        wait_until="domcontentloaded",
                        timeout=120000,
                    )
                    await asyncio.sleep(3)

                    # 2. 기획전 페이지로 이동 (exhbNo 파라미터 필수)
                    log.info("[Refresher] 2단계: 기획전 페이지 이동...")
                    await page.goto(
                        "https://casper.hyundai.com/vehicles/car-list/promotion?exhbNo=E20260277",
                        wait_until="domcontentloaded",
                        timeout=120000,
                    )
                    # networkidle 대신 DOM 로드 후 추가 대기로 API 호출 유도
                    await asyncio.sleep(5)

                    # 3. 데이터 로딩을 위해 잠시 대기 및 "초기화" 버튼 클릭 시도 (이벤트 발생)
                    await asyncio.sleep(3)
                    try:
                        # 초기화 버튼을 눌러서 API 호출을 강제로 발생시킴
                        await page.click("button:has-text('초기화')", timeout=5000)
                        log.info("[Refresher] 3단계: 초기화 버튼 클릭 완료")
                        await asyncio.sleep(2)
                    except Exception:
                        log.warning(
                            "[Refresher] 초기화 버튼을 찾지 못했으나 계속 진행합니다."
                        )

                    # JS 환경 내에서 캡처된 헤더 수집
                    captured = await page.evaluate("window.capturedReqs")
                    js_key = None
                    if captured:
                        for req in captured:
                            h = req.get("headers", {})
                            for k, v in h.items():
                                if k.lower() == "x-ux-state-key":
                                    js_key = v
                                    break
                            if js_key:
                                break

                    self.ux_state_key = js_key or intercepted_key or ""

                    # 쿠키 추출
                    cookies_list = await context.cookies()
                    self.cookies = "; ".join(
                        [f"{c['name']}={c['value']}" for c in cookies_list]
                    )

                    await browser.close()

                    has_ts_cookie = "TS01" in self.cookies
                    if self.ux_state_key and has_ts_cookie:
                        log.info(
                            f"[Refresher] ✅ 보안 토큰 획득 성공 (Key: {self.ux_state_key[:8]}...)"
                        )
                        self.last_refresh_time = now
                        return True
                    else:
                        fail_reason = []
                        if not self.ux_state_key:
                            fail_reason.append("State-Key 누락")
                        if not has_ts_cookie:
                            fail_reason.append("TS01 쿠키 누락")
                        log.warning(
                            f"[Refresher] ⚠️ 갱신 실패: {', '.join(fail_reason)}"
                        )
                        # 디버깅을 위해 쿠키 이름들 로깅
                        cookie_names = [c["name"] for c in cookies_list]
                        log.debug(f"[Refresher] 발견된 쿠키 목록: {cookie_names}")
                        return False

            except Exception as e:
                log.error(f"[Refresher] ❌ 가상 브라우저 구동 중 에러 발생: {e}")
                import traceback

                log.error(traceback.format_exc())
                return False

    def get_headers(self):
        """현재 유효한 보안 헤더 반환"""
        headers = {}
        if self.ux_state_key:
            headers["X-UX-State-Key"] = self.ux_state_key
        if self.cookies:
            headers["Cookie"] = self.cookies
        return headers


# 전역 싱글톤 인스턴스
refresher = TokenRefresher()
