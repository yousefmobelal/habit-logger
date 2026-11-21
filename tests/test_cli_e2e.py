"""Expose the CLI end-to-end suite under the name used in issue #9."""

from tests.test_cli import (
    CliTestCase,
    CrossInvocationTests,
    EmptyDatabaseTests,
    HelpAndEntryPointTests,
    InvalidInputTests,
)

__all__ = [
    "CliTestCase",
    "CrossInvocationTests",
    "EmptyDatabaseTests",
    "HelpAndEntryPointTests",
    "InvalidInputTests",
]


if __name__ == "__main__":
    import unittest

    unittest.main()
