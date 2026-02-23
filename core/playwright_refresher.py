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

                    # === 요청(request) 이벤트 감시 ===
                    async def handle_request(request):
                        nonlocal intercepted_key
                        headers = request.headers
                        for k, v in headers.items():
                            if k.lower() == "x-ux-state-key" and v:
                                intercepted_key = v
                                log.info(
                                    f"[Refresher] 🔑 Request 이벤트에서 State-Key 발견: {v[:16]}..."
                                )

                    # === 응답(response) 이벤트 감시 ===
                    async def handle_response(response):
                        nonlocal intercepted_key
                        # 응답의 원본 요청에서도 헤더 추출 시도
                        try:
                            req_headers = response.request.headers
                            for k, v in req_headers.items():
                                if k.lower() == "x-ux-state-key" and v:
                                    if not intercepted_key:
                                        intercepted_key = v
                                        log.info(
                                            f"[Refresher] 🔑 Response→Request 역추적으로 State-Key 발견: {v[:16]}..."
                                        )
                        except Exception:
                            pass

                    page.on("request", handle_request)
                    page.on("response", handle_response)

                    # 브라우저 XMLHttpRequest/fetch 후킹 스크립트 주입
                    await page.add_init_script("""
                        window.__capturedStateKeys = [];
                        window.capturedReqs = [];
                        
                        // XMLHttpRequest 후킹
                        const originalOpen = XMLHttpRequest.prototype.open;
                        const originalSetHeader = XMLHttpRequest.prototype.setRequestHeader;
                        const originalSend = XMLHttpRequest.prototype.send;
                        XMLHttpRequest.prototype.open = function(method, url) {
                            this._url = url; this._headers = {};
                            return originalOpen.apply(this, arguments);
                        };
                        XMLHttpRequest.prototype.setRequestHeader = function(k, v) {
                            this._headers[k] = v;
                            if (k.toLowerCase() === 'x-ux-state-key') {
                                window.__capturedStateKeys.push(v);
                            }
                            return originalSetHeader.apply(this, arguments);
                        };
                        
                        // Fetch 후킹
                        const originalFetch = window.fetch;
                        window.fetch = async function(...args) {
                            let url = (typeof args[0] === 'string') ? args[0] : (args[0]?.url || "");
                            let headers = {};
                            try {
                                if (args[1] && args[1].headers) {
                                    if (args[1].headers instanceof Headers) {
                                        args[1].headers.forEach((v, k) => { headers[k] = v; });
                                    } else {
                                        headers = args[1].headers;
                                    }
                                }
                            } catch(e) {}
                            
                            // State-Key 캡처
                            for (let [k, v] of Object.entries(headers)) {
                                if (k.toLowerCase() === 'x-ux-state-key') {
                                    window.__capturedStateKeys.push(v);
                                }
                            }
                            
                            window.capturedReqs.push({url: url, headers: headers});
                            return originalFetch.apply(this, args);
                        };
                    """)

                    # ── 1단계: 메인 페이지 접속 ──
                    log.info("[Refresher] 1단계: 현대차 캐스퍼 메인 접속...")
                    await page.goto(
                        "https://casper.hyundai.com",
                        wait_until="networkidle",
                        timeout=120000,
                    )
                    await asyncio.sleep(3)

                    # 이미 Key를 잡았는지 중간 확인
                    if intercepted_key:
                        log.info("[Refresher] ✅ 1단계에서 이미 State-Key 획득!")

                    # ── 2단계: 기획전 페이지로 이동 ──
                    log.info("[Refresher] 2단계: 기획전 페이지 이동...")
                    await page.goto(
                        "https://casper.hyundai.com/vehicles/car-list/promotion?exhbNo=E20260277",
                        wait_until="networkidle",
                        timeout=120000,
                    )
                    await asyncio.sleep(5)

                    # ── 3단계: 사용자 행위 시뮬레이션으로 API 호출 유도 ──
                    log.info("[Refresher] 3단계: 사용자 행위 시뮬레이션...")

                    # 3-1. 초기화 버튼 클릭 시도
                    try:
                        await page.click("button:has-text('초기화')", timeout=5000)
                        log.info("[Refresher] 3단계: 초기화 버튼 클릭 완료")
                        await asyncio.sleep(3)
                    except Exception:
                        log.warning(
                            "[Refresher] 초기화 버튼을 찾지 못했으나 계속 진행합니다."
                        )

                    # 3-2. 스크롤 다운으로 lazy-load API 호출 유도
                    if not intercepted_key:
                        try:
                            await page.evaluate(
                                "window.scrollTo(0, document.body.scrollHeight)"
                            )
                            await asyncio.sleep(2)
                            await page.evaluate("window.scrollTo(0, 0)")
                            await asyncio.sleep(1)
                        except Exception:
                            pass

                    # 3-3. 다른 기획전 탭 클릭 시도 (API 재호출 유도)
                    if not intercepted_key:
                        for selector in [
                            "button:has-text('전시차')",
                            "a:has-text('전시차')",
                            "[data-tab]:nth-child(2)",
                            ".tab-item:nth-child(2)",
                        ]:
                            try:
                                await page.click(selector, timeout=3000)
                                log.info(f"[Refresher] 탭 클릭 성공: {selector}")
                                await asyncio.sleep(3)
                                break
                            except Exception:
                                continue

                    # ── 4단계: JS 환경에서 캡처된 State-Key 수집 ──
                    js_key = None
                    try:
                        # 방법 A: 후킹된 __capturedStateKeys 배열에서 추출
                        captured_keys = await page.evaluate(
                            "window.__capturedStateKeys || []"
                        )
                        if captured_keys:
                            js_key = captured_keys[-1]  # 가장 최근 키
                            log.info(
                                f"[Refresher] 🔑 JS 후킹에서 State-Key {len(captured_keys)}개 발견"
                            )
                    except Exception:
                        pass

                    if not js_key:
                        try:
                            # 방법 B: capturedReqs에서 추출
                            captured = await page.evaluate("window.capturedReqs || []")
                            if captured:
                                for req in captured:
                                    h = req.get("headers", {})
                                    for k, v in h.items():
                                        if k.lower() == "x-ux-state-key":
                                            js_key = v
                                            break
                                    if js_key:
                                        break
                        except Exception:
                            pass

                    if not js_key and not intercepted_key:
                        # 방법 C: 페이지 전역 변수/localStorage/sessionStorage 탐색
                        try:
                            js_key = await page.evaluate("""
                                (() => {
                                    // Next.js __NEXT_DATA__ 확인
                                    if (window.__NEXT_DATA__) {
                                        const props = JSON.stringify(window.__NEXT_DATA__);
                                        const match = props.match(/state[Kk]ey["\s:]+["']([^"']+)/);
                                        if (match) return match[1];
                                    }
                                    // localStorage 탐색
                                    for (let i = 0; i < localStorage.length; i++) {
                                        const key = localStorage.key(i);
                                        const val = localStorage.getItem(key);
                                        if (key.toLowerCase().includes('state') && key.toLowerCase().includes('key')) {
                                            return val;
                                        }
                                        if (val && val.length > 20 && val.length < 200) {
                                            try {
                                                const obj = JSON.parse(val);
                                                if (obj['X-UX-State-Key'] || obj['x-ux-state-key']) {
                                                    return obj['X-UX-State-Key'] || obj['x-ux-state-key'];
                                                }
                                            } catch(e) {}
                                        }
                                    }
                                    // sessionStorage 탐색
                                    for (let i = 0; i < sessionStorage.length; i++) {
                                        const key = sessionStorage.key(i);
                                        const val = sessionStorage.getItem(key);
                                        if (key.toLowerCase().includes('state') && key.toLowerCase().includes('key')) {
                                            return val;
                                        }
                                    }
                                    return null;
                                })()
                            """)
                            if js_key:
                                log.info(
                                    f"[Refresher] 🔑 Storage/전역변수에서 State-Key 발견: {js_key[:16]}..."
                                )
                        except Exception as e:
                            log.debug(f"[Refresher] Storage 탐색 실패: {e}")

                    final_key = js_key or intercepted_key or ""
                    self.ux_state_key = final_key

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
                        # 디버깅을 위해 쿠키 이름 + 캡처된 요청 수 로깅
                        cookie_names = [c["name"] for c in cookies_list]
                        log.info(f"[Refresher] 발견된 쿠키 목록: {cookie_names}")
                        try:
                            req_count = (
                                await page.evaluate("window.capturedReqs?.length || 0")
                                if not browser.is_connected()
                                else 0
                            )
                        except Exception:
                            req_count = "N/A"
                        log.info(f"[Refresher] 캡처된 요청 수: {req_count}")
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
