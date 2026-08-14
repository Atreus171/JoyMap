#!/usr/bin/env python3
"""Dump everything from the iPega PG-9021 in one shot (correct HIDP structs)."""
import ctypes
import pywinusb.hid as hid

h = ctypes.WinDLL("hid")
k = ctypes.windll.kernel32


class CAP(ctypes.Structure):
    _fields_ = [
        ("UsagePage", ctypes.c_ushort), ("ReportID", ctypes.c_ubyte), ("IsAlias", ctypes.c_ubyte),
        ("BitField", ctypes.c_ushort), ("LinkCollection", ctypes.c_ushort),
        ("LinkUsage", ctypes.c_ushort), ("LinkUsagePage", ctypes.c_ushort),
        ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte),
        ("IsDesignatorRange", ctypes.c_ubyte), ("IsAbsolute", ctypes.c_ubyte),
        ("Reserved", ctypes.c_ulong * 10),
        ("Rng", ctypes.c_ushort * 8),
        ("StringMin", ctypes.c_ushort), ("StringMax", ctypes.c_ushort),
        ("DesignatorMin", ctypes.c_ushort), ("DesignatorMax", ctypes.c_ushort),
        ("DataIndexMin", ctypes.c_ushort), ("DataIndexMax", ctypes.c_ushort),
        ("PhysicalMin", ctypes.c_ulong), ("PhysicalMax", ctypes.c_ulong),
        ("LogicalMin", ctypes.c_ulong), ("LogicalMax", ctypes.c_ulong),
        ("UnitsExp", ctypes.c_ulong), ("Units", ctypes.c_ulong),
        ("ReportCount", ctypes.c_ulong), ("ReportSize", ctypes.c_ushort), ("Reserved2", ctypes.c_ushort),
    ]


class CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", ctypes.c_ushort), ("UsagePage", ctypes.c_ushort),
        ("InputReportByteLength", ctypes.c_ushort), ("OutputReportByteLength", ctypes.c_ushort),
        ("FeatureReportByteLength", ctypes.c_ushort), ("Reserved", ctypes.c_ushort * 17),
        ("NumberLinkCollectionNodes", ctypes.c_ushort),
        ("NumberInputButtonCaps", ctypes.c_ushort), ("NumberInputValueCaps", ctypes.c_ushort),
        ("NumberInputDataIndices", ctypes.c_ushort),
        ("NumberOutputButtonCaps", ctypes.c_ushort), ("NumberOutputValueCaps", ctypes.c_ushort),
        ("NumberOutputDataIndices", ctypes.c_ushort),
        ("NumberFeatureButtonCaps", ctypes.c_ushort), ("NumberFeatureValueCaps", ctypes.c_ushort),
        ("NumberFeatureDataIndices", ctypes.c_ushort),
    ]


USAGE_NAME = {
    0x30: "X (LX)", 0x31: "Y (LY)", 0x32: "Z", 0x35: "RZ",
    0x33: "RX", 0x34: "RY", 0x39: "HAT", 0x01: "PTR", 0x02: "MOUSE",
    0x05: "GAME_PAD", 0x08: "MULTI_AXIS", 0xC4: "ACCEL", 0xC5: "BRAKE",
}


def dump_one(d):
    print("---", repr(d.product_name), "0x%04X:0x%04X" % (d.vendor_id, d.product_id))
    handle = k.CreateFileW(d.device_path, 0, 3, None, 3, 0, None)
    if handle in (0, -1, ctypes.c_void_p(-1).value):
        print("  open fail err=", k.GetLastError())
        return
    prep = ctypes.c_void_p()
    if not h.HidD_GetPreparsedData(handle, ctypes.byref(prep)):
        print("  preparse fail err=", k.GetLastError())
        k.CloseHandle(handle)
        return
    caps = CAPS()
    h.HidP_GetCaps(prep, ctypes.byref(caps))
    print("  Top page=0x%04X usage=0x%04X in_len=%d valcaps=%d btncaps=%d" % (
        caps.UsagePage, caps.Usage, caps.InputReportByteLength,
        caps.NumberInputValueCaps, caps.NumberInputButtonCaps))

    if caps.NumberInputValueCaps:
        vb = (CAP * caps.NumberInputValueCaps)()
        ln = ctypes.c_ulong(caps.NumberInputValueCaps)
        r = h.HidP_GetValueCaps(0, ctypes.byref(vb), ctypes.byref(ln), prep)
        print("  VALUE caps ret=0x%X count=%d" % (r, ln.value))
        for i, c in enumerate(vb[:int(ln.value)]):
            umin, umax = c.Rng[0], c.Rng[1]
            nm = USAGE_NAME.get(umin, "?")
            print("   [%d] RID=%d Page=0x%04X Usage=0x%04X(%s) Size=%d Log=%d..%d DatIdx=%d..%d" % (
                i, c.ReportID, c.UsagePage, umin, nm, c.ReportSize,
                c.LogicalMin, c.LogicalMax, c.DataIndexMin, c.DataIndexMax))

    if caps.NumberInputButtonCaps:
        bb = (CAP * caps.NumberInputButtonCaps)()
        ln = ctypes.c_ulong(caps.NumberInputButtonCaps)
        r = h.HidP_GetButtonCaps(0, ctypes.byref(bb), ctypes.byref(ln), prep)
        print("  BUTTON caps ret=0x%X count=%d" % (r, ln.value))
        for c in bb[:int(ln.value)]:
            umin, umax = c.Rng[0], c.Rng[1]
            print("   RID=%d Page=0x%04X Usage=%d..%d range=%d" % (
                c.ReportID, c.UsagePage, umin, umax, c.IsRange))
    k.CloseHandle(handle)


def main():
    devs = hid.find_all_hid_devices()
    print(len(devs), "devices")
    found = False
    for d in devs:
        if d.vendor_id == 0x1949 and d.product_id == 0x0402:
            dump_one(d)
            found = True
    if not found:
        print("iPega 1949:0402 NOT connected")


if __name__ == "__main__":
    main()
