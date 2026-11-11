import threading

from safecor_emulator import MockSysUsbController

# Mapping of disk id -> root directory exposed as a source disk.
SOURCE_DISKS = {"usb0": "/Applications"}  # e.g. "C:\\" on Windows
STORAGE_PATH = "/tmp"
DESTINATION_DISK = ""

if __name__ == "__main__":
    # Requires a broker listening on localhost:1883 (e.g. run `safecor-emulator`).
    print("... Starting Mock sys-usb controller")
    lock = threading.Event()
    mockUSB = MockSysUsbController(lock)
    mockUSB.start(SOURCE_DISKS, STORAGE_PATH, DESTINATION_DISK)
    lock.wait()
    threading.Event().wait()
