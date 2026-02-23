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
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        viewport={"width": 1280, "height": 720},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    )
                    page = await context.new_page()

                    intercepted_key = None

                    async def handle_request(request):
                        nonlocal intercepted_key
                        if "product/exhibition/cars" in request.url:
                            # 캡처 스크립트가 쏴준 가짜 요청 등에서 헤더 추출
                            for k, v in request.headers.items():
                                if k.lower() == "x-ux-state-key":
                                    intercepted_key = v

                    page.on("request", handle_request)

                    # 브라우저 XMLHttpRequest 후킹 스크립트 주입 (X-UX-State-Key 추출 목적)
                    await page.add_init_script("""
                        window.capturedReqs = [];
                        const originalOpen = XMLHttpRequest.prototype.open;
                        const originalSetHeader = XMLHttpRequest.prototype.setRequestHeader;
                        XMLHttpRequest.prototype.open = function(method, url) { this._url = url; this._headers = {}; return originalOpen.apply(this, arguments); };
                        XMLHttpRequest.prototype.setRequestHeader = function(k, v) { this._headers[k] = v; return originalSetHeader.apply(this, arguments); };
                        const originalFetch = window.fetch;
                        window.fetch = async function(...args) {
                            let url = args[0];
                            if(typeof url !== 'string' && url.url) url = url.url;
                            if (typeof url === 'string' && url.includes('cars')) {
                                let headers = {};
                                if (args[1]) { headers = args[1].headers || {}; }
                                window.capturedReqs.push({type: 'fetch', url: url, headers: headers});
                            }
                            return originalFetch.apply(this, args);
                        };
                    """)

                    # 봇 차단막을 통과하기 위해 기획전 페이지 접속
                    log.info("[Refresher] 안전 페이지 접속 중...")
                    await page.goto(
                        "https://casper.hyundai.com/vehicles/car-list/promotion",
                        wait_until="networkidle",
                    )

                    # WAF 통과 및 토큰 생성을 유도하기 위한 지연 및 클릭
                    await asyncio.sleep(2)

                    try:
                        await page.click("text=초기화", timeout=3000)
                        await asyncio.sleep(1)
                    except:
                        pass

                    # JS 환경 내에서 캡처된 헤더 수집
                    captured = await page.evaluate("window.capturedReqs")
                    js_key = None
                    if captured:
                        for req in captured:
                            headers = req.get("headers", {})
                            for k, v in headers.items():
                                if (
                                    k.lower() == "x-ux-state-key"
                                    or k == "X-UX-State-Key"
                                ):
                                    js_key = v
                                    break
                            if js_key:
                                break

                    self.ux_state_key = js_key or intercepted_key or ""

                    # 쿠키 추출 (TS01... 등)
                    cookies_list = await context.cookies()
                    cookie_str = "; ".join(
                        [f"{c['name']}={c['value']}" for c in cookies_list]
                    )
                    self.cookies = cookie_str

                    await browser.close()

                    if self.ux_state_key and "TS01" in self.cookies:
                        log.info(
                            f"[Refresher] ✅ 보안 토큰 갱신 성공 (Key: {self.ux_state_key[:8]}...)"
                        )
                        self.last_refresh_time = now
                        return True
                    else:
                        log.warning(
                            "[Refresher] ⚠️ 보안 토큰 획득 실패 (응답에 WAF 쿠키나 상태 키가 없음)"
                        )
                        return False

            except Exception as e:
                log.error(f"[Refresher] ❌ 가상 브라우저 구동 중 에러 발생: {e}")
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
