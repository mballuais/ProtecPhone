from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    queries = [line for line in (ROOT / "docs/REQUETES-NOSQL.md").read_text(encoding="utf-8").splitlines()
               if line.startswith("docker compose exec ")]
    target = ROOT / "docs/validation/requetes.log"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as log:
        for command in queries:
            result = subprocess.run(shlex.split(command), cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
            log.write(command + "\n" + result.stdout + result.stderr + f"\nexit_code={result.returncode}\n\n")
            result.check_returncode()
    print(f"OK : {len(queries)} requetes executees ; {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
