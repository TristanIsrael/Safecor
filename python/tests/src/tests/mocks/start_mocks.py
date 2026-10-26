from safecor_emulator import MockSysUsbController
from DevModeHelper import DevModeHelper
from MockDom0Controller import MockDom0Controller
import threading

if __name__ == "__main__":
    print("Starting mocks...")

    main_lock = threading.Event()
    lock_dom0 = threading.Event()
    lock_sys_usb = threading.Event()

    print("... Starting Mock Dom0 controller")
    dom0 = MockDom0Controller(lock_dom0)
    dom0.start(DevModeHelper.get_storage_path())
    lock_dom0.wait()

    print("... Starting Mock sys-usb controller")
    mock = MockSysUsbController(lock_sys_usb)
    mock.start({"root": DevModeHelper.get_mocked_source_disk_path()},
               DevModeHelper.get_storage_path(),
               DevModeHelper.get_mocked_destination_disk_path())
    lock_sys_usb.wait()

    print("Mocks started")

    main_lock.wait()