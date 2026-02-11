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
    { "channelId": "특별기획전_채널_ID", ... },
    { "channelId": "전시차_채널_ID", ... },
    { "channelId": "리퍼브_채널_ID", ... }
  ]
}
```

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
