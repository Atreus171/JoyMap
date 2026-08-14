# JoyMap

[![Python 3](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Platform-Windows-0078d6.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Developed with opencode](https://img.shields.io/badge/Desenvolvido-opencode-6772AE.svg)](https://opencode.ai)

Ferramenta para **mapear controles HID** no Windows: descobre qual **byte/bit** de cada botão de um controle/adaptador muda quando você aperta. Útil para adaptadores que exigem mapeamento manual (ex.: adaptadores PS2, controles Bluetooth genéricos).
Também suporta leitura via **XInput** (controles Xbox) e **DirectInput** (controles legados).

## Requisitos
- Windows (usa `hid.dll` via `pywinusb`, `xinput.dll`, `dinput8.dll`, `winmm.dll`)
- Python 3.x
- `pip install pywinusb`

## Instalação
```
git clone https://github.com/SEU_USUARIO/joymap.git
cd joymap
pip install -r requirements.txt
```

## Uso

### Executável (sem instalar Python)
Use o `JoyMap.exe` na raiz da pasta (buildado com PyInstaller — tudo embutido).

**Duplo-clique** abre um menu interativo:
```
  1) Mapear controles HID (detectar byte/bit de cada botao)
  2) Ler dispositivo em tempo real (XInput)
  3) Digitar comando (ex: --mode dinput, --mode joy, 5 --map ...)
  Ctrl+X para sair
```
- Escolhendo `1` (HID), ele lista os dispositivos, pede o **número do dispositivo**,
  o **layout** e começa a perguntar **"APERTE e solte o botao AGORA"** para cada botão
  (A, B, X, Y...), registrando o byte/bit de cada um.
- Escolhendo `2`, lê ao vivo via XInput (controles Xbox/360/One e GamePad Amazon).
- Escolhendo `3`, digita um comando como `5 --map --layout xbox; --mode dinput`.

> **Auto-detecção XInput:** controles Xbox (VID `0x045E`) e GamePad Amazon
> (VID `0x1949`) são detectados automaticamente. Como eles **não enviam reports RAW
> em modo HID**, o modo `1` oferece redirecionar para a leitura XInput em vez de
> travar no "Nenhum report recebido". Em scripts/pipes (saída redirecionada) sem
> argumentos, o modo `hid` apenas lista os dispositivos e sai. (Desenvolvido com
> [opencode](https://opencode.ai).)

### Versão Python (para desenvolvimento)
Listar dispositivos HID:
```
python -u joymap.py
```

Abrir um dispositivo e ver o diff ao vivo:
```
python -u joymap.py 7
```

Mapeamento guiado com layout de botões:
```
python -u joymap.py 7 --map --layout playstation
python -u joymap.py 7 --map --layout xbox
python -u joymap.py 7 --map --layout nintendo
```

Exportar direto para um arquivo (sem perguntar):
```
python -u joymap.py 7 --map --layout playstation --export mapeamento_ps2
```

## Modos de leitura (`--mode`)
| Modo | Descrição | Como usar |
|---|---|---|
| `hid` (padrão) | HID via pywinusb — mapeamento byte/bit e diff ao vivo | `python -u joymap.py <indice>` |
| `xinput` | Controles Xbox/360/One via `xinput.dll` — mostra botões nomeados e sticks | `python -u joymap.py --mode xinput` |
| `joy` | Joysticks via API legada `winmm` — eixos, POV e bitmask de botões | `python -u joymap.py --mode joy` |
| `dinput` | Controles legados via DirectInput `dinput8.dll` | `python -u joymap.py --mode dinput` |

> No modo `xinput`, `joy` e `dinput`, os botões já vêm **decodificados** pela API (não há mapeamento byte/bit).

> Ao rodar via **duplo-clique** sem argumentos, aparece um **menu de modos**. Em scripts/pipes (saida redirecionada), o modo `hid` sem argumentos apenas lista os dispositivos e sai.

### Layouts disponíveis
| Layout | Botões pedidos no teste |
|---|---|
| `playstation` | X (Cross), Circle, Square, Triangle, L1, R1, L2, R2, Select/Share, Start/Options, L3, R3, PS/Home |
| `xbox` | A, B, X, Y, LB, RB, LT, RT, View, Menu, L3, R3, Guide |
| `nintendo` | B, A, Y, X, L, R, ZL, ZR, Minus, Plus, L3, R3, Home |

## Como funciona
O script compara cada report HID recebido com o **report de repouso (baseline)**:

1. Ao abrir o dispositivo, o primeiro report vira o **baseline** (estado com nada apertado).
2. Cada novo report é comparado byte a byte com o baseline.
3. Quando você aperta um botão, alguns **bytes mudam de valor**. A ferramenta mostra:
   - qual **byte** mudou,
   - o valor de repouso → valor apertado,
   - quais **bits** foram alterados.

Exemplo de saída:
```
BOTAO 1/13:  X (Cross)
  > detectado: byte5: 0F->4F (bit6)
```
Isso significa: ao apertar X, o **byte 5** vai de `0x0F` para `0x4F` — o **bit6** (`0x40`) é o botão X.

### Proteção anti-remapeamento
Se o diff de um botão já foi registrado em outro slot, o script **ignora** e continua esperando o botão correto, evitando que dois botões fiquem com o mesmo mapeamento.

## Exemplo de resultado
Veja [`examples/mapping_example.json`](examples/mapping_example.json) para um exemplo real de mapeamento de um adaptador PS2.

## Exportação JSON
Ao final do mapeamento, o script pergunta se quer exportar. O JSON gerado (ex.: `mapping_20260814_123456.json`) contém:
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

## Licença
MIT — veja [LICENSE](LICENSE).
