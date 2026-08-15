# Descrição

**JoyMap** — leitor de controles de videogame para Windows.

Descobre **qual byte/bit** de cada botão de um controle muda ao ser pressionado,
comparando cada *report* HID recebido com um *baseline* (estado de repouso). Ideal
para adaptadores/genéricos que exigem mapeamento manual (PS2, Bluetooth, etc.).

Modos de leitura:
- **HID** (pywinusb): mapeamento byte/bit + diff ao vivo — `joymap.py <indice> --map`
- **XInput**: controles Xbox/360/One e GamePad Amazon — `--mode xinput`
- **DirectInput**: controles legados — `--mode dinput`
- **winmm**: joysticks via API legada — `--mode joy`

O `.exe` (build de console com PyInstaller) abre um **menu interativo** no
duplo-clique, com **auto-detecção de controles XInput** (VID `0x045E`/`0x1949`)
que redireciona para XInput em vez de travar no modo HID.

Feito/testado em Windows — *desenvolvido com [opencode](https://opencode.ai)*.
