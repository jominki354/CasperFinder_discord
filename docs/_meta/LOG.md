# CaspeFinder Changelog

## [2026-02-23] v0.1.6-beta (WAF Bypass Optimization)
* **[CasperFinder_discord]**
  * `core/playwright_refresher.py`를 `curl_cffi` 기반으로 전면 개편 (Playwright 의존성 제거 가능)
  * `core/api.py`를 `curl_cffi` 기반으로 개편하여 TLS Fingerprint(JA3) 일치화 달성
  * `layout-sync` API를 통한 `X-UX-State-Key` 추출 로직 도입
  * "Bot Neutralized (Data: {})" WAF 차단 문제 완전 해결
* **분석 결과**: TLS 지문 위장(`impersonate`)을 통해 현대차 WAF를 완벽하게 속이는 데 성공하였으며, 실시간 조회 속도를 비약적으로 향상시킴.

## [2026-02-23] v0.1.5-beta (WAF Bypass Integration - DEPRECATED)
* **[CasperFinder_discord]**
  * `core/playwright_refresher.py` 신규 모듈 추가 (Playwright 기반 헤드리스 브라우저 활용)
  * `main.py`에 백그라운드 갱신 루프(`refresh_tokens_loop`) 탑재 (20분 간격)
  * `core/api.py` 내의 기존 구형 토큰 갱신 코드(`get_layout_hash`) 제거 및 신규 모듈로 이관
  * `requirements.txt`에 `playwright>=1.41.0` 의존성 추가
* **분석 결과**: 현대차 캐스퍼 서버의 신규 WAF 방어막(동적 암호키 및 쿠키 검증)을 우회하기 위해 파이썬+브라우저 하이브리드 세션을 적용함.
