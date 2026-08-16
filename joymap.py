#!/usr/bin/env python3
"""JoyMap / HID live sniffer + descriptor dumper + XInput/DirectInput modes.

Usage:
  1. Make sure the BT controller is connected to THIS PC (turn the Joypad OS
     adapter off / away so it cannot grab the controller).
  2. pip install pywinusb
  3. python -u joymap.py              # list devices
     python -u joymap.py <index>      # live diff sniffer
     python -u joymap.py <index> --map  # guided button-by-button mapping

It will:
  - list matching HID devices (search by name, or press Enter to see all)
  - open the device and stream INPUT reports
  - show a baseline (first report) and then a diff per change so you can
    press each button once and read exactly which byte/bit it toggles
  - best-effort dump the HID report descriptor (usages) via hid.dll
  - XInput mode (--mode xinput) for Xbox controllers
  - DirectInput mode (--mode dinput) for legacy controllers
"""
import sys
import time
import queue as _queue

try:
    import pywinusb.hid as hid
except ImportError:
    sys.exit("pywinusb not installed. Run: pip install pywinusb")


# ---------------------------------------------------------------------------
# Cabecalho ASCII art (pixel/arcade, gradiente verde, moldura e glitch) -
# apenas visual, nao altera nenhuma logica. Sem dependencias externas.
# ---------------------------------------------------------------------------

_HEADER_VERSION = "v1.1"

# Fonte bitmap 5x7 propria, estilo pixel quadrado/robusto (nao arredondado).
_PIXEL_FONT = {
    "J": [
        "01111",
        "00010",
        "00010",
        "00010",
        "10010",
        "10010",
        "01100",
    ],
    "O": [
        "01110",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "01110",
    ],
    "Y": [
        "10001",
        "10001",
        "01010",
        "00100",
        "00100",
        "00100",
        "00100",
    ],
    "M": [
        "10001",
        "11011",
        "10101",
        "10101",
        "10001",
        "10001",
        "10001",
    ],
    "A": [
        "01110",
        "10001",
        "10001",
        "11111",
        "10001",
        "10001",
        "10001",
    ],
    "P": [
        "11110",
        "10001",
        "10001",
        "11110",
        "10000",
        "10000",
        "10000",
    ],
}

_PIXEL_CHAR = "#"
_PIXEL_ROWS = 7

# Gradiente verde 256-color (glow: centro mais claro, bordas mais escuras).
_GRAD = [28, 40, 46, 46, 46, 40, 28]


def _pixel_text(text):
    """Converte texto em grade de pixels usando a fonte bitmap 5x7.
    Retorna lista de linhas (strings) prontas para imprimir."""
    text = text.upper()
    rows = [""] * _PIXEL_ROWS
    for ch in text:
        glyph = _PIXEL_FONT.get(ch)
        if glyph is None:
            glyph = ["00000"] * _PIXEL_ROWS
        for i in range(_PIXEL_ROWS):
            row = "".join(_PIXEL_CHAR if c == "1" else " " for c in glyph[i])
            rows[i] += row + "  "
    return rows


