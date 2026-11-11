#!/usr/bin/env python3
import os
import random
import shutil
import string
import subprocess
import sys
import tempfile

# Constants
MIN_FILE_SIZE = 1 * 1024  # 1 KiB
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MiB
ARCHIVE_RATIO = 0.1  # 10%
ARCHIVE_DEPTH = 10
MAX_ARCHIVE_FILE_SIZE = 2 * 1024 * 1024  # 2 MiB

ARCHIVE_FORMATS = ["zip", "7z", "gz", "bzip2", "xz", "lz4"]


def random_filename(ext="bin"):
    name = "".join(random.choices(string.ascii_letters + string.digits, k=10))
    return f"{name}.{ext}"


def random_file(path, size):
    with open(path, "wb") as f:
        f.write(os.urandom(size))
    print(f"Created file: {path} ({size} bytes)")


def create_nested_tree(base_dir, max_size, files_per_level=2):
    current_dir = base_dir
    for depth in range(ARCHIVE_DEPTH):
        next_dir = os.path.join(current_dir, f"level_{depth}")
        os.makedirs(next_dir, exist_ok=True)
        for _ in range(files_per_level):
            fpath = os.path.join(next_dir, random_filename())
            fsize = random.randint(MIN_FILE_SIZE, min(max_size, MAX_ARCHIVE_FILE_SIZE))
            random_file(fpath, fsize)
        current_dir = next_dir


def create_archive(archive_path, format_name):
    with tempfile.TemporaryDirectory() as tempdir:
        print(f"Creating archive content in: {tempdir}")
        create_nested_tree(tempdir, MAX_ARCHIVE_FILE_SIZE)
        base = os.path.splitext(archive_path)[0]

        if format_name == "zip":
            # shutil.make_archive automatically appends .zip
            temp_zip = shutil.make_archive(base, "zip", tempdir)
            os.rename(temp_zip, archive_path)
            print(f"Created ZIP archive: {archive_path}")
        elif format_name == "7z":
            result = subprocess.run(
                ["7zz", "a", archive_path, tempdir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode == 0:
                print(f"Created 7z archive: {archive_path}")
            else:
                print(f"7z creation failed: {result.stderr.decode()}")
        elif format_name == "gz":
            result = subprocess.run(
                ["tar", "-czf", archive_path, tempdir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode == 0:
                print(f"Created GZ archive: {archive_path}")
            else:
                print(f"GZ creation failed: {result.stderr.decode()}")
        elif format_name == "bzip2":
            result = subprocess.run(
                ["tar", "-cjf", archive_path, tempdir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode == 0:
                print(f"Created BZIP2 archive: {archive_path}")
            else:
                print(f"BZIP2 creation failed: {result.stderr.decode()}")
        elif format_name == "xz":
            result = subprocess.run(
                ["tar", "cJf", archive_path, tempdir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode == 0:
                print(f"Created XZ archive: {archive_path}")
            else:
                print(f"XZ creation failed: {result.stderr.decode()}")
        elif format_name == "lz4":
            result = subprocess.run(
                ["tar", "--lzma", "-cf", archive_path, tempdir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode == 0:
                print(f"Created LZ4 archive: {archive_path}")
            else:
                print(f"LZ4 creation failed: {result.stderr.decode()}")


def main(target_dir):
    if not os.path.isdir(target_dir):
        print(f"Error: Target directory '{target_dir}' does not exist.")
        sys.exit(1)

    print(f"Starting file generation in: {target_dir}")
    count = 0
    try:
        while True:
            if random.random() < ARCHIVE_RATIO:
                ext = random.choice(ARCHIVE_FORMATS)
                fname = random_filename(ext=ext)
                archive_path = os.path.join(target_dir, fname)
                print(f"\nGenerating archive #{count + 1}: {fname} ({ext})")
                create_archive(archive_path, ext)
            else:
                size = random.randint(MIN_FILE_SIZE, MAX_FILE_SIZE)
                fname = random_filename("bin")
                fpath = os.path.join(target_dir, fname)
                random_file(fpath, size)
            count += 1
            if count % 10 == 0:
                print(f"\n[Progress] {count} files created...\n")
    except OSError as e:
        print(f"\n[Stopped] Disk full or write error after {count} files: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 generate_files.py <target_directory>")
        sys.exit(1)
    main(sys.argv[1])
