# JoyMap v1.2.0

Fully standalone Windows tool for **mapping game controllers via HID**: it reveals
which **byte/bit** of each button changes when you press it — perfect for PS2 adapters,
generic Bluetooth controllers and any input device that needs manual mapping.

## What's new in v1.2.0

- **Auto gamepad selection**: when exactly one gamepad is detected (e.g. `Twin USB
  Joystick`), JoyMap asks "Use this gamepad automatically? (y/N)" — press `y` and it
  opens it directly, no index needed. If there are several (or you decline), it asks
  for the index as usual.

## What's new in v1.1.1

- Guided mapping now advances to the next button automatically after **15 seconds**
  without a detected press (no more hanging when a controller streams idle reports).
- The final mapping summary shows the device identity:
  `input_device`, `input_vendor_id` and `input_product_id` (hex) — useful for configs.
- Device list marks real gamepads with `  <-- gamepad`, and a timeout explains when the
  selected HID interface isn't the gamepad (e.g. Bluetooth pairing, mouse, consumer control).
- After a timeout you can pick another device index without restarting the app.

## What's included

- **`JoyMap.exe`** — a single self-contained file. Download it, double-click, done.
  No Python or other files needed (Python interpreter + `pywinusb` are bundled).

## Features

- **Interactive menu** on double-click (device selection, guided mapping, export).
- **Automatic language detection** (Portuguese / Spanish / English) based on the OS,
  with an in-menu language switcher. Falls back to English.
- **Guided byte/bit mapping** — press each button when asked; the tool records the exact
  byte + bit for every one, and shows the full button order of the chosen layout up front.
- **XInput auto-detection** for Xbox controllers and the Amazon GamePad (VID
  `0x045E`/`0x1949`): offers redirect to XInput instead of hanging on "no report".
- **Multi-mode reading**:
  - `hid` — pywinusb raw reports (default)
  - `xinput` — Xbox controllers (`--mode xinput`)
  - `dinput` — legacy controllers (`--mode dinput`)
  - `joy` — legacy winmm joysticks (`--mode joy`)
- **JSON export** with layout, baseline and each button's mapping.
- **Anti-remap protection** — prevents two buttons from getting the same diff.

## Available layouts

| Layout | Buttons |
|---|---|
| `playstation` | X, Circle, Square, Triangle, L1-R2, Select/Share, Start/Options, L3, R3, PS/Home |
| `xbox` | A, B, X, Y, LB, RB, LT, RT, View, Menu, L3, R3, Guide |
| `nintendo` | B, A, Y, X, L, R, ZL, ZR, Minus, Plus, L3, R3, Home |

## How to use

```text
Double-click JoyMap.exe            # interactive menu
JoyMap.exe --mode xinput           # read Xbox controllers live
JoyMap.exe --mode dinput           # legacy controllers
JoyMap.exe 0 --map --layout xbox   # guided mapping (from source)
```

## Notes

- Windows only. Uses only system DLLs (`hid.dll`, `xinput.dll`, `dinput8.dll`, `winmm.dll`).
- Built with PyInstaller. Source and usage docs in the repository README.
- Developed with [opencode](https://opencode.ai).
