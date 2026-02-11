#!/bin/bash
# CasperFinder Bot - LXC 배포 스크립트
# 사용법: bash setup.sh

set -e

APP_DIR="/opt/casperfinder-bot"
SERVICE_NAME="casperfinder-bot"

echo "===== CasperFinder Bot 배포 시작 ====="

# 1. 시스템 패키지 설치
echo "[1/5] 시스템 패키지 설치..."
apt update -y && apt install -y python3 python3-venv python3-pip

# 2. 앱 디렉토리 생성
echo "[2/5] 앱 디렉토리 설정..."
mkdir -p "$APP_DIR/data"

# 3. 파일 복사 (현재 디렉토리에서)
echo "[3/5] 파일 복사..."
cp -r main.py config.json requirements.txt core/ "$APP_DIR/"

# 4. 가상환경 + 의존성 설치
echo "[4/5] Python 가상환경 생성 및 의존성 설치..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# 5. systemd 서비스 등록
echo "[5/5] systemd 서비스 등록..."
cp deploy/casperfinder-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo ""
echo "===== 배포 완료 ====="
echo "상태 확인:  systemctl status $SERVICE_NAME"
echo "로그 확인:  journalctl -u $SERVICE_NAME -f"
echo ""
