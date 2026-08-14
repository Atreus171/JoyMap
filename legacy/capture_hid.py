import sys
import time


def list_devices():
    import pywinusb.hid as hid
    print("VID:PID   Nome")
    print("-" * 50)
    for d in hid.find_all_hid_devices():
        print(f"{d.vendor_id:04X}:{d.product_id:04X}  {d.product_name}")


def capture(vid, pid):
    import pywinusb.hid as hid
    targets = [d for d in hid.find_all_hid_devices()
               if d.vendor_id == vid and d.product_id == pid]
    if not targets:
        print("Dispositivo nao encontrado. Conecte/pareie antes de rodar.")
        return
    dev = targets[0]
    print(f"\nAbrindo {vid:04X}:{pid:04X}  ->  {dev.product_name}")

    dev.open()

    # Diagnostico: mostra as colecoes e reports de input
    try:
        print("Colecoes/HID-usage:")
        for c in dev.find_collections():
            print(f"  usage_page=0x{c.usage_page:04X} usage=0x{c.usage:04X}")
    except Exception as e:
        print("  (sem info de colecoes:", e, ")")

    reports = dev.find_input_reports()
    print(f"Input reports encontrados: {len(reports)}")
    if not reports:
        print("Nenhum input report -> o dispositivo nao envia HID padrao ou "
              "esta bloqueado por outro programa (Steam, jogo, joy.cpl aberto).")
        dev.close()
        return

    def handler(data):
        try:
            raw = list(bytes(data))
            print(' '.join(f"{b:02X}" for b in raw))
        except Exception as e:
            print("erro no handler:", e)

    for r in reports:
        print(f"  report id={r.report_id} tam={r.report_size}")
        r.set_raw_data_handler(handler)

    print("\nAperte botoes / mexa nos analógicos. Ctrl+C para parar.\n")
    try:
        while True:
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    dev.close()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        list_devices()
        print("\nUso: python capture_hid.py VID PID")
    else:
        v = int(sys.argv[1], 16)
        p = int(sys.argv[2], 16)
        capture(v, p)
