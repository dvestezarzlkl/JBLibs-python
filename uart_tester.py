from __future__ import annotations

from .lng.default import *
from .helper import loadLng

loadLng()

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
DEFAULT_TEST_REPEAT = 1
DEFAULT_BYTESIZE = 8
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 1
DEFAULT_SERIAL_TIMEOUT = 0.2
TIMEOUT = 2  # vteřiny pro čekání na odpověď
HISTORY_FILE = os.path.expanduser("~/.serial_sender_history")

_history_initialized = False


def get_hash128(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def generate_test_text(length: int) -> str:
    base = "Nejobdelavatelnejsi-se-vse-obdelavatelnych-1234567890-"
    return (base * ((length // len(base)) + 1))[:length]


def build_test_command(length: int, repeat: int = DEFAULT_TEST_REPEAT) -> str:
    return f"test{length}n{repeat}"


def parse_command(line: str) -> tuple[int | None, int | None]:
    match = re.match(r"^test(?P<len>\d+)?(?:n(?P<rep>\d+))?$", line.strip().lower())
    if match:
        length = int(match.group("len")) if match.group("len") else DEFAULT_TEST_LEN
        repeat = int(match.group("rep")) if match.group("rep") else DEFAULT_TEST_REPEAT
        return length, repeat
    return None, None


def validate_test_params(length: int, repeat: int) -> str | None:
    if length < 1:
        return TXT_UART_ERR_LEN_MIN
    if length > 1024:
        return TXT_UART_ERR_LEN_MAX
    if repeat < 1:
        return TXT_UART_ERR_REPEAT_MIN
    if repeat > 100:
        return TXT_UART_ERR_REPEAT_MAX
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

    print(
        TXT_UART_SEND_STATUS.format(
            attempt=attempt_label,
            length=ln,
            hash=expected_hash,
        ),
        end="     ",
    )

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
                        print(f"[OK   {attempt_label}] {TXT_UART_OK_HASH_CONTENT}")
                        return True
                    print(f"[FAIL {attempt_label}] {TXT_UART_FAIL_HASH_CONTENT}")
                    return False

                print(
                    f"[FAIL {attempt_label}] "
                    + TXT_UART_FAIL_HASH.format(
                        received_hash=received_hash,
                        computed_hash=computed_hash,
                    )
                )
                return False
            except ValueError:
                print(f"[FAIL {attempt_label}] {TXT_UART_FAIL_INVALID_RESPONSE.format(line=line)}")
                return False

    print(f"[TIMEOUT {attempt_label}] {TXT_UART_TIMEOUT}")
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


def serialGet(
    port: str,
    baudrate: int,
    timeout: float = DEFAULT_SERIAL_TIMEOUT,
    bytesize: int = DEFAULT_BYTESIZE,
    parity: str = DEFAULT_PARITY,
    stopbits: float = DEFAULT_STOPBITS,
    xonxoff: bool = False,
    rtscts: bool = False,
    dsrdtr: bool = False,
) -> Any | str:
    """Otevře sériový port."""
    if serial is None:
        return TXT_UART_ERR_MISSING_PYSERIAL

    try:
        return serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=timeout,
            xonxoff=xonxoff,
            rtscts=rtscts,
            dsrdtr=dsrdtr,
        )
    except serial.SerialException as e:
        return TXT_UART_ERR_OPEN_PORT.format(port=port, err=e)


def receiver_mode(ser: Any, clear_screen: bool = True) -> str | None:
    """Režim příjmu - čeká na zprávy a odpovídá."""
    if clear_screen:
        cls()

    print(TXT_UART_RECEIVER_TITLE.format(version=VERSION))
    print(TXT_UART_INFO_PORT.format(port=ser.port, baudrate=ser.baudrate) + "\n")
    print(TXT_UART_RECEIVER_ACTIVE)
    print(TXT_UART_RECEIVER_EXIT_HINT + "\n")

    try:
        while True:
            line = ser.readline().decode(errors="replace").strip()
            if not line:
                continue

            ln = len(line)

            if line.startswith("test_"):
                print(TXT_UART_IN_BYTES_RECEIVED.format(length=ln), end="     ")
                payload = line[5:]
                hash_val = get_hash128(payload)
                resp = f"resp_{payload}_{hash_val}"
                ser.write((resp + "\r\n").encode())
                ser.flush()
                ln = len(resp)
                print(TXT_UART_OUT_BYTES_SENT.format(length=ln, hash=hash_val))
            else:
                print(f"[IN ] {line}")
    except KeyboardInterrupt:
        return TXT_UART_RECEIVER_STOPPED


def cls() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def header(ser: Any, clear: bool = True) -> None:
    if clear:
        cls()
    print("*" * 70)
    print(TXT_UART_SENDER_TITLE.format(version=VERSION))
    print("*" * 70)
    print(TXT_UART_INFO_PORT.format(port=ser.port, baudrate=ser.baudrate))
    print(TXT_UART_HEADER_CMD_HINT)
    print(TXT_UART_HEADER_HELP_HINT)
    print(TXT_UART_HEADER_RCV_HINT)
    print("\n")


def print_help() -> None:
    print(TXT_UART_HELP_TITLE)
    print(TXT_UART_HELP_SYNTAX)
    print(TXT_UART_HELP_TEST_DEFAULT)
    print(TXT_UART_HELP_TEST_LEN)
    print(TXT_UART_HELP_TEST_REPEAT)
    print(TXT_UART_HELP_TEST_REPEAT_DEFAULT)
    print(TXT_UART_HELP_RCV)
    print(TXT_UART_HELP_CLS)
    print(TXT_UART_HELP_EXIT)
    print(TXT_UART_HELP_HELP)


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
            print(TXT_UART_SWITCH_TO_RCV)
            if x := receiver_mode(ser):
                print(x)
            print(TXT_UART_BACK_TO_TX)
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

            print(TXT_UART_SENDING_TEST.format(length=length, repeat=repeat))
            try:
                run_test(ser, length, repeat)
                input(TXT_UART_PRESS_ENTER)
            except KeyboardInterrupt:
                print(TXT_UART_STOPPED_BY_USER)
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
    serial_timeout: float = DEFAULT_SERIAL_TIMEOUT,
    bytesize: int = DEFAULT_BYTESIZE,
    parity: str = DEFAULT_PARITY,
    stopbits: float = DEFAULT_STOPBITS,
    xonxoff: bool = False,
    rtscts: bool = False,
    dsrdtr: bool = False,
) -> str | None:
    """Spustí tester v zadaném režimu."""
    ser = serialGet(
        port,
        baudrate,
        timeout=serial_timeout,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        xonxoff=xonxoff,
        rtscts=rtscts,
        dsrdtr=dsrdtr,
    )

    if isinstance(ser, str):
        return ser

    error: str | None = None
    try:
        if transmitter:
            transmitter_mode(ser)
        else:
            error = receiver_mode(ser)
    except Exception as e:
        error = TXT_UART_ERR_OCCURRED.format(err=e)
    finally:
        try:
            ser.close()
        except Exception as e:
            close_error = TXT_UART_ERR_CLOSE_PORT.format(err=e)
            if error:
                return f"{error}\n{close_error}"
            return close_error

    return error


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=TXT_UART_ARG_DESCRIPTION
    )
    parser.add_argument("port", help=TXT_UART_ARG_PORT_HELP)
    parser.add_argument(
        "-b",
        "--baudrate",
        type=int,
        default=DEFAULT_BAUDRATE,
        help=TXT_UART_ARG_BAUDRATE_HELP.format(baudrate=DEFAULT_BAUDRATE),
    )
    parser.add_argument(
        "-r",
        "--receiver",
        action="store_true",
        help=TXT_UART_ARG_RECEIVER_HELP,
    )
    parser.add_argument(
        "-p",
        "--parity",
        choices=["N", "E", "O", "M", "S"],
        default=DEFAULT_PARITY,
        help=TXT_UART_ARG_PARITY_HELP,
    )
    parser.add_argument(
        "--bytesize",
        type=int,
        choices=[5, 6, 7, 8],
        default=DEFAULT_BYTESIZE,
        help=TXT_UART_ARG_BYTESIZE_HELP.format(bytesize=DEFAULT_BYTESIZE),
    )
    parser.add_argument(
        "--stopbits",
        type=float,
        choices=[1, 1.5, 2],
        default=DEFAULT_STOPBITS,
        help=TXT_UART_ARG_STOPBITS_HELP.format(stopbits=DEFAULT_STOPBITS),
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=DEFAULT_SERIAL_TIMEOUT,
        help=TXT_UART_ARG_TIMEOUT_HELP.format(timeout=DEFAULT_SERIAL_TIMEOUT),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    cls()

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    ret = runAs(
        args.port,
        args.baudrate,
        not args.receiver,
        serial_timeout=args.timeout,
        bytesize=args.bytesize,
        parity=args.parity,
        stopbits=args.stopbits,
    )
    chyba = False
    if ret:
        print(ret)
        chyba = True

    print(TXT_UART_EXITING)
    if chyba:
        sys.exit(1)


if __name__ == "__main__":
    main()
