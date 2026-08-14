#!/usr/bin/env python3
"""Direct HID reader + descriptor dumper (own handle, ReadFile loop)."""
import sys
import ctypes
from ctypes import wintypes as wt

try:
    import pywinusb.hid as hid
except ImportError:
    sys.exit("pip install pywinusb")

h = ctypes.WinDLL("hid")
k = ctypes.windll.kernel32

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", ctypes.c_ushort),
        ("UsagePage", ctypes.c_ushort),
        ("InputReportByteLength", ctypes.c_ushort),
        ("OutputReportByteLength", ctypes.c_ushort),
        ("FeatureReportByteLength", ctypes.c_ushort),
        ("Reserved", ctypes.c_ushort * 17),
        ("NumberLinkCollectionNodes", ctypes.c_ushort),
        ("NumberInputButtonCaps", ctypes.c_ushort),
        ("NumberInputValueCaps", ctypes.c_ushort),
        ("NumberInputDataIndices", ctypes.c_ushort),
        ("NumberOutputButtonCaps", ctypes.c_ushort),
        ("NumberOutputValueCaps", ctypes.c_ushort),
        ("NumberOutputDataIndices", ctypes.c_ushort),
        ("NumberFeatureButtonCaps", ctypes.c_ushort),
        ("NumberFeatureValueCaps", ctypes.c_ushort),
        ("NumberFeatureDataIndices", ctypes.c_ushort),
    ]


U = ctypes.c_ushort * 6
class Rng(ctypes.Union):
    _fields_ = [("Range", U), ("NotRange", U)]
class CAP(ctypes.Structure):
    _fields_ = [
        ("UsagePage", ctypes.c_ushort),
        ("ReportID", ctypes.c_ubyte),
        ("IsAlias", ctypes.c_ubyte),
        ("BitField", ctypes.c_ushort),
        ("LinkCollection", ctypes.c_ushort),
        ("LinkUsage", ctypes.c_ushort),
        ("LinkUsagePage", ctypes.c_ushort),
        ("IsRange", ctypes.c_ubyte),
        ("IsStringRange", ctypes.c_ubyte),
        ("IsDesignatorRange", ctypes.c_ubyte),
        ("IsAbsolute", ctypes.c_ubyte),
        ("Reserved", ctypes.c_ulong * 10),
        ("u", Rng),
        ("LogicalMin", ctypes.c_ulong),
        ("LogicalMax", ctypes.c_ulong),
        ("PhysicalMin", ctypes.c_ulong),
        ("PhysicalMax", ctypes.c_ulong),
        ("UnitsExp", ctypes.c_ushort),
        ("Units", ctypes.c_ushort),
    ]


def dump_device(dev):
    print(f"\n=== {dev.product_name!r}  {dev.vendor_id:04X}:{dev.product_id:04X} ===")
    path = dev.device_path
    handle = k.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                           FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                           OPEN_EXISTING, 0, None)
    if handle in (0, -1, ctypes.c_void_p(-1).value, 0xFFFFFFFFFFFFFFFF):
        print("  CreateFile failed err=", k.GetLastError())
        return
    prep = ctypes.c_void_p()
    if not h.HidD_GetPreparsedData(handle, ctypes.byref(prep)) or not prep:
        print("  HidD_GetPreparsedData failed err=", k.GetLastError())
        k.CloseHandle(handle)
        return
    caps = HIDP_CAPS()
    r = h.HidP_GetCaps(prep, ctypes.byref(caps))
    page = caps.UsagePage
    print(f"  Top UsagePage=0x{page:04X} Usage=0x{caps.Usage:04X}  "
          f"(InputLen={caps.InputReportByteLength} Btn={caps.NumberInputButtonCaps} Val={caps.NumberInputValueCaps})")
    if page == 0x0001:
        print("  -> GAME PAD (good)")
    elif page == 0x000C:
        print("  -> CONSUMER CONTROL (media keys - this is the bad one)")

    if r == 0 or True:
        print("  BUTTON CAPS:", flush=True)
        bc = max(caps.NumberInputButtonCaps, 1)
        bb = (CAP * bc)()
        ln = ctypes.c_ulong(bc)
        rb = h.HidP_GetButtonCaps(0, ctypes.byref(bb), ctypes.byref(ln), prep)
        print(f"    (ret=0x{rb:X}, count={ln.value})", flush=True)
        for c in bb[:max(int(ln.value), 1)]:
            umin, umax = (c.u.Range[0], c.u.Range[1]) if c.IsRange else (c.u.NotRange[0], c.u.NotRange[0])
            print(f"    RID={c.ReportID} Page=0x{c.UsagePage:04X} Bit=0x{c.BitField:04X} Usage {umin}..{umax} range={bool(c.IsRange)}")
        print("  VALUE CAPS:", flush=True)
        vc = max(caps.NumberInputValueCaps, 1)
        vb = (CAP * vc)()
        ln = ctypes.c_ulong(vc)
        rv = h.HidP_GetValueCaps(0, ctypes.byref(vb), ctypes.byref(ln), prep)
        print(f"    (ret=0x{rv:X}, count={ln.value})", flush=True)
        for c in vb[:max(int(ln.value), 1)]:
            umin, umax = (c.u.Range[0], c.u.Range[1]) if c.IsRange else (c.u.NotRange[0], c.u.NotRange[0])
            print(f"    RID={c.ReportID} Page=0x{c.UsagePage:04X} Usage=0x{umin:04X} Bit=0x{c.BitField:04X} Log={c.LogicalMin}..{c.LogicalMax} range={bool(c.IsRange)}")
    k.CloseHandle(handle)


def main():
    devs = hid.find_all_hid_devices()
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        print(f"{len(devs)} HID devices:\n")
        for i, d in enumerate(devs):
            try:
                name = d.product_name or ""
                vid = d.vendor_id; pid = d.product_id
            except Exception:
                continue
            print(f"[{i:3}] {vid:04X}:{pid:04X}  {name!r}")
        print("\nDumping UsagePage of each (look for 0x0001 vs 0x000C):\n")
        for d in devs:
            try:
                dump_device(d)
            except Exception as e:
                print("  (skip)", e)
        return

    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        idx = int(sys.argv[1])
        if idx < 0 or idx >= len(devs):
            print(f"index {idx} out of range (0..{len(devs)-1})")
            return
        dump_device(devs[idx])
        return

    # default: just list
    print(f"{len(devs)} HID devices:\n")
    for i, d in enumerate(devs):
        name = d.product_name or ""
        print(f"[{i:3}] {d.vendor_id:04X}:{d.product_id:04X}  {name!r}")
    print("\nUsage:")
    print("  python -u hid_read.py            # list devices")
    print("  python -u hid_read.py <index>    # dump one device's collection")
    print("  python -u hid_read.py --all      # dump UsagePage of ALL devices")


if __name__ == "__main__":
    main()
