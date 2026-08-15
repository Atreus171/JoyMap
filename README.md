# JoyMap

[![Python 3](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Platform-Windows-0078d6.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Developed with opencode](https://img.shields.io/badge/Developed-opencode-6772AE.svg)](https://opencode.ai)

Tool for **mapping HID controllers** on Windows: it discovers which **byte/bit** of each
button of a controller/adapter changes when you press it. Useful for adapters that require
manual mapping (e.g. PS2 adapters, generic Bluetooth controllers).
It also supports reading via **XInput** (Xbox controllers) and **DirectInput** (legacy controllers).

## Requirements
- **To use the pre-built executable:** Windows only — **no Python installation needed**.
  `JoyMap.exe` is a self-contained single file (built with PyInstaller) that embeds the
  Python interpreter and all modules (`pywinusb`, etc.). Whoever downloads the release
  only needs that one file — no other files from this repo are required to run it.
- **To build/develop from source:** Python 3.x + `pip install pywinusb`.

## Installation
```
git clone https://github.com/SEU_USUARIO/joymap.git
cd joymap
pip install -r requirements.txt
```

## Usage

### Executable (without installing Python)
Use the `JoyMap.exe` in the project root (or from the release). It is a **standalone
single file** — Python and `pywinusb` are already bundled inside. Download it, double-click,
and it runs. It only uses Windows system DLLs already present on every Windows machine.

**Double-click** opens an interactive menu:
```
  1) Map HID controllers (detect byte/bit of each button)
  2) Type a command (e.g. --mode xinput, --mode dinput, 5 --map ...)
  3) Select language
  Ctrl+X to exit
```
- The **language is detected automatically** from the system (Portuguese, Spanish or
  English), but option `3` lets you switch to another one at any time.
- Choosing `1` (HID) lists the devices, asks for the **device number**, the **layout**
  and then asks **"PRESS and release the button NOW"** for each button (A, B, X, Y...),
  recording each button's byte/bit. Before the presses it shows the **order of all buttons**
  of the chosen layout, so you know which HID corresponds to which button at the end.
- Choosing `2` lets you type a command like `5 --map --layout xbox`, `--mode xinput`
  or `--mode dinput`.

> **XInput auto-detection:** Xbox controllers (VID `0x045E`) and Amazon GamePad
> (VID `0x1949`) are detected automatically. Because they **do not send RAW reports
> in HID mode**, option `1` offers to redirect to XInput reading instead of getting
> stuck on "No report received". In scripts/pipes (redirected output) without
> arguments, `hid` mode only lists the devices and exits. (Developed with
> [opencode](https://opencode.ai).)

### Python version (for development)
List HID devices:
```
python -u joymap.py
```

Open a device and watch the live diff:
```
python -u joymap.py 7
```

Guided mapping with a button layout:
```
python -u joymap.py 7 --map --layout playstation
python -u joymap.py 7 --map --layout xbox
python -u joymap.py 7 --map --layout nintendo
```

Export directly to a file (without asking):
```
python -u joymap.py 7 --map --layout playstation --export mapping_ps2
```

## Reading modes (`--mode`)
| Mode | Description | How to use |
|---|---|---|
| `hid` (default) | HID via pywinusb — byte/bit mapping and live diff | `python -u joymap.py <index>` |
| `xinput` | Xbox/360/One controllers via `xinput.dll` — shows named buttons and sticks | `python -u joymap.py --mode xinput` |
| `joy` | Joysticks via legacy `winmm` API — axes, POV and button bitmask | `python -u joymap.py --mode joy` |
| `dinput` | Legacy controllers via DirectInput `dinput8.dll` | `python -u joymap.py --mode dinput` |

> In `xinput`, `joy` and `dinput` modes, buttons come already **decoded** by the API
> (no byte/bit mapping needed).

> Running via **double-click** without arguments shows a **mode menu**. In
> scripts/pipes (redirected output), `hid` mode without arguments only lists the
> devices and exits.

### Available layouts
| Layout | Buttons asked in the test |
|---|---|
| `playstation` | X (Cross), Circle, Square, Triangle, L1, R1, L2, R2, Select/Share, Start/Options, L3, R3, PS/Home |
| `xbox` | A, B, X, Y, LB, RB, LT, RT, View, Menu, L3, R3, Guide |
| `nintendo` | B, A, Y, X, L, R, ZL, ZR, Minus, Plus, L3, R3, Home |

## How it works
The script compares each received HID report with the **idle report (baseline)**:

1. On device open, the first report becomes the **baseline** (state with nothing pressed).
2. Each new report is compared byte by byte with the baseline.
3. When you press a button, some **bytes change value**. The tool shows:
   - which **byte** changed,
   - the idle value → pressed value,
   - which **bits** were altered.

Example output:
```
BUTTON 1/13:  X (Cross)
  > detected: byte5: 0F->4F (bit6)
```
This means: when pressing X, **byte 5** goes from `0x0F` to `0x4F` — **bit6** (`0x40`) is the X button.

### Anti-remap protection
If a button's diff was already recorded in another slot, the script **ignores** it and
keeps waiting for the correct button, preventing two buttons from sharing the same mapping.

## Example result
See [`examples/mapping_example.json`](examples/mapping_example.json) for a real mapping
example from a PS2 adapter.

## JSON export
At the end of the mapping, the script asks whether you want to export. The generated JSON
(e.g. `mapping_20260814_123456.json`) contains:
```json
{
  "layout": "PlayStation (X O Square Triangle)",
  "baseline": "07 80 82 8F 6F 8C 00 00",
  "buttons": {
    "X (Cross)": "byte5: 0F->4F (bit6)",
    ...
  }
}
```

## License
MIT — see [LICENSE](LICENSE).

---

*This project was developed with [opencode](https://opencode.ai), an open-source AI
coding assistant.*
