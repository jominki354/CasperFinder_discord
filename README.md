# CasperFinder Discord Bot (casperfinder_bot)

캐스퍼 기획전 신규 차량을 감지하여 Discord 채널에 알림을 전송하는 봇입니다.

## 사전 준비

1. [Discord Developer Portal](https://discord.com/developers/applications)에서 봇 생성
2. Bot 토큰 복사
3. 서버에 봇 초대 (Send Messages, Embed Links 권한)
4. 각 채널 ID 확인 (개발자 모드 활성화 → 채널 우클릭 → ID 복사)

## 설정

`config.json`을 열고 아래 값을 입력합니다:

```json
{
  "discord": {
    "token": "실제_봇_토큰",
    "integratedChannelId": "통합_채널_ID"
  },
  "targets": [
    { "channelId": "특별기획전_채널_ID", "label": "특별기획전", "exhbNo": "E20260277", "deliveryAreaCode": "T", "deliveryLocalAreaCode": "T1", "subsidyRegion": "1100" },
    { "channelId": "전시차_채널_ID", "label": "전시차", "exhbNo": "D0003", "subsidyRegion": "1100" },
    { "channelId": "리퍼브_채널_ID", "label": "리퍼브", "exhbNo": "R0003", "deliveryAreaCode": "T", "deliveryLocalAreaCode": "T1", "subsidyRegion": "" }
  ],
  "api": {
    "baseUrl": "https://casper.hyundai.com/gw/wp/product/v2/product/exhibition/cars",
    "headers": {
      "Content-Type": "application/json;charset=utf-8",
      "Accept": "application/json, text/plain, */*",
      "ep-channel": "wpc",
      "ep-version": "v2",
      "service-type": "product",
      "x-b3-sampled": "1",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    },
    "defaultPayload": {
      "subsidyRegion": "1100",
      "choiceOptYn": "Y",
      "carCode": "",
      "sortCode": "50",
      "deliveryAreaCode": "T",
      "deliveryLocalAreaCode": "T1",
      "carBodyCode": "",
      "carEngineCode": "",
      "carTrimCode": "",
      "exteriorColorCode": "",
      "interiorColorCode": [],
      "deliveryCenterCode": "",
      "wpaScnCd": "",
      "optionFilter": "",
      "pageNo": 1,
      "pageSize": 18
    }
  }
}
```
**🚨 필수 주의사항 (Anti-Bot 우회 파라미터):**
최신 현대차 보안 패치 대응을 위해 위 `defaultPayload` 안의 **18개 항목(특히 값이 빈 문자열 `""` 이나 빈 배열 `[]` 인 필드들)을 단 하나도 누락 없이** `config.json`에 100% 동일하게 입력해야 기획전 차량이 정상 감지됩니다 (0대 응답 버그 방지).

## 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 봇 실행
python main.py
```

## 배포 (Proxmox LXC)

```bash
# systemd 서비스 등록
sudo cp casperfinder-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable casperfinder-bot
sudo systemctl start casperfinder-bot

# 로그 확인
journalctl -u casperfinder-bot -f
```
