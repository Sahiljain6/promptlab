import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from promptlab import storage


class UsageQuotaTests(unittest.TestCase):
    def test_quota_blocks_after_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "data" / "promptlab.db"
            with patch.object(storage, "DB_PATH", db_path):
                self.assertEqual(storage.reserve_usage_slot(limit=2, window_minutes=60), (True, 1))
                self.assertEqual(storage.reserve_usage_slot(limit=2, window_minutes=60), (True, 0))
                self.assertEqual(storage.reserve_usage_slot(limit=2, window_minutes=60), (False, 0))

    def test_invalid_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            storage.reserve_usage_slot(limit=0)


if __name__ == "__main__":
    unittest.main()
