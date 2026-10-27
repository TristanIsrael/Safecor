import unittest
import os
import io
import tempfile
import shutil
import hashlib
import unittest.mock as mock

from safecor import FileHelper, Constants


class TestFileHelper(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="safecor_fh_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- is_archive_file -------------------------------------------------

    def test_is_archive_positive(self):
        for filename in [
            "A filename with ext.zip",
            "An archive ISO.iso",
            "A complex filename-123.00.zip",
            "a file.name.schmoll-1.0.13.zip",
            "backup.tar.gz",
            "pkg.deb",
            "archive.7z",
        ]:
            self.assertTrue(FileHelper.is_archive_file(filename), filename)

    def test_is_archive_negative(self):
        for filename in [
            "a normal file.txt",
            "image.png",
            "no extension",
            "",
        ]:
            self.assertFalse(FileHelper.is_archive_file(filename), filename)

    # --- calculate_fingerprint ------------------------------------------

    def test_calculate_fingerprint(self):
        path = os.path.join(self.tmp, "f.txt")
        data = b"hello world"
        with open(path, "wb") as f:
            f.write(data)

        expected = hashlib.md5(data).hexdigest()
        self.assertEqual(FileHelper.calculate_fingerprint(path), expected)

    def test_calculate_fingerprint_missing_file(self):
        self.assertEqual(FileHelper.calculate_fingerprint(os.path.join(self.tmp, "nope.txt")), "")

    # --- create_file / remove_file --------------------------------------

    def test_create_file_empty(self):
        path = os.path.join(self.tmp, "empty.bin")
        FileHelper.create_file(path, 0)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(os.path.getsize(path), 0)

    def test_create_file_with_size(self):
        path = os.path.join(self.tmp, "data.bin")
        FileHelper.create_file(path, 2)  # 2 KiB
        self.assertEqual(os.path.getsize(path), 2 * 1024)

    def test_remove_file(self):
        path = os.path.join(self.tmp, "to_remove.txt")
        with open(path, "w") as f:
            f.write("x")
        self.assertTrue(FileHelper.remove_file(path))
        self.assertFalse(os.path.exists(path))

    def test_remove_file_missing(self):
        self.assertFalse(FileHelper.remove_file(os.path.join(self.tmp, "ghost.txt")))

    # --- get_disks_list -------------------------------------------------

    def test_get_disks_list(self):
        for d in ["disk_a", "disk_b"]:
            os.makedirs(os.path.join(self.tmp, d))
        with open(os.path.join(self.tmp, "notadir"), "w") as f:
            f.write("x")

        with mock.patch.object(Constants, "USB_MOUNT_POINT", self.tmp):
            disks = FileHelper.get_disks_list()

        self.assertCountEqual(sorted(disks), ["disk_a", "disk_b"])

    # --- get_folder_contents --------------------------------------------

    def _make_tree(self, root):
        with open(os.path.join(root, "a.txt"), "w") as f:
            f.write("x")
        os.makedirs(os.path.join(root, "sub"))
        with open(os.path.join(root, "sub", "b.txt"), "w") as f:
            f.write("y")

    def _names(self, contents):
        return sorted(e["name"] for e in contents)

    def test_get_folder_contents_non_recursive(self):
        self._make_tree(self.tmp)
        contents = []
        FileHelper.get_folder_contents(self.tmp, contents, cutting=len(self.tmp), recursive=False)
        self.assertEqual(self._names(contents), ["a.txt", "sub"])
        self.assertTrue(any(e["type"] == "file" for e in contents))
        self.assertTrue(any(e["type"] == "folder" for e in contents))

    def test_get_folder_contents_recursive(self):
        self._make_tree(self.tmp)
        contents = []
        FileHelper.get_folder_contents(self.tmp, contents, cutting=len(self.tmp), recursive=True)
        self.assertEqual(self._names(contents), ["a.txt", "b.txt", "sub"])

        b = [e for e in contents if e["name"] == "b.txt"][0]
        self.assertEqual(b["path"], "/sub")
        self.assertEqual(b["size"], 1)

    def test_get_folder_contents_with_filter(self):
        self._make_tree(self.tmp)
        contents = []
        FileHelper.get_folder_contents(
            self.tmp, contents, cutting=len(self.tmp), recursive=True, name_filter=["*.txt"]
        )
        # Filters return only matching files, no folders
        self.assertEqual(self._names(contents), ["a.txt", "b.txt"])
        self.assertTrue(all(e["type"] == "file" for e in contents))

    def test_get_folder_contents_symlink_skipped(self):
        self._make_tree(self.tmp)
        os.symlink(os.path.join(self.tmp, "a.txt"), os.path.join(self.tmp, "link.txt"))
        contents = []
        FileHelper.get_folder_contents(self.tmp, contents, cutting=len(self.tmp), recursive=False)
        self.assertNotIn("link.txt", self._names(contents))

    # --- get_files_list (mount point mocked) ----------------------------

    def test_get_files_list_recursive(self):
        self._make_tree(self.tmp)
        with mock.patch.object(FileHelper, "get_mount_point", return_value=self.tmp):
            files = FileHelper.get_files_list("diskX", recursive=True)
        self.assertEqual(self._names(files), ["a.txt", "b.txt", "sub"])

    def test_get_files_list_with_filter(self):
        self._make_tree(self.tmp)
        with mock.patch.object(FileHelper, "get_mount_point", return_value=self.tmp):
            files = FileHelper.get_files_list("diskX", recursive=True, name_filter=["*.txt"])
        self.assertEqual(self._names(files), ["a.txt", "b.txt"])

    def test_get_files_list_no_mount_point(self):
        with mock.patch.object(FileHelper, "get_mount_point", return_value=None):
            self.assertEqual(FileHelper.get_files_list("missing-disk", recursive=True), [])

    # --- get_mount_point -------------------------------------------------

    def test_get_mount_point_found(self):
        mounts = "tmpfs /tmp tmpfs 0 0\n/dev/sda1 /media/usb/disk1 ext4 0 0\n/dev/loop0 /media/loop/foo squashfs 0 0\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=mounts)):
            self.assertEqual(FileHelper.get_mount_point("disk1"), "/media/usb/disk1")

    def test_get_mount_point_not_found(self):
        mounts = "/dev/sda1 /media/usb/disk1 ext4 0 0\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=mounts)):
            self.assertIsNone(FileHelper.get_mount_point("nope"))

    def test_get_mount_point_ignores_short_lines(self):
        mounts = "malformed\n/dev/sda1 /media/usb/disk1 ext4 0 0\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=mounts)):
            self.assertEqual(FileHelper.get_mount_point("disk1"), "/media/usb/disk1")

    # --- copy_file -------------------------------------------------------

    def test_copy_file_success(self):
        src = os.path.join(self.tmp, "src")
        dst = os.path.join(self.tmp, "dst")
        os.makedirs(src)
        os.makedirs(dst)
        with open(os.path.join(src, "a.txt"), "wb") as f:
            f.write(b"copy me")

        src_fp = FileHelper.calculate_fingerprint(os.path.join(src, "a.txt"))
        result = FileHelper.copy_file(src, "/a.txt", dst, src_fp)
        self.assertEqual(result, src_fp)
        self.assertTrue(os.path.exists(os.path.join(dst, "a.txt")))

    def test_copy_file_fingerprint_mismatch(self):
        src = os.path.join(self.tmp, "src")
        dst = os.path.join(self.tmp, "dst")
        os.makedirs(src)
        os.makedirs(dst)
        with open(os.path.join(src, "a.txt"), "wb") as f:
            f.write(b"copy me")

        result = FileHelper.copy_file(src, "/a.txt", dst, "not-the-right-fingerprint")
        self.assertEqual(result, "")

    def test_copy_file_source_missing(self):
        src = os.path.join(self.tmp, "src")
        dst = os.path.join(self.tmp, "dst")
        os.makedirs(src)
        os.makedirs(dst)
        result = FileHelper.copy_file(src, "/ghost.txt", dst, "whatever")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
