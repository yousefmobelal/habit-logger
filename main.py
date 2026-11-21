"""Command-line entry point for the habit logger."""

import argparse

from commands import habit
from commands import summary
from commands import task


def build_parser():
    """Return the root argument parser with task commands registered."""
    parser = argparse.ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    task.register(subparsers)
    habit.register(subparsers)
    summary.register(subparsers)
    return parser


def main(argv=None):
    """Parse root arguments and dispatch a selected command handler."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
