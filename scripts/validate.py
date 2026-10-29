"""Run the complete real suite and retain its unmodified output and exit status."""
import datetime
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs" / "validation"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    DEST.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-u", "scripts/run.py", "test", *sys.argv[1:]]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (DEST / "integration.log").open("wb") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line.decode("utf-8", errors="replace"), end="", flush=True)
        result = process.wait()
    metadata = {"started_utc": started, "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "command": ["python", "scripts/run.py", "test", *sys.argv[1:]], "exit_code": result,
                "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    (DEST / "result.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    sys.exit(main())
