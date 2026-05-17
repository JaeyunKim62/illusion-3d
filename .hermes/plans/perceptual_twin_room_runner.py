#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import pathlib
import subprocess
import time

ROOT = pathlib.Path(r"C:\00_Codes\illusion-3d")
PROMPT = ROOT / ".hermes" / "plans" / "perceptual-twin-room-tick-prompt.txt"
LOG = ROOT / ".hermes" / "plans" / "perceptual-twin-room-runner-2026-05-17.log"
STATUS = ROOT / ".hermes" / "plans" / "perceptual-twin-room-runner-status.txt"
DURATION_SECONDS = 3 * 60 * 60
MAX_TICKS = 9
SLEEP_BETWEEN_TICKS = 30


def stamp() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def append(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(text)


def write_status(tick: int, state: str, detail: str = "") -> None:
    STATUS.write_text(
        f"updated={stamp()}\n"
        f"tick={tick}\n"
        f"state={state}\n"
        f"detail={detail}\n",
        encoding="utf-8",
    )


def main() -> int:
    started = time.time()
    append(LOG, f"\n=== runner start {stamp()} duration={DURATION_SECONDS}s max_ticks={MAX_TICKS} ===\n")
    for tick in range(1, MAX_TICKS + 1):
        elapsed = time.time() - started
        if elapsed >= DURATION_SECONDS:
            break
        write_status(tick, "running", "starting hermes chat tick")
        append(LOG, f"\n--- tick {tick} start {stamp()} elapsed={elapsed:.0f}s ---\n")
        cmd = [
            "hermes",
            "chat",
            "-Q",
            "--source",
            "perceptual-twin-room-3h-runner",
            "--max-turns",
            "80",
            "-s",
            "webgl-3d-viewers",
            "-s",
            "subagent-driven-development",
            "-t",
            "terminal,file,browser,skills,delegation",
            "-q",
            PROMPT.read_text(encoding="utf-8"),
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=min(55 * 60, int(DURATION_SECONDS - elapsed)),
            )
            append(LOG, proc.stdout[-20000:])
            append(LOG, f"\n--- tick {tick} exit={proc.returncode} end {stamp()} ---\n")
            write_status(tick, "tick_finished", f"exit={proc.returncode}")
            if proc.returncode != 0:
                append(LOG, "runner stopping after non-zero tick exit\n")
                break
        except subprocess.TimeoutExpired as exc:
            append(LOG, f"\n--- tick {tick} TIMEOUT {stamp()} ---\n{exc.stdout or ''}\n")
            write_status(tick, "timeout", "stopping after timeout")
            break
        remaining = DURATION_SECONDS - (time.time() - started)
        if remaining <= SLEEP_BETWEEN_TICKS:
            break
        time.sleep(SLEEP_BETWEEN_TICKS)
    write_status(tick if 'tick' in locals() else 0, "done", "runner completed or stopped")
    append(LOG, f"\n=== runner end {stamp()} total_elapsed={time.time() - started:.0f}s ===\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
