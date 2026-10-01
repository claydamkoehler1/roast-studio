"""Check native linking without requiring a USB bus on a hosted CI runner."""
import ctypes
import ctypes.util
import libusb_package


def main():
    candidates = [libusb_package.find_library('usb-1.0'),
                  libusb_package.find_library('libusb-1.0'),
                  ctypes.util.find_library('usb-1.0')]
    for name in dict.fromkeys(filter(None, candidates)):
        try:
            library = ctypes.CDLL(name)
            assert hasattr(library, 'libusb_init')
            assert hasattr(library, 'libusb_bulk_transfer')
            print('Native libusb library linked successfully.')
            return
        except (OSError, AssertionError):
            continue
    raise SystemExit('No compatible libusb shared library could be loaded.')


if __name__ == '__main__':
    main()
