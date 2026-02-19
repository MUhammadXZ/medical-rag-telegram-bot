#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MIN_PYTHON = (3, 9)
DEFAULT_INDEX = "eval/faiss/guidelines.index"
DEFAULT_METADATA = "eval/faiss/guidelines_metadata.json"
TOKEN_PATTERN = re.compile(r"^\d{8,}:[A-Za-z0-9_-]{20,}$")


def print_step(message: str) -> None:
    print(f"\n[setup] {message}")


def ensure_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        version = ".".join(str(part) for part in MIN_PYTHON)
        raise SystemExit(
            f"Python {version}+ is required. Current version: {sys.version.split()[0]}."
        )


def install_requirements(project_root: Path) -> None:
    print_step("Installing dependencies from requirements.txt")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(project_root / "requirements.txt")],
        check=True,
    )


def load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def save_env_file(path: Path, values: dict[str, str]) -> None:
    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            lines.append(raw_line)
            continue

        key, _ = raw_line.split("=", 1)
        normalized_key = key.strip()
        if normalized_key in values:
            lines.append(f"{normalized_key}={values[normalized_key]}")
        else:
            lines.append(raw_line)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prompt_with_default(prompt: str, default: str) -> str:
    entered = input(f"{prompt} [{default}]: ").strip()
    return entered or default


def validate_token_format(token: str) -> bool:
    return bool(TOKEN_PATTERN.match(token))


def test_telegram_connectivity(token: str) -> tuple[bool, str]:
    url = f"https://api.telegram.org/bot{urllib.parse.quote(token, safe=':')}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return False, f"Telegram API HTTP error: {exc.code}. Check token validity."
    except urllib.error.URLError as exc:
        return False, f"Network error while reaching Telegram API: {exc.reason}"

    if '"ok":true' not in payload:
        return False, "Telegram API did not confirm the token. It may be invalid or revoked."
    return True, "Telegram connectivity test passed."


def ensure_env(project_root: Path) -> Path:
    env_path = project_root / ".env"
    template_path = project_root / ".env.example"

    if not template_path.exists():
        raise SystemExit("Missing .env.example template. Cannot continue setup.")

    if not env_path.exists():
        env_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
        print_step("Created .env from .env.example")

    return env_path


def run_wizard(project_root: Path, env_path: Path) -> None:
    print_step("Running interactive configuration wizard")
    current = load_env_file(env_path)

    token_default = current.get("TELEGRAM_BOT_TOKEN", "")
    while True:
        token = prompt_with_default("Enter TELEGRAM_BOT_TOKEN", token_default or "")
        if validate_token_format(token):
            break
        print("Invalid token format. Expected pattern: <bot_id>:<secret> (from BotFather).")

    index_path = prompt_with_default("Path to CMPA_INDEX_PATH", current.get("CMPA_INDEX_PATH", DEFAULT_INDEX))
    metadata_path = prompt_with_default(
        "Path to CMPA_METADATA_PATH", current.get("CMPA_METADATA_PATH", DEFAULT_METADATA)
    )

    missing_files: list[str] = []
    for candidate in (index_path, metadata_path):
        if not (project_root / candidate).exists():
            missing_files.append(candidate)

    if missing_files:
        print("\nThe following FAISS artifacts are missing:")
        for item in missing_files:
            print(f" - {item}")
        print(
            "Remediation: generate or copy FAISS artifacts into eval/faiss/ "
            "before launching the bot."
        )
    else:
        print("FAISS artifact validation passed.")

    print_step("Testing Telegram connectivity")
    ok, message = test_telegram_connectivity(token)
    print(message)
    if not ok:
        print("You can still save .env and fix the token later.")

    save_env_file(
        env_path,
        {
            "TELEGRAM_BOT_TOKEN": token,
            "CMPA_INDEX_PATH": index_path,
            "CMPA_METADATA_PATH": metadata_path,
        },
    )
    print_step(f"Saved configuration to {env_path}")


def launch_bot(project_root: Path) -> None:
    print_step("Launching Telegram bot")
    subprocess.run([sys.executable, "-m", "app.interfaces.telegram_bot"], cwd=project_root, check=True)


def main() -> None:
    project_root = Path(__file__).resolve().parent
    os.chdir(project_root)

    ensure_python_version()
    install_requirements(project_root)
    env_path = ensure_env(project_root)
    run_wizard(project_root, env_path)

    start = input("\nStart the bot now? [Y/n]: ").strip().lower()
    if start in {"", "y", "yes"}:
        launch_bot(project_root)
    else:
        print("Setup complete. Start later with: python -m app.interfaces.telegram_bot")


if __name__ == "__main__":
    main()
