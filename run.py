"""Run the agent from the command line.

  python run.py "Priya Sharma joins Monday as a designer"
  python run.py "Rahul Verma left today"
  python run.py "Priya Sharma joins as a designer" --faults mm_create_user=fail_after_once
"""
import argparse
import sys

from agent.executor import parse_faults
from agent.factory import build_runtime
from agent.reporting import render, save


def main():
    p = argparse.ArgumentParser()
    p.add_argument("request", help="the sentence from the manager")
    p.add_argument("--faults", default=None, help="e.g. mm_create_user=fail_after_once")
    p.add_argument("--auto-approve", action="store_true", help="say yes to approvals (demo/testing only)")
    args = p.parse_args()

    runtime = build_runtime(
        faults=parse_faults(args.faults) if args.faults is not None else None,
        approve=(lambda d: True) if args.auto_approve else None,
    )
    print(f"\n[agent] Processing: \"{args.request}\" ...")
    report = runtime.run(args.request)
    print(render(report))
    print("Saved:", save(report))
    sys.exit(0 if report.status == "VERIFIED" else 1)


if __name__ == "__main__":
    main()
