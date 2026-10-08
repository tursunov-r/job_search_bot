#!/usr/bin/env python3
"""Pull from GitHub; rebuild/restart the bot only if something actually changed.

Meant to run unattended on a schedule (e.g. via crontab every 5-10 minutes)
so a deploy happens automatically after a push, without needing to be on
the same network/IP as the Pi to trigger it by hand. If there's nothing
new, it exits quietly without touching the running containers.

Usage: python3 deploy.py

Crontab example (check every 5 minutes, log to a file):
    */5 * * * * cd /home/pi/telegram_bot/job_search_bot && python3 deploy.py >> deploy.log 2>&1
"""

import subprocess
import sys


def run(command: list[str], description: str) -> None:
    print(f"\n=== {description} ===")
    print("$", " ".join(command))
    result = subprocess.run(command)
    if result.returncode != 0:
        print(f"\nШаг «{description}» завершился с ошибкой (код {result.returncode}). Останавливаюсь.")
        sys.exit(result.returncode)


def current_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> None:
    before = current_commit()

    pull = subprocess.run(["git", "pull"], capture_output=True, text=True)
    if pull.returncode != 0:
        print("=== git pull завершился с ошибкой ===")
        print(pull.stdout)
        print(pull.stderr)
        sys.exit(pull.returncode)

    after = current_commit()
    if before == after:
        # Нет новых коммитов — работающие контейнеры не трогаем.
        return

    print(f"=== Новый коммит: {before[:8]} -> {after[:8]} ===")
    print(pull.stdout)

    run(["docker", "compose", "down"], "Останавливаю контейнеры")
    run(["docker", "compose", "build", "--no-cache"], "Пересобираю образ без кеша")
    run(["docker", "compose", "up", "-d"], "Поднимаю контейнеры")
    print("\nГотово. Проверить логи: docker compose logs -f bot")


if __name__ == "__main__":
    main()
