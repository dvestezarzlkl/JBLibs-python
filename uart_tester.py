from __future__ import annotations

import argparse
import atexit
import hashlib
import importlib
import os
import re
import sys
import time
from typing import Any, Sequence

try:
    import serial
except ImportError:
    serial = None


VERSION = "1.3.0"
version = VERSION

DEFAULT_BAUDRATE = 19200
DEFAULT_TEST_LEN = 64
TIMEOUT = 2  # vteřiny pro čekání na odpověď
HISTORY_FILE = os.path.expanduser("~/.serial_sender_history")

_history_initialized = False


def get_hash128(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def generate_test_text(length: int) -> str:
    base = "Nejobdelavatelnejsi-se-vse-obdelavatelnych-1234567890-"
    return (base * ((length // len(base)) + 1))[:length]


def parse_command(line: str) -> tuple[int | None, int | None]:
    match = re.match(r"^test(?P<len>\d+)?(?:n(?P<rep>\d+))?$", line.strip().lower())
    if match:
        length = int(match.group("len")) if match.group("len") else DEFAULT_TEST_LEN
        repeat = int(match.group("rep")) if match.group("rep") else 1
        return length, repeat
    return None, None


def validate_test_params(length: int, repeat: int) -> str | None:
    if length < 1:
        return "[ERROR] Délka musí být větší než 0."
    if length > 1024:
        return "[ERROR] Délka je příliš velká (max 1024)."
    if repeat < 1:
        return "[ERROR] Počet opakování musí být větší než 0."
    if repeat > 100:
        return "[ERROR] Počet opakování je příliš velký (max 100)."
    return None


def _get_readline() -> Any | None:
    for module_name in ("readline", "pyreadline", "pyreadline3"):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue
    return None


def init_history(
    history_file: str = HISTORY_FILE,
    history_length: int = 50,
) -> None:
    global _history_initialized

    if _history_initialized:
        return

    readline = _get_readline()
    if readline is None:
        _history_initialized = True
        return
    if not all(
        hasattr(readline, attr)
        for attr in ("read_history_file", "write_history_file", "set_history_length")
    ):
        _history_initialized = True
        return

    try:
        readline.read_history_file(history_file)
    except FileNotFoundError:
        pass
    except OSError:
        pass

    readline.set_history_length(history_length)

    def _write_history() -> None:
        try:
            readline.write_history_file(history_file)
        except OSError:
            pass

    atexit.register(_write_history)
    _history_initialized = True


def send_and_wait_for_response(
    ser: Any,
    payload: str,
    attempt: int,
    timeout: float = TIMEOUT,
) -> bool:
    """Odešle zprávu a čeká na odpověď."""
    payload = "~" + payload + str(attempt) + "~"
    full_msg = "test_" + payload
    expected_hash = get_hash128(payload)

    ser.write((full_msg + "\r\n").encode())
    ser.flush()
    ln = len(full_msg)
    attempt_label = str(attempt).rjust(3)

    print(f"[SEND {attempt_label}] bytes: {ln} (hash: {expected_hash})", end="     ")

    start_time = time.time()
    while time.time() - start_time < timeout:
        line = ser.readline().decode(errors="replace").strip()
        if not line:
            continue

        if line.startswith("resp_"):
            try:
                content = line[5:]
                data, received_hash = content.rsplit("_", 1)
                computed_hash = get_hash128(data)

                if received_hash == computed_hash:
                    if data == payload:
                        print(f"[OK   {attempt_label}] Hash i obsah odpovídá.")
                        return True
                    print(f"[FAIL {attempt_label}] Hash OK - CHYBA obsahu.")
                    return False

                print(f"[FAIL {attempt_label}] Hash CHYBA {received_hash} != {computed_hash}")
                return False
            except ValueError:
                print(f"[FAIL {attempt_label}] Neplatný formát odpovědi: {line}")
                return False

    print(f"[TIMEOUT {attempt_label}] Nebyla přijata žádná odpověď.")
    return False


def run_test(
    ser: Any,
    length: int = DEFAULT_TEST_LEN,
    repeat: int = 1,
    delay: float = 0.3,
    timeout: float = TIMEOUT,
) -> list[bool] | str:
    error = validate_test_params(length, repeat)
    if error:
        return error

    payload = generate_test_text(length)
    results: list[bool] = []

    for i in range(1, repeat + 1):
        results.append(send_and_wait_for_response(ser, payload, i, timeout=timeout))
        time.sleep(delay)

    return results


def serialGet(port: str, baudrate: int, timeout: float = 0.2) -> Any | str:
    """Otevře sériový port."""
    if serial is None:
        return "[ERROR] Chybí knihovna pyserial. Nainstaluj ji příkazem: pip install pyserial"

    try:
        return serial.Serial(port, baudrate, timeout=timeout)
    except serial.SerialException as e:
        return f"[ERROR] Nelze otevřít port {port}: {e}"


def receiver_mode(ser: Any, clear_screen: bool = True) -> str | None:
    """Režim příjmu - čeká na zprávy a odpovídá."""
    if clear_screen:
        cls()

    print(f"[INFO] Serial tester - Receiver {VERSION} by dvestezar.cz")
    print(f"[INFO] Port: {ser.port} @ {ser.baudrate} baud\n")
    print("[RECEIVER] Režim příjmu aktivní. Čekám na zprávy...")
    print("[RECEIVER] Ukonči pomocí Ctrl+C\n")

    try:
        while True:
            line = ser.readline().decode(errors="replace").strip()
            if not line:
                continue

            ln = len(line)

            if line.startswith("test_"):
                print(f"[IN ] bytes received: {ln}", end="     ")
                payload = line[5:]
                hash_val = get_hash128(payload)
                resp = f"resp_{payload}_{hash_val}"
                ser.write((resp + "\r\n").encode())
                ser.flush()
                ln = len(resp)
                print(f"[OUT] bytes sent: {ln}, hash: {hash_val}")
            else:
                print(f"[IN ] {line}")
    except KeyboardInterrupt:
        return "[RECEIVER] Ukončeno uživatelem."


def cls() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def header(ser: Any, clear: bool = True) -> None:
    if clear:
        cls()
    print("*" * 70)
    print(f"********** Serial tester - Sender {VERSION} by dvestezar.cz **********")
    print("*" * 70)
    print(f"[INFO] Port: {ser.port} @ {ser.baudrate} baud")
    print("Zadej příkaz 'test[<len>][n<repeat>]' nebo 'exit'.")
    print("Pro nápovědu zadej 'help'.")
    print("Pro spuštění režimu příjmu zadej 'rcv'.")
    print("\n")


def print_help() -> None:
    print("\n*** Dostupné příkazy: ***")
    print("  test              → syntaxe = test[<len>][n<repeat>]")
    print("  - test              → odešle 64 znaků (defaultní test)")
    print("  - test120           → odešle 120 znaků")
    print("  - test80n5          → odešle 80 znaků, opakuje 5x")
    print("  - testn3            → odešle 64 znaků, opakuje 3x")
    print("  rcv               → spustí režim příjmu")
    print("  cls               → smaže obrazovku")
    print("  exit              → ukončí skript")
    print("  help              → zobrazí tento přehled\n")


def transmitter_mode(ser: Any, use_history: bool = True) -> None:
    if use_history:
        init_history()

    header(ser)
    while True:
        try:
            line = input("> ")
        except EOFError:
            break

        command = line.strip().lower()

        if command == "exit":
            break
        if command == "cls":
            header(ser)
            continue
        if command == "rcv":
            print("--- >>> Spouštím režim příjmu...")
            if x := receiver_mode(ser):
                print(x)
            print("--- <<< Návrat do odesílacího režimu.")
            time.sleep(1)
            header(ser)
            continue
        if command == "help":
            print_help()
            continue

        length, repeat = parse_command(line)
        if length is not None and repeat is not None:
            error = validate_test_params(length, repeat)
            if error:
                print(error)
                continue

            print(f"[INFO] Odesílám testovací zprávy ({length} znaků, {repeat}x)...")
            try:
                run_test(ser, length, repeat)
                input("Pro pokračování stiskněte ENTER...")
            except KeyboardInterrupt:
                print("\n[INFO] Ukončeno uživatelem.")
                time.sleep(1)
            header(ser)
        else:
            ser.write((line + "\r\n").encode())
            ser.flush()


def transmiter_mode(ser: Any) -> None:
    """Zpětně kompatibilní alias pro původní překlep v názvu funkce."""
    transmitter_mode(ser)


def runAs(
    port: str,
    baudrate: int = DEFAULT_BAUDRATE,
    transmitter: bool = True,
    serial_timeout: float = 0.2,
) -> str | None:
    """Spustí tester v zadaném režimu."""
    ser = serialGet(port, baudrate, timeout=serial_timeout)

    if isinstance(ser, str):
        return ser

    error: str | None = None
    try:
        if transmitter:
            transmitter_mode(ser)
        else:
            error = receiver_mode(ser)
    except Exception as e:
        error = f"[ERROR] Došlo k chybě: {e}"
    finally:
        try:
            ser.close()
        except Exception as e:
            close_error = f"[ERROR] Nelze zavřít port: {e}"
            if error:
                return f"{error}\n{close_error}"
            return close_error

    return error


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Odesílá testovací zprávy na sériový port a ověřuje odpovědi."
    )
    parser.add_argument("port", help="Sériový port, např. /dev/ttyS3")
    parser.add_argument(
        "-b",
        "--baudrate",
        type=int,
        default=DEFAULT_BAUDRATE,
        help=f"Rychlost v baudech (default: {DEFAULT_BAUDRATE})",
    )
    parser.add_argument(
        "-r",
        "--receiver",
        action="store_true",
        help="Spustit jako receiver (příjemce zpráv)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    cls()

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    ret = runAs(args.port, args.baudrate, not args.receiver)
    chyba = False
    if ret:
        print(ret)
        chyba = True

    print("Ukončuji.")
    if chyba:
        sys.exit(1)


if __name__ == "__main__":
    main()
