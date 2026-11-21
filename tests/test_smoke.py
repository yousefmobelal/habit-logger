"""Smoke test proving the unittest suite is discoverable."""

import unittest


class SmokeTests(unittest.TestCase):
    def test_smoke(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