def _enable_ansi():
    """Habilita cores ANSI no console do Windows (CMD/terminal) via ctypes."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        h = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
            kernel32.SetConsoleMode(h, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


def _term_width():
    try:
        return max(40, __import__("os").get_terminal_size().columns)
    except Exception:
        return 80


def _print_ascii_header():
    """Cabecalho arcade alinhado a esquerda: moldura, gradiente verde com glow
    e glitch de entrada (pisca/desloca antes do quadro final estavel)."""
    if not sys.stdout.isatty():
        return
    _enable_ansi()
    import random

    RESET = "\033[0m"

    def c(n):
        return "\033[1;38;5;%dm" % n

    art = _pixel_text("JoyMap")
    art_w = max(len(l.rstrip()) for l in art)
    box_w = art_w + 4  # largura da area interna da moldura

    def glitch_row(content, glitch):
        """Desloca a linha e apaga alguns pixels (efeito glitch)."""
        shift = random.randint(1, 3)
        chars = list((" " * shift + content).ljust(art_w))
        for _ in range(2 + glitch):
            pos = random.randrange(len(chars))
            if chars[pos] == _PIXEL_CHAR:
                chars[pos] = " "
        return "".join(chars)

    def make_rows(glitch=0):
        """Monta o quadro completo (moldura + arte + versao). Retorna
        lista de (linha_sem_cor, indice_da_cor)."""
        rows, cols = [], []
        rows.append("+" + "=" * (art_w + 2) + "+"); cols.append(46)
        for i, l in enumerate(art):
            content = l.rstrip()
            if glitch:
                content = glitch_row(content, glitch)
            rows.append("| " + content.ljust(art_w) + " |"); cols.append(_GRAD[i])
        rows.append("| " + "-" * art_w + " |"); cols.append(40)
        rows.append("| " + _HEADER_VERSION.ljust(art_w) + " |"); cols.append(46)
        rows.append("+" + "=" * (art_w + 2) + "+"); cols.append(46)
        return rows, cols

    def emit(plain, n):
        print(c(n) + plain + RESET, flush=True)

    frames = 3
    n_rows = len(make_rows()[0])
    for f in range(frames):
        glitch = 0 if f == frames - 1 else (1 if f == 0 else 2)
        rows, cols = make_rows(glitch)
        for plain, n in zip(rows, cols):
            emit(plain, n)
        time.sleep(0.09)
        if f < frames - 1:
            print("\033[%dA" % n_rows, end="", flush=True)  # sobe p/ redesenhar
    print()


def list_devices():
    all_devs = hid.find_all_hid_devices()
    print(f"\nFound {len(all_devs)} HID devices.\n")
    matches = []
    for i, d in enumerate(all_devs):
        name = (d.product_name or "") or "(no name)"
        vid = f"{d.vendor_id:04X}" if getattr(d, "vendor_id", None) is not None else "????"
        pid = f"{d.product_id:04X}" if getattr(d, "product_id", None) is not None else "????"
        print(f"[{i:3}] {vid}:{pid}  {name!r}")
        if "ipega" in name.lower() or "pg-" in name.lower() or "pg" == name.lower():
            matches.append((i, d))
    return all_devs, matches


def dump_descriptor(device):
    """Best-effort: parse usages via Windows hid.dll HIDP_* APIs."""
    try:
        import ctypes
        from ctypes import wintypes as wt
        h = ctypes.WinDLL("hid")
        k = ctypes.windll.kernel32

        path = device.device_path
        handle = k.CreateFileW(path, 0,
                               ctypes.wintypes.DWORD(3), None, 3, 0x40000000, None)
        if handle in (0, -1, ctypes.c_void_p(-1).value):
            print("[desc] cannot open device handle for descriptor")
            return

        prep = ctypes.c_void_p()
        if not h.HidD_GetPreparsedData(handle, ctypes.byref(prep)) or not prep:
            print(f"[desc] HidD_GetPreparsedData failed (err={k.GetLastError()})")
            k.CloseHandle(handle)
            return

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

        caps = HIDP_CAPS()
        res = h.HidP_GetCaps(prep, ctypes.byref(caps))
        if res != 0:
            print(f"[desc] HidP_GetCaps failed (err={k.GetLastError()}, ret={res})")
            k.CloseHandle(handle)
            return

        print("\n=== HIDP_CAPS ===")
        print(f"  Top UsagePage=0x{caps.UsagePage:04X} Usage=0x{caps.Usage:04X}")
        print(f"  InputReportByteLength={caps.InputReportByteLength}")
        print(f"  #InputButtonCaps={caps.NumberInputButtonCaps} "
              f"#InputValueCaps={caps.NumberInputValueCaps}")

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

        print("\n=== BUTTON CAPS (input) ===")
        bcount = caps.NumberInputButtonCaps or 1
        bbuf = (CAP * bcount)()
        length = ctypes.c_ulong(bcount)
        if h.HidP_GetButtonCaps(0, ctypes.byref(bbuf), ctypes.byref(length), prep) == 0:
            for c in bbuf[:min(length.value, 8)]:
                if c.IsRange:
                    umin, umax = c.u.Range[0], c.u.Range[1]
                else:
                    umin = umax = c.u.NotRange[0]
                print(f"  ReportID={c.ReportID} Page=0x{c.UsagePage:04X} "
                      f"BitField=0x{c.BitField:04X} Usage {umin}..{umax} range={bool(c.IsRange)}")
        else:
            print("  (HidP_GetButtonCaps returned error)")

        print("\n=== VALUE CAPS (input) ===")
        vcount = caps.NumberInputValueCaps or 1
        vbuf = (CAP * vcount)()
        length = ctypes.c_ulong(vcount)
        if h.HidP_GetValueCaps(0, ctypes.byref(vbuf), ctypes.byref(length), prep) == 0:
            for c in vbuf[:min(length.value, 16)]:
                if c.IsRange:
                    umin, umax = c.u.Range[0], c.u.Range[1]
                else:
                    umin = umax = c.u.NotRange[0]
                print(f"  ReportID={c.ReportID} Page=0x{c.UsagePage:04X} "
                      f"Usage=0x{umin:04X} BitField=0x{c.BitField:04X} "
                      f"Logical={c.LogicalMin}..{c.LogicalMax} range={bool(c.IsRange)}")
        else:
            print("  (HidP_GetValueCaps returned error)")

        k.CloseHandle(handle)
    except Exception as e:
        print(f"[desc] descriptor dump skipped: {e}")


XINPUT_VENDORS = {0x045E, 0x1949}  # Microsoft (Xbox), Amazon (Fire gamepad)


def _is_xinput_device(name, vid):
    """Detecta controles que só falam XInput (nao enviam reports RAW em modo HID)."""
    n = (name or "").lower()
    if "xbox" in n or "360" in n or "xbox one" in n:
        return True
    if vid is not None and vid in XINPUT_VENDORS:
        return True
    return False


def changed_vs_baseline(baseline, b):
    diffs = []
    for i in range(max(len(b), len(baseline))):
        ob = baseline[i] if i < len(baseline) else 0
        nb = b[i] if i < len(b) else 0
        if ob != nb:
            changed = ob ^ nb
            bits = [f"bit{j}" for j in range(8) if changed & (1 << j)]
            diffs.append(f"byte{i}: {ob:02X}->{nb:02X} ({'+'.join(bits)})")
    return diffs


LAYOUTS = {
    "xbox": {
        "name": "Xbox (A B X Y)",
        "labels": ["A", "B", "X", "Y", "LB", "RB", "LT", "RT",
                   "View", "Menu", "L3", "R3", "Guide"],
    },
    "playstation": {
        "name": "PlayStation (X O Square Triangle)",
        "labels": ["X (Cross)", "Circle", "Square", "Triangle",
                   "L1", "R1", "L2", "R2",
                   "Select/Share", "Start/Options", "L3", "R3", "PS/Home"],
    },
    "nintendo": {
        "name": "Nintendo (B A Y X)",
        "labels": ["B", "A", "Y", "X",
                   "L", "R", "ZL", "ZR",
                   "Minus", "Plus", "L3", "R3", "Home"],
    },
}


LANG_CODES = ("pt", "es", "en")

LANGS = {
    "pt": {
        "name": "Português",
        "choose_lang": "Escolha o idioma:",
        "lang_opt": "  {n}) {name}",
        "lang_prompt": "Idioma (1-3) [1]: ",
        "lang_detected": "Idioma detectado: {name}",
        "menu_title": "JoyMap - leitor de controles",
        "menu_map": "Mapear controles HID (detectar byte/bit de cada botao)",
        "menu_cmd": "Digitar comando (ex: --mode xinput, --mode dinput, 5 --map ...)",
        "menu_lang": "Selecionar idioma",
        "menu_exit": "Ctrl+X para sair",
        "menu_prompt": "Escolha uma opcao: ",
        "menu_invalid": "Opcao invalida. Tente de novo.",
        "cmd_prompt": "Digite o comando (ex: --mode dinput, --mode joy, 5 --map --layout xbox; Enter=menu, Ctrl+X=sai): ",
        "dev_prompt": "Digite o numero do dispositivo para abrir (Ctrl+X para sair): ",
        "dev_invalid": "Numero invalido. Tente de novo.",
        "xinput_hint": "[dica] dispositivo Xbox/XInput detectado. Em modo HID ele pode NAO emitir reports; se quiser, pode ler via XInput.",
        "xinput_ask": "Ler em tempo real via XInput em vez disso? (s/n): ",
        "xinput_warn": "[aviso] Xbox/XInput: use --mode xinput (modo HID nao le este controle).",
        "opening": "Abrindo: {name}",
        "guide_intro": "Modo mapeamento guia: vamos mapear os botoes um por um. (Ctrl+X para cancelar)",
        "choose_layout": "Escolha o layout do controle:",
        "layout_prompt": "Layout (1-{n}) [1]: ",
        "layout_unknown": "Layout '{key}' desconhecido. Usando xbox.",
        "no_report": "Nenhum report recebido. Confira se o controle esta conectado.",
        "baseline": "BASELINE (repouso)",
        "layout_label": "Layout",
        "button": "BOTAO {i}/{total}:  {label}",
        "press_btn": "APERTE e solte o botao AGORA.",
        "countd": "começa em {c}...",
        "detected": "detectado: {sig}",
        "dup": "ATENCAO: diff ja mapeado em [{btn}] - ignorado (anti-remapeamento).",
        "dup_hint": "Aperte OUTRO botao ou o correto deste slot.",
        "nothing": "NADA (nao altera este report)",
        "final_header": "  MAPEAMENTO FINAL",
        "export_ask": "Exportar resultado em JSON? (s/N): ",
        "exported": "Exportado para: {path}",
        "open_fail": "Falha ao abrir dispositivo: {err}",
        "usage": {
            "list": "  python -u joymap.py",
            "single": "  python -u joymap.py <index>",
            "map": "  python -u joymap.py <index> --map [--layout xbox|playstation|nintendo]",
        },
    },
    "es": {
        "name": "Español",
        "choose_lang": "Elija el idioma:",
        "lang_opt": "  {n}) {name}",
        "lang_prompt": "Idioma (1-3) [1]: ",
        "lang_detected": "Idioma detectado: {name}",
        "menu_title": "JoyMap - lector de controles",
        "menu_map": "Mapear controles HID (detectar byte/bit de cada botón)",
        "menu_cmd": "Escribir comando (ej: --mode xinput, --mode dinput, 5 --map ...)",
        "menu_lang": "Seleccionar idioma",
        "menu_exit": "Ctrl+X para salir",
        "menu_prompt": "Elija una opción: ",
        "menu_invalid": "Opción inválida. Inténtelo de nuevo.",
        "cmd_prompt": "Escriba el comando (ej: --mode dinput, --mode joy, 5 --map --layout xbox; Enter=menú, Ctrl+X=sale): ",
        "dev_prompt": "Escriba el número del dispositivo para abrir (Ctrl+X para salir): ",
        "dev_invalid": "Número inválido. Inténtelo de nuevo.",
        "xinput_hint": "[aviso] dispositivo Xbox/XInput detectado. En modo HID quizás NO envíe reports; si quiere, puede leer por XInput.",
        "xinput_ask": "¿Leer en tiempo real por XInput en su lugar? (s/n): ",
        "xinput_warn": "[aviso] Xbox/XInput: use --mode xinput (el modo HID no lee este control).",
        "opening": "Abriendo: {name}",
        "guide_intro": "Modo de mapeo guiado: mapearemos los botones uno por uno. (Ctrl+X para cancelar)",
        "choose_layout": "Elija la distribución del control:",
        "layout_prompt": "Distribución (1-{n}) [1]: ",
        "layout_unknown": "Distribución '{key}' desconocida. Usando xbox.",
        "no_report": "No se recibió ningún report. Verifique que el control esté conectado.",
        "baseline": "BASELINE (en reposo)",
        "layout_label": "Distribución",
        "button": "BOTÓN {i}/{total}:  {label}",
        "press_btn": "PRESIONE y suelte el botón AHORA.",
        "countd": "empieza en {c}...",
        "detected": "detectado: {sig}",
        "dup": "ATENCIÓN: diff ya asignado a [{btn}] - ignorado (anti-reasignación).",
        "dup_hint": "PRESIONE OTRO botón o el correcto para esta ranura.",
        "nothing": "NADA (no modifica este report)",
        "final_header": "  MAPEO FINAL",
        "export_ask": "¿Exportar resultado en JSON? (s/N): ",
        "exported": "Exportado a: {path}",
        "open_fail": "Fallo al abrir dispositivo: {err}",
        "usage": {
            "list": "  python -u joymap.py",
            "single": "  python -u joymap.py <index>",
            "map": "  python -u joymap.py <index> --map [--layout xbox|playstation|nintendo]",
        },
    },
    "en": {
        "name": "English",
        "choose_lang": "Choose the language:",
        "lang_opt": "  {n}) {name}",
        "lang_prompt": "Language (1-3) [1]: ",
        "lang_detected": "Detected language: {name}",
        "menu_title": "JoyMap - game controller reader",
        "menu_map": "Map HID controllers (detect byte/bit of each button)",
        "menu_cmd": "Type a command (e.g. --mode xinput, --mode dinput, 5 --map ...)",
        "menu_lang": "Select language",
        "menu_exit": "Ctrl+X to exit",
        "menu_prompt": "Choose an option: ",
        "menu_invalid": "Invalid option. Try again.",
        "cmd_prompt": "Type a command (e.g. --mode dinput, --mode joy, 5 --map --layout xbox; Enter=menu, Ctrl+X=exit): ",
        "dev_prompt": "Type the device number to open (Ctrl+X to exit): ",
        "dev_invalid": "Invalid number. Try again.",
        "xinput_hint": "[hint] Xbox/XInput device detected. In HID mode it may NOT send reports; you can read via XInput instead.",
        "xinput_ask": "Read live via XInput instead? (y/n): ",
        "xinput_warn": "[warn] Xbox/XInput: use --mode xinput (HID mode cannot read this controller).",
        "opening": "Opening: {name}",
        "guide_intro": "Guided mapping mode: let's map the buttons one by one. (Ctrl+X to cancel)",
        "choose_layout": "Choose the controller layout:",
        "layout_prompt": "Layout (1-{n}) [1]: ",
        "layout_unknown": "Unknown layout '{key}'. Using xbox.",
        "no_report": "No report received. Check that the controller is connected.",
        "baseline": "BASELINE (idle)",
        "layout_label": "Layout",
        "button": "BUTTON {i}/{total}:  {label}",
        "press_btn": "PRESS and release the button NOW.",
        "countd": "starting in {c}...",
        "detected": "detected: {sig}",
        "dup": "WARNING: diff already mapped to [{btn}] - ignored (anti-remap).",
        "dup_hint": "Press ANOTHER button or the correct one for this slot.",
        "nothing": "NOTHING (this report unchanged)",
        "final_header": "  FINAL MAPPING",
        "export_ask": "Export result as JSON? (y/N): ",
        "exported": "Exported to: {path}",
        "open_fail": "Failed to open device: {err}",
        "usage": {
            "list": "  python -u joymap.py",
            "single": "  python -u joymap.py <index>",
            "map": "  python -u joymap.py <index> --map [--layout xbox|playstation|nintendo]",
        },
    },
}


def _detect_system_lang():
    """Detecta o idioma do sistema (Windows). Fallback: 'en'."""
    try:
        import ctypes
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        prim = lcid & 0x3FF  # Primary Language ID (bits 0-9)
        pt = prim == 0x16 or lcid in (0x0816,)
        if pt:
            return "pt"
        if prim == 0x0A:
            return "es"
        if prim == 0x09:
            return "en"
    except Exception:
        pass
    try:
        import locale
        loc = locale.getdefaultlocale()[0] or ""
        low = loc.lower()
        if low.startswith("pt"):
            return "pt"
        if low.startswith("es"):
            return "es"
        if low.startswith("en"):
            return "en"
    except Exception:
        pass
    return "en"


def export_json(mapping, layout, lang, fname=None, baseline=None):
    """Export result to JSON (auto if fname given, else asks)."""
    if fname is None:
        try:
            ans = input("\n" + lang["export_ask"]).strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = ""
        if ans not in ("s", "y", "sim", "yes"):
            print()
            return
        from datetime import datetime
        fname = f"mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    if not fname.lower().endswith(".json"):
        fname += ".json"

    import json
    data = {
        "layout": layout["name"],
        "baseline": baseline.hex(" ") if baseline else None,
        "buttons": {},
    }
    for k, v in mapping.items():
        data["buttons"][k] = v
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(lang["exported"].format(path=fname) + "\n")


def get_layout(layout_name, lang):
    """Return layout dict from name, or ask interactively if None."""
    if layout_name is not None:
        key = layout_name.lower()
        if key in LAYOUTS:
            return LAYOUTS[key]
        print(lang["layout_unknown"].format(key=key))
        return LAYOUTS["xbox"]
    print("\n" + lang["choose_layout"])
    keys = list(LAYOUTS)
    for i, k in enumerate(keys, 1):
        print(lang["lang_opt"].format(n=i, name=LAYOUTS[k]["name"]))
    try:
        n = int(input(lang["layout_prompt"].format(n=len(keys)).strip() or "1"))
    except (ValueError, EOFError):
        n = 1
    return LAYOUTS[keys[n - 1] if 1 <= n <= len(keys) else 0]


def guided_map(dev, layout, lang, export_file=None, interativo=False):
    """Prompts the user to press each button; records the exact byte/bit."""
    q = _queue.Queue()

    def on_data(data):
        q.put(bytes(data))

    dev.set_raw_data_handler(on_data)

    baseline = None
    deadline = time.time() + 30
    hint = False
    print("\n  Aguardando report do controle...", flush=True)
    while baseline is None:
        if time.time() > deadline:
            print("\n  [aviso] nenhum report HID chegou. Se for controle Xbox/XInput,\n"
                  "          pode não emitir reports em modo HID.\n", flush=True)
            if interativo:
                try:
                    want = input("  Ler via XInput em vez disso? (s/n): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    want = ""
                if want in ("s", "sim", "y", "yes"):
                    xinput_live()
                    return
                else:
                    print("  Reabra e use a opcao 2) (XInput) ou escolha um controle nao-Xbox.\n")
            else:
                print("  Use: python -u joymap.py --mode xinput")
            return
        try:
            first = q.get(timeout=0.5)
        except _queue.Empty:
            if not hint and time.time() > 5:
                hint = True
                print("\n  [dica] o controle pode so enviar report quando voce aperta algo.\n"
                      "         Aperte e solte QUALQUER botao agora para gerar o baseline.\n", flush=True)
            continue
        # O primeiro report pode ser de um botao apertado. Coleta por ~1.5s para
        # o estado ocioso (botoes soltos) virar o baseline correto.
        last = first
        settle = time.time() + 1.5
        while time.time() < settle:
            try:
                last = q.get(timeout=0.3)
            except _queue.Empty:
                pass
        baseline = last
    print(f"\n{lang['baseline']}: {baseline.hex(' ')}", flush=True)
    print(f"{lang['layout_label']}: {layout['name']}\n", flush=True)

    # Orientacao: lista todos os botoes do layout escolhido de uma vez
    print("=" * 52, flush=True)
    print("  ORDEM DOS BOTOES deste layout — ao final voce sabera o HID de cada:", flush=True)
    print("=" * 52, flush=True)
    for i, lbl in enumerate(layout["labels"], 1):
        print(f"    {i:2d}) {lbl}", flush=True)
    print("=" * 52 + "\n", flush=True)

    labels = layout["labels"]
    mapping = {}

    def wait_idle(timeout):
        """Waits until stream returns to baseline (buttons all released)."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                b = q.get(timeout=0.3)
            except _queue.Empty:
                continue
            if not changed_vs_baseline(baseline, b):
                return True
        return False

    wait_idle(3)
    total = len(labels)
    used = {}  # diff -> button already mapped (proteção anti-remapeamento)

    for i, label in enumerate(labels, 1):
        print("\n" + "=" * 52, flush=True)
        print("  " + lang["button"].format(i=i, total=total, label=label), flush=True)
        print("=" * 52, flush=True)
        # countdown only on the first button
        if i == 1:
            for c in range(4, 0, -1):
                print("    " + lang["countd"].format(c=c), flush=True)
                time.sleep(1)
        print("  " + lang["press_btn"] + "\n", flush=True)

        wait_idle(2)  # discard whatever is held from positioning
        _detect_timeout = 15
        pressed_report = None
        try:
            while True:
                b = q.get(timeout=_detect_timeout)  # waits until data arrives
                d = changed_vs_baseline(baseline, b)
                if d:
                    sig = " | ".join(d)
                    if sig in used:
                        # já mapeado para outro botão -> não remapear
                        print("  > " + lang["dup"].format(btn=used[sig]), flush=True)
                        print("    " + lang["dup_hint"], flush=True)
                        continue  # keep waiting; doesn't overwrite
                    pressed_report = sig
                    print("  > " + lang["detected"].format(sig=pressed_report), flush=True)
                    break  # go to next button immediately
        except _queue.Empty:
            pass

        if pressed_report is None:
            print("  > " + lang["nothing"], flush=True)
        else:
            used[pressed_report] = label  # registra p/ não remapear depois
        mapping[label] = pressed_report
        wait_idle(1)

    print("\n\n" + "=" * 52, flush=True)
    print(lang["final_header"], flush=True)
    print("=" * 52, flush=True)
    for k, v in mapping.items():
        print(f"  {k:14s} -> {v}", flush=True)
    print("=" * 52, flush=True)

    export_json(mapping, layout, lang, export_file, baseline=baseline)


