# TODO (CasperFinder_discord)

## 완료
- [x] WAF 우회 아키텍처 설계 (`curl_cffi` 기반)
- [x] `TokenRefresher` 경량화 및 `layout-sync` 연동
- [x] 세션 정합성(Session Consistency v2) 구현 및 `AsyncSession` 도입
- [x] F5 BIG-IP 및 Cloudflare WAF 심층 분석 및 문서화 (`ANALYSIS.md`)
- [x] 장기 안정성 테스트 (10분 이상 무오류 확인)

## 예정
- [ ] 구형 Playwright 의존성 코드 완전 제거 (정리 작업)
- [ ] 에러 발생 시 자동 재시도 로직 고도화
- [ ] 다중 프록시 로테이션 도입 (필요 시)
