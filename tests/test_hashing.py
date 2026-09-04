import unittest
import tempfile
import os
from src.utils.hashing import get_file_hash

class TestHashing(unittest.TestCase):

    def test_file_hashing_consistency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "doc_original.pdf")
            file2 = os.path.join(tmpdir, "doc_renamed.pdf")

            content = b"PDF Header Dummy Content " * 5000  # ~125KB
            with open(file1, "wb") as f:
                f.write(content)

            hash1 = get_file_hash(file1)

            # Rename file and check hash identity matches
            os.rename(file1, file2)
            hash2 = get_file_hash(file2)

            self.assertEqual(hash1, hash2, "File hash must match regardless of file path or rename")

if __name__ == "__main__":
    unittest.main()