def xinput_live():
    """Le controles compatíveis com XInput (Xbox) via xinput.dll."""
    import ctypes
    lib = None
    for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
        try:
            lib = ctypes.WinDLL(name)
            break
        except OSError:
            continue
    if lib is None:
        print("XInput não disponível neste Windows.")
        return

    class XINPUT_GAMEPAD(ctypes.Structure):
        _fields_ = [
            ("wButtons", ctypes.c_ushort),
            ("bLeftTrigger", ctypes.c_ubyte),
            ("bRightTrigger", ctypes.c_ubyte),
            ("sThumbLX", ctypes.c_short),
            ("sThumbLY", ctypes.c_short),
            ("sThumbRX", ctypes.c_short),
            ("sThumbRY", ctypes.c_short),
        ]

    class XINPUT_STATE(ctypes.Structure):
        _fields_ = [("dwPacketNumber", ctypes.c_ulong), ("Gamepad", XINPUT_GAMEPAD)]

    fn = lib.XInputGetState
    fn.restype = ctypes.c_ulong
    fn.argtypes = [ctypes.c_uint, ctypes.POINTER(XINPUT_STATE)]

    BTN = {
        0x0001: "DPAD-UP", 0x0002: "DPAD-DOWN", 0x0004: "DPAD-LEFT", 0x0008: "DPAD-RIGHT",
        0x0010: "Start", 0x0020: "Select", 0x0040: "L3", 0x0080: "R3",
        0x0100: "LB", 0x0200: "RB",
        0x1000: "A", 0x2000: "B", 0x4000: "X", 0x8000: "Y",
    }
    any_connected = False
    print("\nXInput: lendo slots 0-3. Aperte Ctrl+C para sair.\n")
    try:
        while True:
            for slot in range(4):
                st = XINPUT_STATE()
                r = fn(slot, ctypes.byref(st))
                if r != 0:
                    continue
                any_connected = True
                g = st.Gamepad
                names = [n for m, n in BTN.items() if g.wButtons & m]
                line = (f"slot{slot}: {'+'.join(names) if names else '(nenhum botao)'} | "
                        f"LX={g.sThumbLX:6d} LY={g.sThumbLY:6d} | "
                        f"RX={g.sThumbRX:6d} RY={g.sThumbRY:6d} | "
                        f"LT={g.bLeftTrigger:3d} RT={g.bRightTrigger:3d}")
                print(line, flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nencerrado")
    if not any_connected:
        print("Nenhum controle XInput conectado.")


def joy_live():
    """Le controles via API legada winmm (joystick)."""
    import ctypes
    try:
        winmm = ctypes.WinDLL("winmm")
    except OSError as e:
        print("winmm não disponível:", e)
        return

    class JOYINFOEX(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
            ("dwXpos", ctypes.c_ulong), ("dwYpos", ctypes.c_ulong),
            ("dwZpos", ctypes.c_ulong), ("dwRpos", ctypes.c_ulong),
            ("dwUpos", ctypes.c_ulong), ("dwVpos", ctypes.c_ulong),
            ("dwButtons", ctypes.c_ulong), ("dwButtonNumber", ctypes.c_ulong),
            ("dwPOV", ctypes.c_ulong), ("dwReserved1", ctypes.c_ulong),
            ("dwReserved2", ctypes.c_ulong),
        ]

    joyGetNumDevs = winmm.joyGetNumDevs
    joyGetNumDevs.restype = ctypes.c_uint
    joyGetPosEx = winmm.joyGetPosEx
    joyGetPosEx.restype = ctypes.c_uint
    joyGetPosEx.argtypes = [ctypes.c_uint, ctypes.POINTER(JOYINFOEX)]

    JOY_RETURNALL = 0x000000FF
    n = joyGetNumDevs()
    print(f"\nJoysticks (winmm): {n} suportado(s).")
    ids = []
    for i in range(32):
        ji = JOYINFOEX()
        ji.dwSize = ctypes.sizeof(JOYINFOEX)
        ji.dwFlags = JOY_RETURNALL
        if joyGetPosEx(i, ctypes.byref(ji)) == 0:
            ids.append(i)
    if not ids:
        print("Nenhum joystick via winmm (talvez o controle seja so XInput/HID).")
        return
    print("IDs detectados:", ids, "\nAperte Ctrl+C para sair.\n")
    try:
        while True:
            for i in ids:
                ji = JOYINFOEX()
                ji.dwSize = ctypes.sizeof(JOYINFOEX)
                ji.dwFlags = JOY_RETURNALL
                if joyGetPosEx(i, ctypes.byref(ji)) != 0:
                    continue
                print(f"joy{i}: X={ji.dwXpos:5d} Y={ji.dwYpos:5d} Z={ji.dwZpos:5d} "
                      f"R={ji.dwRpos:5d} U={ji.dwUpos:5d} V={ji.dwVpos:5d} "
                      f"POV={ji.dwPOV:5d} BTN=0x{ji.dwButtons:08X}", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nencerrado")


def dinput_live():
    """Le controles via DirectInput (dinput8.dll), para controles legados
    (PS2/PS3, joysticks USB) que xinput nao enxerga."""
    import ctypes
    try:
        dinput = ctypes.WinDLL("dinput8")
    except OSError as e:
        print("dinput8 nao disponivel:", e)
        return

    MAX_PATH = 260

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

        def __str__(self):
            b = bytes(self.Data4)
            return (f"{self.Data1:08X}-{self.Data2:04X}-{self.Data3:04X}-"
                    f"{b[0]:02X}{b[1]:02X}-{bytes(b[2:]).hex()}")

    def mkg(d1, d2=0, d3=0, d4=(0, 0, 0, 0, 0, 0, 0, 0)):
        return GUID(d1, d2, d3, (ctypes.c_ubyte * 8)(*d4))

    IID_DI8W = GUID(0xBF798031, 0x483A, 0x4DA2,
                    (ctypes.c_ubyte * 8)(0xAA, 0x99, 0x5D, 0x64, 0xED, 0x36, 0x97, 0x00))

    class DIDEVICEINSTANCEW(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong),
            ("guidInstance", GUID),
            ("guidProduct", GUID),
            ("dwDevType", ctypes.c_ulong),
            ("tszInstanceName", ctypes.c_wchar * MAX_PATH),
            ("tszProductName", ctypes.c_wchar * MAX_PATH),
            ("guidFFDriver", GUID),
            ("wUsagePage", ctypes.c_ushort),
            ("wUsage", ctypes.c_ushort),
        ]

    gmod = ctypes.WinDLL("kernel32").GetModuleHandleW
    gmod.restype = ctypes.c_void_p

    d8create = dinput.DirectInput8Create
    d8create.restype = ctypes.c_long
    d8create.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                         ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p),
                         ctypes.c_void_p]
    pp = ctypes.c_void_p()
    hr = d8create(gmod(None), 0x0800, ctypes.byref(IID_DI8W), ctypes.byref(pp), None)
    if hr != 0 or not pp.value:
        print(f"DirectInput8Create falhou (hr=0x{hr & 0xFFFFFFFF:08X}).")
        return

    def method(vtbl_pointer, idx, restype, argtypes):
        fp = vtbl_pointer[idx]
        return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(fp)

    vtbl_addr = ctypes.cast(pp.value, ctypes.POINTER(ctypes.c_void_p))[0]
    vtable = ctypes.cast(vtbl_addr, ctypes.POINTER(ctypes.c_void_p))
    DI8DEVCLASS_GAMECTRL = 0x00000004
    DIEDFL_ATTACHEDONLY = 0x00000001

    devices = []

    def enum_cb(di, pv):
        inst = di.contents
        name = (inst.tszProductName or inst.tszInstanceName).strip() or "(sem nome)"
        devices.append([inst.guidInstance, name])
        return 0  # DIENUM_CONTINUE

    DIENUMCB = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.POINTER(DIDEVICEINSTANCEW), ctypes.c_void_p)
    enum_fn = method(vtable, 4, ctypes.c_long,
                     [ctypes.c_ulong, DIENUMCB, ctypes.c_void_p, ctypes.c_ulong])
    hr = enum_fn(pp.value, DI8DEVCLASS_GAMECTRL, DIENUMCB(enum_cb), None,
                 DIEDFL_ATTACHEDONLY)
    if hr != 0:
        print(f"EnumDevices falhou (hr=0x{hr & 0xFFFFFFFF:08X}).")
        return

    if not devices:
        print("\nNenhum dispositivo DirectInput de controle (gamepad/joystick) conectado.")
        return

    print("\nDispositivos DirectInput detectados:")
    for i, (g, name) in enumerate(devices):
        print(f"  [{i}] {name}")
    if len(devices) > 1:
        try:
            n = int(input("\nEscolha um (indice): ").strip())
        except (ValueError, EOFError):
            n = 0
        if not (0 <= n < len(devices)):
            n = 0
    else:
        n = 0
    guid_instance, dev_name = devices[n]
    print(f"\nAbrindo: {dev_name!r}\n")

    iface = ctypes.c_void_p()
    create_dev = method(vtable, 3, ctypes.c_long,
                        [ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p),
                         ctypes.c_void_p])
    hr = create_dev(pp.value, ctypes.byref(guid_instance), ctypes.byref(iface), None)
    if hr != 0 or not iface.value:
        print(f"CreateDevice falhou (hr=0x{hr & 0xFFFFFFFF:08X}).")
        return

    dv_vtbl_addr = ctypes.cast(iface.value, ctypes.POINTER(ctypes.c_void_p))[0]
    dv_vtable = ctypes.cast(dv_vtbl_addr, ctypes.POINTER(ctypes.c_void_p))

    def dmeth(idx, restype, argtypes):
        return method(dv_vtable, idx, restype, argtypes)

    class DIOBJECTDATAFORMAT(ctypes.Structure):
        _fields_ = [
            ("pguid", ctypes.POINTER(GUID)),
            ("dwOfs", ctypes.c_ulong),
            ("dwType", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
        ]

    class DIDATAFORMAT(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong),
            ("dwObjSize", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("dwDataSize", ctypes.c_ulong),
            ("dwNumObjs", ctypes.c_ulong),
            ("rgodf", ctypes.POINTER(DIOBJECTDATAFORMAT)),
        ]

    class DIJOYSTATE(ctypes.Structure):
        _fields_ = [
            ("lX", ctypes.c_long), ("lY", ctypes.c_long),
            ("lZ", ctypes.c_long), ("lRx", ctypes.c_long),
            ("lRy", ctypes.c_long), ("lRz", ctypes.c_long),
            ("rglSlider", ctypes.c_long * 2),
            ("rgdwPOV", ctypes.c_ulong * 4),
            ("rgbButtons", ctypes.c_ubyte * 32),
        ]

    G_X = mkg(0xA36D02E0, 0xC9F3, 0x11CF, (0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00))
    G_Y = mkg(0xA36D02E1, 0xC9F3, 0x11CF, (0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00))
    G_Z = mkg(0xA36D02E2, 0xC9F3, 0x11CF, (0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00))
    G_RX = mkg(0xA36D02F4, 0xC9F3, 0x11CF, (0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00))
    G_RY = mkg(0xA36D02F5, 0xC9F3, 0x11CF, (0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00))
    G_RZ = mkg(0xA36D02E3, 0xC9F3, 0x11CF, (0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00))
    G_SLIDER = mkg(0xA36D02E4, 0xC9F3, 0x11CF, (0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00))
    G_BTN = mkg(0xA36D02F0, 0xC9F3, 0x11CF, (0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00))
    G_POV = mkg(0xA36D02F2, 0xC9F3, 0x11CF, (0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00))

    DIDFT_OPTIONAL = 0x80000000
    DIDFT_ANYINSTANCE = 0x00FF0000
    DIDFT_AXIS = 0x00000003
    DIDFT_BUTTON = 0x0000000C
    DIDFT_POV = 0x00000030
    DIF_ABSAXIS = 0x00000001

    objs = []
    for ofs, g in [(0, G_X), (4, G_Y), (8, G_Z), (12, G_RX), (16, G_RY), (20, G_RZ)]:
        objs.append(DIOBJECTDATAFORMAT(ctypes.pointer(g), ofs,
                                       DIDFT_AXIS | DIDFT_ANYINSTANCE | DIDFT_OPTIONAL,
                                       DIF_ABSAXIS))
    for nsl in range(2):
        objs.append(DIOBJECTDATAFORMAT(ctypes.pointer(G_SLIDER), 24 + 4 * nsl,
                                       DIDFT_AXIS | DIDFT_ANYINSTANCE | DIDFT_OPTIONAL,
                                       DIF_ABSAXIS))
    for npov in range(4):
        objs.append(DIOBJECTDATAFORMAT(ctypes.pointer(G_POV), 32 + 4 * npov,
                                       DIDFT_POV | DIDFT_ANYINSTANCE | DIDFT_OPTIONAL, 0))
    for nbtn in range(32):
        objs.append(DIOBJECTDATAFORMAT(ctypes.pointer(G_BTN), 48 + nbtn,
                                       DIDFT_BUTTON | DIDFT_ANYINSTANCE | DIDFT_OPTIONAL, 0))

    Arr = DIOBJECTDATAFORMAT * len(objs)
    arr = Arr(*objs)
    df = DIDATAFORMAT(ctypes.sizeof(DIDATAFORMAT),
                      ctypes.sizeof(DIOBJECTDATAFORMAT),
                      0, ctypes.sizeof(DIJOYSTATE), len(objs),
                      ctypes.cast(arr, ctypes.POINTER(DIOBJECTDATAFORMAT)))

    set_fmt = dmeth(11, ctypes.c_long, [ctypes.POINTER(DIDATAFORMAT)])
    hr = set_fmt(iface.value, ctypes.byref(df))
    if hr != 0:
        print(f"SetDataFormat faltou? hr=0x{hr & 0xFFFFFFFF:08X}. "
              "Talvez o controle exija outro formato.")
        return

    set_coop = dmeth(13, ctypes.c_long, [ctypes.c_void_p, ctypes.c_ulong])
    hr = set_coop(iface.value, None, 0x00000004 | 0x00000002)  # BG | NONEXCLUSIVE
    acquire = dmeth(7, ctypes.c_long, [])
    hr = acquire(iface.value)
    if hr != 0 and hr != 0x80070005:  # falha pouca importa; reacquire no loop
        pass

    get_state = dmeth(9, ctypes.c_long, [ctypes.c_ulong, ctypes.c_void_p])

    def pov_str(p):
        if p == 0xFFFFFFFF:
            return "C"
        return f"{p / 100.0:.0f}g"

    print("Lendo (Ctrl+C para sair).\n")
    last = None
    try:
        while True:
            st = DIJOYSTATE()
            hr = get_state(iface.value, ctypes.sizeof(st), ctypes.byref(st))
            if hr != 0:
                acquire(iface.value)
                time.sleep(0.1)
                continue
            pressed = [str(i) for i in range(32) if st.rgbButtons[i]]
            povs = "/".join(pov_str(p) for p in st.rgdwPOV)
            line = (f"X={st.lX:6d} Y={st.lY:6d} Z={st.lZ:6d} "
                    f"RX={st.lRx:6d} RY={st.lRy:6d} RZ={st.lRz:6d} "
                    f"S0={st.rglSlider[0]:6d} S1={st.rglSlider[1]:6d} "
                    f"POV=[{povs}] BTN={'+'.join(pressed) or '(nenhum)'}")
            if line != last:
                print(line, flush=True)
                last = line
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            dmeth(2, ctypes.c_ulong, [])(iface.value)
        except Exception:
            pass
        print("\nencerrado")


MODES = {
    "hid": "HID (pywinusb) - mapeamento byte/bit",
    "xinput": "XInput - controles Xbox (xinput.dll)",
    "joy": "Joystick legado (winmm)",
    "dinput": "DirectInput - controles legados (dinput8.dll)",
}


def build_parser():
    import argparse
    p = argparse.ArgumentParser(
        prog="joymap",
        description="Leitor/mapeador de controles para Windows. "
                    "Descobre qual byte/bit de cada botao do controle.",
        epilog="Exemplos:\n"
               "  python -u joymap.py\n"
               "  python -u joymap.py 7\n"
               "  python -u joymap.py 7 --map --layout playstation\n"
               "  python -u joymap.py --mode xinput\n"
               "  python -u joymap.py --mode joy\n"
               "  python -u joymap.py --mode dinput",
    )
    p.add_argument("index", nargs="?", type=int,
                   help="indice do dispositivo HID (omitir para listar os dispositivos)")
    p.add_argument("--mode", choices=list(MODES), default=None,
                   help=f"modo de leitura: {', '.join(MODES)} (se omitido, pergunta no menu)")
    p.add_argument("--map", action="store_true",
                   help="modo mapeamento guiado (aperte cada botao para registrar o byte/bit)")
    p.add_argument("--layout", choices=list(LAYOUTS), default=None,
                   help=f"layout dos botoes: {', '.join(LAYOUTS)} (se omitido, pergunta)")
    p.add_argument("--export", metavar="ARQUIVO",
                   help="exportar o mapeamento para ARQUIVO.json (sem perguntar)")
    return p


def _pause_if_console(msg="Pressione Enter para fechar..."):
    """Mantém a janela do console aberta quando a saída vai para um console
    visível (ex.: duplo-clique no .exe). Baseia-se em stdout (não stdin), que
    é fiável para detectar se há uma console real mostrando o texto."""
    try:
        if sys.stdout.isatty():
            print()
            input(msg)
    except Exception:
        pass


def _menu_principal(lang):
    """Menu interativo exibido no duplo-clique.
    Retorna ("modo", <modo>) | ("cmd", None) | ("lang", None) | None para sair (Ctrl+X)."""
    items = [
        ("1", lang["menu_map"]),
        ("2", lang["menu_cmd"]),
        ("3", lang["menu_lang"]),
    ]
    while True:
        print("\n" + "=" * 52)
        print("  " + lang["menu_title"])
        print("=" * 52)
        for k, d in items:
            print(f"  {k}) {d}")
        print("  " + lang["menu_exit"])
        print("=" * 52)
        try:
            r = input("\n" + lang["menu_prompt"])
        except (EOFError, KeyboardInterrupt):
            return None
        # Ctrl+X (0x18) ou Ctrl+C (0x03) como caractere sai
        if r == "\x18" or r == "\x03":
            return None
        r = r.strip()
        if r == "":
            continue  # Enter soa -> volta pro menu (nao fecha)
        if r == "3":
            return ("lang", None)
        if r == "2":
            return ("cmd", None)
        if r == "1":
            return ("modo", "hid")
        if r in ("q", "quit"):
            return None
        print("  " + lang["menu_invalid"])


def _escolher_idioma(lang):
    """Pergunta o idioma (pt/es/en) e retorna o codigo escolhido.
    Entrada invalida ou vazia mantem o idioma atual (lang) - nunca reverte
    silenciosamente para outro idioma."""
    codes = LANG_CODES
    # o codigo atual eh a chave correspondente ao dict `lang`
    current = LANG_CODES[0]
    for code in codes:
        if LANGS[code] is lang:
            current = code
            break
    while True:
        print("\n" + "=" * 52)
        print("  " + lang["choose_lang"])
        print("=" * 52)
        for i, code in enumerate(codes, 1):
            print(lang["lang_opt"].format(n=i, name=LANGS[code]["name"]))
        print("=" * 52)
        try:
            raw = input("\n" + lang["lang_prompt"].strip())
        except (EOFError, KeyboardInterrupt):
            return current
        raw = raw.strip()
        if raw == "":
            return current
        try:
            n = int(raw)
        except ValueError:
            print("  " + lang["menu_invalid"])
            continue
        if 1 <= n <= len(codes):
            return codes[n - 1]
        print("  " + lang["menu_invalid"])


def run(args, lang=None):
    """Dispatch logica a partir de args parseados. Reusavel pelo menu
    'digitar comando'."""
    if lang is None:
        lang = LANGS[_detect_system_lang()]
    interativo = sys.stdout.isatty()

    if args.mode == "xinput":
        xinput_live()
        return
    if args.mode == "joy":
        joy_live()
        return
    if args.mode == "dinput":
        dinput_live()
        return

    all_devs, _ = list_devices()

    if args.index is None:
        if not interativo:
            print("\nUso: " + lang["usage"]["map"])
            return
        # HID interativo (menu): pede o indice (Ctrl+X sai)
        while True:
            try:
                raw = input("\n" + lang["dev_prompt"])
            except (EOFError, KeyboardInterrupt):
                return
            if raw == "\x18" or raw == "\x03":
                return
            raw = raw.strip()
            if not raw:
                continue  # Enter vazio -> pergunta de novo
            try:
                args.index = int(raw)
                break
            except ValueError:
                print("  " + lang["dev_invalid"])

    if not (0 <= args.index < len(all_devs)):
        print(f"Indice {args.index} fora do intervalo (0..{len(all_devs)-1}).")
        _pause_if_console()
        return
    dev = all_devs[args.index]

    name = getattr(dev, "product_name", "") or ""
    vid = getattr(dev, "vendor_id", None)
    if _is_xinput_device(name, vid):
        if interativo:
            # Xbox/XInput pode nao emitir reports em modo HID; oferece XInput,
            # mas se o usuario disser "nao", segue para o mapeamento HID normal.
            print("\n  " + lang["xinput_hint"] + "\n")
            try:
                want = input("         " + lang["xinput_ask"]).strip().lower()
            except (EOFError, KeyboardInterrupt):
                want = ""
            if want in ("s", "sim", "y", "yes"):
                xinput_live()
                return
            # respondeu "nao": continua para o mapeamento HID
        else:
            print("  " + lang["xinput_warn"])

    print(f"\n{lang['opening'].format(name=dev.product_name)}")
    try:
        dev.open()
    except Exception as e:
        _pause_if_console()
        sys.exit(lang["open_fail"].format(err=e))

    if args.map or args.export:
        layout = get_layout(args.layout, lang)
        try:
            guided_map(dev, layout, lang, export_file=args.export, interativo=interativo)
        finally:
            dev.close()
        _pause_if_console()
        return

    if interativo:
        # duplo-clique: vai direto para mapeamento guia (precione A, B, X, ...)
        print("\n" + lang["guide_intro"])
        layout = get_layout(args.layout, lang)
        try:
            guided_map(dev, layout, lang, interativo=interativo)
        finally:
            dev.close()
        _pause_if_console()
        return

    dump_descriptor(dev)

    baseline = None
    last = None
    count = [0]

    def on_data(data):
        nonlocal baseline, last
        count[0] += 1
        b = bytes(data)
        if baseline is None:
            baseline = b
            last = b
            print(f"\nBASELINE (idle): {b.hex(' ')}")
            print("Pressione um botao, solte, e veja a linha CHANGED.\n")
            return
        if b != last:
            diffs = []
            for i in range(max(len(b), len(baseline))):
                ob = baseline[i] if i < len(baseline) else 0
                nb = b[i] if i < len(b) else 0
                if ob != nb:
                    changed = ob ^ nb
                    bits = [f"bit{j}" for j in range(8) if changed & (1 << j)]
                    diffs.append(f"byte{i}: {ob:02X}->{nb:02X} ({'+'.join(bits)})")
            print(f"CHANGED: {b.hex(' ')}  " + " | ".join(diffs))
        last = b

    dev.set_raw_data_handler(on_data)
    print("\nRodando ate Ctrl+C (recebendo reports...)\n")
    warned = False
    idle_for = [0]
    try:
        while True:
            time.sleep(2)
            if count[0] == 0:
                idle_for[0] += 2
                if not warned and idle_for[0] >= 6:
                    warned = True
                    print("\n  [aviso] nenhum report HID chegou. Se for controle Xbox, use:\n"
                          "          JoyMap.exe --mode xinput   (Xbox nao envia reports em modo HID)\n",
                          flush=True)
            else:
                idle_for[0] = 0
            print(f"  [recebidos ate agora: {count[0]}]", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()
        print("\nencerrado")


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Nenhum modo e nenhum indice: menu principal (duplo-clique)
    if args.mode is None and args.index is None:
        if sys.stdout.isatty():
            _print_ascii_header()
            lang = LANGS[_detect_system_lang()]
            print(lang["lang_detected"].format(name=lang["name"]) + "\n")
            while True:
                choice = _menu_principal(lang)
                if choice is None:
                    return
                kind, val = choice
                if kind == "lang":
                    lang = LANGS[_escolher_idioma(lang)]
                    continue
                if kind == "modo":
                    args.mode = val
                    run(args, lang=lang)
                    return
                # kind == "cmd": digitar comando
                try:
                    raw_cmd = input("\n" + lang["cmd_prompt"]).strip()
                except (EOFError, KeyboardInterrupt):
                    raw_cmd = ""
                # Ctrl+X para sair do comando
                if raw_cmd in ("\x18", "\x03"):
                    return
                if not raw_cmd:
                    continue
                import shlex
                # parse tolerante: comando invalido nao aborta o app
                real_stderr = sys.stderr
                try:
                    extra = parser.parse_args(shlex.split(raw_cmd))
                except SystemExit:
                    sys.stderr = real_stderr
                    print(lang["menu_invalid"])
                    continue
                finally:
                    sys.stderr = real_stderr
                # mescla: comando digitado sobrescreve modo/indice do menu
                if extra.mode is not None:
                    args.mode = extra.mode
                else:
                    args.mode = None
                args.index = extra.index if extra.index is not None else args.index
                args.map = args.map or extra.map
                args.export = extra.export or args.export
                if extra.layout is not None:
                    args.layout = extra.layout
                run(args, lang=lang)
                return
        else:
            all_devs, _ = list_devices()
            print("\nUso: " + LANGS[_detect_system_lang()]["usage"]["map"])
            return

    run(args, lang=LANGS[_detect_system_lang()])


if __name__ == "__main__":
    main()
