import subprocess
import time

for i in range(12):
    print(f"\n[Attempt {i + 1}]")
    result = subprocess.run(
        [
            "ssh",
            "mk1",
            "lxc-attach -n 201 -- bash -c 'cd /opt/casperfinder-bot && cat data/update.log 2>/dev/null | tail -n 2; git log -1 --oneline'",
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout.strip())
    if "5ec413b" in result.stdout:
        print("DETECTED PULL!")
        break
    time.sleep(5)
