"""Start Docker, seed via business APIs, verify flows and exercise real restarts."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def compose(*args):
    subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True)


def check(action):
    compose("run", "--rm", "--no-deps", "checks", action)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["demo", "test"], nargs="?", default="demo")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    # Stop writers before deleting the isolated demonstration namespace.
    compose("up", "-d", "--wait", "redis")
    compose("stop", "product", "orders", "sav")
    check("reset")
    build = [] if args.no_build else ["--build"]
    compose("up", *build, "-d", "--wait", "product", "orders", "sav")
    check(args.action)
    if args.action == "test":
        try:
            compose("stop", "orders")
            check("offline-publish")
            compose("up", "-d", "--wait", "orders")
            check("offline-verify")
            compose("stop", "product")
            check("stage-inflight")
            # Redis persistence is tested with an actual restart while the event is in flight.
            compose("restart", "redis")
            compose("up", "-d", "--wait", "redis", "product", "orders", "sav")
            check("recovered")
            compose("kill", "-s", "SIGKILL", "product")
            compose("up", "-d", "--wait", "product")
            check("recovered")
            print("OK : 14 tests d'integration + indisponibilite, reprise en cours, persistance Redis et arret brutal", flush=True)
        finally:
            compose("up", "-d", "--wait", "product", "orders", "sav")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"ECHEC : commande Docker terminee avec le code {error.returncode}", file=sys.stderr)
        compose("logs", "--tail", "40", "product", "orders", "sav")
        sys.exit(error.returncode)
