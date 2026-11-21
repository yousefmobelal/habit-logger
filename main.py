"""Command-line entry point for the habit logger."""

import argparse

from commands import habit
from commands import summary
from commands import task


class _RootHelpFormatter(argparse.HelpFormatter):
    """Format root command help with the documented help column."""

    def __init__(self, prog):
        super().__init__(prog, max_help_position=16)


class _CliArgumentParser(argparse.ArgumentParser):
    """Keep invalid-choice errors stable across Python versions."""

    def _check_value(self, action, value):
        if isinstance(action.choices, dict) and value not in action.choices:
            choices = ", ".join(map(repr, action.choices))
            message = f"invalid choice: {value!r} (choose from {choices})"
            raise argparse.ArgumentError(action, message)
        super()._check_value(action, value)


def build_parser():
    """Return the root parser with all command groups registered."""
    parser = _CliArgumentParser(prog="main.py", formatter_class=_RootHelpFormatter)
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
