import sys
import json
import urllib.request
import datetime
import os


def load_config():
    config_path = "/opt/casperfinder-bot/config.prod.json"
    if not os.path.exists(config_path):
        config_path = "/opt/casperfinder-bot/config.json"

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) < 3:
        print("Usage: python notify_update.py <hash> <message>")
        return

    commit_hash = sys.argv[1]
    commit_msg = " ".join(sys.argv[2:])

    try:
        config = load_config()
        token = config.get("discord", {}).get("token")

        # 기획전/자동 배포 알림 채널 ID
        channel_id = "1471131944334000150"

        if not token:
            print("No token found in config.")
            return

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        github_url = (
            f"https://github.com/jominki354/CasperFinder_discord/commit/{commit_hash}"
        )

        content = (
            f"### **자동 업데이트 및 재시작 완료** ({now})\n"
            f"**커밋 번호:** [{commit_hash}](<{github_url}>)\n"
            f"```\n{commit_msg}\n```"
        )

        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        data = json.dumps({"content": content}).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bot {token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "DiscordBot (https://github.com/jominki354, 1.0)")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print("Successfully sent update notification to Discord.")
            else:
                print(f"Failed to send. Status: {response.status}")

    except Exception as e:
        print(f"Error sending update notification: {e}")


if __name__ == "__main__":
    main()
