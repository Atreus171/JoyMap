import ctypes
import ctypes.wintypes as wt
import struct

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Tipos locais (wintypes desta instalacao nao tem os handles)
HANDLE = ctypes.c_void_p
HWND = HANDLE
HINSTANCE = HANDLE
HICON = HANDLE
HCURSOR = HANDLE
HBRUSH = HANDLE
HMENU = HANDLE
LRESULT = ctypes.c_longlong
LPCWSTR = wt.LPCWSTR
HWND_MESSAGE = ctypes.c_void_p(-3)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

# Estruturas
class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wt.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", LPCWSTR),
        ("lpszClassName", LPCWSTR),
    ]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wt.USHORT),
        ("usUsage", wt.USHORT),
        ("dwFlags", wt.DWORD),
        ("hwndTarget", HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wt.DWORD),
        ("dwSize", wt.DWORD),
        ("hDevice", HANDLE),
        ("wParam", wt.WPARAM),
    ]


# Assinaturas
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
user32.RegisterClassW.restype = wt.ATOM
user32.CreateWindowExW.argtypes = [wt.DWORD, LPCWSTR, LPCWSTR, wt.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   HWND, HMENU, HINSTANCE, ctypes.c_void_p]
user32.CreateWindowExW.restype = HWND
user32.DefWindowProcW.argtypes = [HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = wt.LONG
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.restype = wt.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.GetRawInputData.argtypes = [HANDLE, wt.UINT, ctypes.c_void_p,
                                   ctypes.POINTER(wt.UINT), ctypes.c_int]
user32.GetRawInputData.restype = wt.UINT
user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE),
                                           wt.UINT, wt.UINT]
user32.RegisterRawInputDevices.restype = wt.BOOL

WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIM_TYPEHID = 2
RIDEV_INPUTSINK = 0x00000100

prev = {}


def handle_raw(hRawInput):
    sz = wt.UINT(0)
    user32.GetRawInputData(hRawInput, RID_INPUT, None, ctypes.byref(sz),
                           ctypes.sizeof(RAWINPUTHEADER))
    if sz.value == 0:
        return
    buf = ctypes.create_string_buffer(sz.value)
    res = user32.GetRawInputData(hRawInput, RID_INPUT, buf, ctypes.byref(sz),
                                 ctypes.sizeof(RAWINPUTHEADER))
    if res == 0xFFFFFFFF:
        return
    hdr = RAWINPUTHEADER.from_buffer_copy(buf[:ctypes.sizeof(RAWINPUTHEADER)])
    if hdr.dwType != RIM_TYPEHID:
        return
    off = ctypes.sizeof(RAWINPUTHEADER)
    dwSizeHid, dwCount = struct.unpack_from('<II', buf, off)
    off += 8
    for _ in range(dwCount):
        chunk = list(buf[off:off + dwSizeHid])
        off += dwSizeHid
        hexs = ' '.join(f'{b:02X}' for b in chunk)
        p = prev.get(hdr.hDevice)
        if p is None:
            print(hexs)
        else:
            diffs = []
            for i, b in enumerate(chunk):
                if b != p[i]:
                    for bit in range(8):
                        if ((b >> bit) & 1) != ((p[i] >> bit) & 1):
                            diffs.append(f"byte{i}bit{bit}")
            if diffs:
                print(hexs, "   <-- mudou:", ' '.join(diffs))
        prev[hdr.hDevice] = chunk


@WNDPROC
def wndproc(hWnd, msg, wParam, lParam):
    if msg == WM_INPUT:
        handle_raw(wt.HANDLE(lParam))
    return user32.DefWindowProcW(hWnd, msg, wParam, lParam)


def main():
    wc = WNDCLASS()
    wc.lpfnWndProc = wndproc
    wc.lpszClassName = "RawCapWnd"
    wc.hInstance = kernel32.GetModuleHandleW(None)
    if not user32.RegisterClassW(ctypes.byref(wc)):
        print("Falha registrar classe:", ctypes.get_last_error())
        return
    hwnd = user32.CreateWindowExW(0, "RawCapWnd", None, 0,
                                  0, 0, 0, 0, HWND_MESSAGE, None,
                                  kernel32.GetModuleHandleW(None), None)
    if not hwnd:
        print("Falha criar janela:", ctypes.get_last_error())
        return

    regs = [(0x01, 0x05), (0x01, 0x04), (0x01, 0x08), (0x0C, 0x01)]
    devs = (RAWINPUTDEVICE * len(regs))()
    for i, (pg, us) in enumerate(regs):
        devs[i].usUsagePage = pg
        devs[i].usUsage = us
        devs[i].dwFlags = RIDEV_INPUTSINK
        devs[i].hwndTarget = hwnd
    if not user32.RegisterRawInputDevices(devs, len(regs),
                                          ctypes.sizeof(RAWINPUTDEVICE)):
        print("Falha registrar raw input:", ctypes.get_last_error())
        return

    print("Capturando... aperte UM botao de cada vez e anote qual foi.")
    print("Ctrl+C para sair.\n")
    msg = wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nEncerrado.")
