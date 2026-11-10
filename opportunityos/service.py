"""Install and manage the macOS per-user OpportunityOS LaunchAgent."""
import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

from .store import ROOT, Store

LABEL = "local.opportunityos"
LAUNCHCTL = "/bin/launchctl"


def launchctl(*args, check=True, quiet=False):
    return subprocess.run([LAUNCHCTL, *args], check=check,
                          stdout=subprocess.DEVNULL if quiet else None,
                          stderr=subprocess.DEVNULL if quiet else None)


def install(plist, domain, target, directory, port):
    store = Store(directory)
    logs = store.directory / "logs"
    logs.mkdir(exist_ok=True, mode=0o700)
    spec = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, "-m", "opportunityos", "--data",
                             str(store.directory), "--port", str(port)],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 15,
        "Umask": 0o077,
        "StandardOutPath": str(logs / "service.log"),
        "StandardErrorPath": str(logs / "service-error.log"),
    }
    previous = plist.read_bytes() if plist.is_file() else None
    plist.parent.mkdir(parents=True, exist_ok=True)
    temporary = plist.with_suffix(".tmp")
    temporary.write_bytes(plistlib.dumps(spec))
    temporary.replace(plist)
    was_loaded = launchctl("print", target, check=False, quiet=True).returncode == 0
    if was_loaded:
        launchctl("bootout", target)
    try:
        launchctl("bootstrap", domain, str(plist))
    except subprocess.CalledProcessError:
        if previous is None:
            plist.unlink(missing_ok=True)
        else:
            plist.write_bytes(previous)
            if was_loaded:
                launchctl("bootstrap", domain, str(plist), check=False)
        raise
    print(f"Installed {LABEL} · http://127.0.0.1:{port}")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "status", "restart", "uninstall"))
    parser.add_argument("--data", default="~/Library/Application Support/OpportunityOS")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("LaunchAgent setup requires macOS")
    if not 1024 <= args.port <= 65535:
        parser.error("Choose an unprivileged TCP port between 1024 and 65535")
    plist = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    domain = f"gui/{os.getuid()}"
    target = f"{domain}/{LABEL}"
    if args.command == "install":
        install(plist, domain, target, args.data, args.port)
    elif args.command == "status":
        launchctl("print", target)
    elif args.command == "restart":
        launchctl("kickstart", "-k", target)
    else:
        if launchctl("print", target, check=False, quiet=True).returncode == 0:
            launchctl("bootout", target)
        plist.unlink(missing_ok=True)
        print("Removed the LaunchAgent. Your database remains in place.")


if __name__ == "__main__":
    main()
