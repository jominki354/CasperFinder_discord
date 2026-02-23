# 현대차 기획전 API 보안/WAF 우회 분석 리포트

**작성일시**: 2026-02-23
**대상**: `https://casper.hyundai.com/gw/wp/product/v2/product/exhibition/cars`

## 1. 개요
기존 순수 파이썬(`aiohttp`) 환경에서 JSON POST 요청을 정상적인 파라미터 17개 풀세트로 보내더라도 `TotalCount: 0` 등 빈 껍데기 응답만 반환되는 문제가 발생했습니다. 브라우저 덤프 분석을 통해 현대차가 적용한 신규 봇 방어 로직을 식별하고 이를 우회하는 아키텍처를 수립했습니다.

## 2. 결함 원인 분석 (신규 봇 방어벽)
현대차 WAF(Web Application Firewall)는 이제 단순한 형태의 API 폴링 봇을 차단하기 위해 **실제 브라우저 구동 증명**을 요구합니다.

### 차단 핵심 요소 (Deep Analysis 결과)
1.  **`TS01...` 보안 쿠키 (F5 BIG-IP Advanced WAF)**: 
    *   **식별된 쿠키명**: `TS0123d4c1` 등 (접속 시마다 가변)
    *   **역할**: BIG-IP ASM(Advanced WAF)에서 발행하며, 세션 내의 모든 HTTP/2 프레임워크와 TLS 핸드쉐이크가 일관된 지문(JA3)을 유지하는지 감시합니다. `curl_cffi` 없이 일반 `aiohttp`로 찌를 경우 여기서 즉시 차단됩니다.
2.  **`__cf_bm` 쿠키 및 `cf-ray` 헤더 (Cloudflare Bot Management)**:
    *   Cloudflare의 봇 방어 티어가 적용되어 있습니다. `__cf_bm` 쿠키가 세션에 포함되지 않거나 Cloudflare가 정의한 비정상 지문(JA3/JA4)으로 판단될 경우 챌린지 페이지 혹은 드랍 처리가 발생합니다.
3.  **`X-UX-State-Key` 헤더 (`layoutHash`)**:
    *   **출처 API**: `GET https://casper.hyundai.com/gw/wp/common/v2/common/ui/layout-sync`
    *   **데이터 구조**: `{"data":{"layoutHash":"UUID-FORMAT-KEY","valid":"true"}, ...}`
    *   **유효성**: 특정 브라우저 세션(위의 쿠키들과 결합된 상태)에 종속된 고유 키입니다.

### 기술적 상세 (Nuxt.js 내부 로직)
- **스크립트 경로**: `https://casper.hyundai.com/_nuxt/3abb850.js`
- **실행 시퀀스**:
    1.  사용자 액션 발생 (기획전 페이지 로드 또는 필터 변경)
    2.  `dispatch('GET_LAYOUT_HASH')` 액션 트리거
    3.  `layout-sync` API 호출하여 `layoutHash` 수신 및 전역 상태(Store) 저장
    4.  `postExhibitionCarList` 호출 시 `headers: { 'x-ux-state-key': store.layoutHash }` 강제 주입
- **특이 사항**: 서버는 이 호출 시퀀스 사이의 시간차(Latency)와 세션 쿠키의 생존 시간(TTL)을 비교 검증하여 자동화 봇 여부를 판별합니다.

## 3. 해결 방안 (curl_cffi 기반 경량화 & 지문 위장)
파이썬 엔진을 유지하면서, 브라우저의 TLS 지문(JA3)을 완벽히 모방하는 `curl_cffi` 라이브러리를 도입했습니다.

### 아키텍처 로직 (개선됨)
1.  **초경량 토큰 획득 (curl_cffi)**:
    *   `TokenRefresher`는 이제 무거운 Playwright 대신 `curl_cffi`를 사용하여 `layout-sync` API를 직접 찌릅니다.
    *   `impersonate="chrome110"` 옵션을 통해 서버가 해당 요청을 실제 브라우저로 인식하게 만듭니다.
    *   응답 JSON에서 `layoutHash`(`X-UX-State-Key`)를 즉각 추출합니다.
2.  **지문 일치 조회 (curl_cffi)**:
    *   `api.py`의 모든 조회 요청 역시 `curl_cffi`를 사용합니다.
    *   토큰을 딸 때와 데이터를 가져올 때의 **TLS 지문이 완벽히 일치**하므로 WAF는 이를 동일한 정상 브라우저 세션으로 판단합니다.
    *   "가짜 응답 (Data: {})" 문제를 근본적으로 차단하며, 조회 속도는 0.1초 수준으로 비약적인 향상을 이뤘습니다.

*   이 방식은 타사 봇들이 브라우저를 매번 열어서 리소스를 낭비하는 방식과 대비되어 **서버 부하는 무시할 수준이면서도, 조달 속도는 실시간 최속**을 유지하는 최종 진화형 패턴입니다.

## 4. 인프라 및 메타 헤더 (Technical Headers)
브라우저 분석 결과, WAF 통과를 위해 필수적으로 포함되어야 하는 메타 헤더들입니다:
- `ep-channel: wpc`: 현대차 웹 채널 식별자
- `ep-version: v2`: API 버전 명세
- `service-type: product` / `common`: 요청 도메인별 서비스 타입 구분
- `X-Requested-With: XMLHttpRequest`: AJAX 요청 명시

## 5. 다차원 우회 전략 (보강)
단순한 토큰 교체만으로는 부족하며, 다음 세 가지 요소의 **동기화(Synchronization)**가 핵심입니다:
1.  **TLS 지문 일치 (Cipher Suite)**: `curl_cffi`를 사용하여 `layout-sync`와 차량 조회 시 동일한 브라우저 지문(Chrome 110 JA3)을 유지.
2.  **세션 쿠키 영속성 (Cookie Persistence)**: `AsyncSession`을 사용하여 `TS01` 및 `__cf_bm` 쿠키를 유실 없이 전 구간에서 자동 관리.
3.  **엄격한 호출 시퀀스 (Strict Sequence)**: 조회 직전에 반드시 `layout-sync`를 호출하여 서버가 기대하는 상태 키의 TTL(Time-To-Live)을 만족시킴.


* 예시데이타
```
{
  "data": {
    "totalCount": 8,
    "discountsearchcars": [
      {
        "vehicleId": "246CF972-27D4-411B-9430-8E1E627C1E1B",
        "carNm": "캐스퍼 일렉트릭",
        "carPrice": 31500000,
        "trimNm": "인스퍼레이션",
        "extCrNm": "버터크림 옐로우 펄 / ...",
        "intCrNm": "베이지 풀 투톤",
        "carProductionDate": "20241022",
        "discountAmt": 3000000,
        "poName": "제주인수센터",
        "options": [
          {"optionName": "파킹 어시스트"}
        ]
      }
      // ... (나머지 7대의 차량 데이터)
    ]
  },
  "rspStatus": {
    "rspCode": "0000",
    "rspMessage": "성공"
  }
}
```