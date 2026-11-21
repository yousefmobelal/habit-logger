"""Command-line entry point for the habit logger."""

import argparse


def build_parser():
    """Return the root argument parser."""
    return argparse.ArgumentParser(prog="main.py")


def main(argv=None):
    """Parse root arguments; subcommands are added in a later task."""
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
