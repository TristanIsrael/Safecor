import unittest
from safecor import FileHelper

class TestFileHelper(unittest.TestCase):

    def test_is_archive(self):
        filenames = [
            "A filename with ext.zip",
            "An archive ISO.iso",
            "A complex filename-123.00.zip",
            "a file.name.schmoll-1.0.13.zip"
        ]

        for filename in filenames:
            self.assertTrue(FileHelper.is_archive_file(filename))
