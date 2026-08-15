# Description

**JoyMap** — video game controller reader for Windows.

It discovers **which byte/bit** of each button on a controller changes when pressed,
by comparing every received HID *report* with a *baseline* (idle state). Ideal for
adapters/generic controllers that require manual mapping (PS2, Bluetooth, etc.).

Reading modes:
- **HID** (pywinusb): byte/bit mapping + live diff — `joymap.py <index> --map`
- **XInput**: Xbox/360/One controllers and Amazon GamePad — `--mode xinput`
- **DirectInput**: legacy controllers — `--mode dinput`
- **winmm**: joysticks via legacy API — `--mode joy`

The `.exe` (console build with PyInstaller) opens an **interactive menu** on
double-click, with **automatic XInput controller detection** (VID `0x045E`/`0x1949`)
that redirects to XInput instead of getting stuck in HID mode. The **language is
detected automatically** from the system (Portuguese, Spanish or English) and can be
changed from the menu.

Built/tested on Windows — *developed with [opencode](https://opencode.ai)*.
