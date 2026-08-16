#!/usr/bin/env python3
"""Portable timeout runner — spawns child process with configurable timeout.
Returns: 0 on success, 124 on timeout, child exit code otherwise.
"""
import sys, subprocess, signal, time, os

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("cmd", nargs=argparse.REMAINDER)
    args = p.parse_args()

    if not args.cmd:
        print("Usage: run_with_timeout.py --timeout N -- cmd args...")
        sys.exit(2)
    # Strip leading '--' if present (argparse REMAINDER captures it)
    if args.cmd[0] == "--":
        args.cmd = args.cmd[1:]

    proc = subprocess.Popen(args.cmd)
    deadline = time.time() + args.timeout

    try:
        while time.time() < deadline:
            try:
                ret = proc.wait(timeout=0.5)
                sys.exit(ret)
            except subprocess.TimeoutExpired:
                continue
        # Timeout reached
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        sys.exit(124)
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()
        sys.exit(130)

if __name__ == "__main__":
    main()
