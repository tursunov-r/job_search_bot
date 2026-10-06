#!/usr/bin/env python3
"""Pull the latest code from GitHub and fully rebuild/restart the bot.

Usage: python3 deploy.py
"""

import subprocess
import sys

STEPS = [
    (["git", "pull"], "Тяну изменения из GitHub"),
    (["docker", "compose", "down"], "Останавливаю контейнеры"),
    (["docker", "compose", "build", "--no-cache"], "Пересобираю образ без кеша"),
    (["docker", "compose", "up", "-d"], "Поднимаю контейнеры"),
]


def run(command: list[str], description: str) -> None:
    print(f"\n=== {description} ===")
    print("$", " ".join(command))
    result = subprocess.run(command)
    if result.returncode != 0:
        print(f"\nШаг «{description}» завершился с ошибкой (код {result.returncode}). Останавливаюсь.")
        sys.exit(result.returncode)


def main() -> None:
    for command, description in STEPS:
        run(command, description)
    print("\nГотово. Проверить логи: docker compose logs -f bot")


if __name__ == "__main__":
    main()
