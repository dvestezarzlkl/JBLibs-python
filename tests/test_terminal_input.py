from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "_jblibs_terminal_testpkg"

if PACKAGE_NAME not in sys.modules:
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(ROOT)]
    package.__package__ = PACKAGE_NAME
    sys.modules[PACKAGE_NAME] = package

c_menu_module = importlib.import_module(f"{PACKAGE_NAME}.c_menu")
input_module = importlib.import_module(f"{PACKAGE_NAME}.input")


class FakeReadline:
    def __init__(self, history=None):
        self.history = list(history or [])

    def clear_history(self):
        self.history.clear()

    def add_history(self, value):
        self.history.append(value)

    def get_current_history_length(self):
        return len(self.history)

    def get_history_item(self, index):
        if 1 <= index <= len(self.history):
            return self.history[index - 1]
        return None


class TerminalInputTests(unittest.TestCase):
    def setUp(self):
        input_module._terminal_histories.clear()
        input_module._terminal_history_loaded.clear()

    def test_history_is_namespaced_and_external_readline_history_is_restored(self):
        readline = FakeReadline(["outside"])

        def first_input(_prompt):
            self.assertEqual(readline.history, [])
            readline.add_history("status")
            return "status"

        with (
            patch.object(input_module, "_get_terminal_readline", return_value=readline),
            patch("builtins.input", side_effect=first_input),
        ):
            self.assertEqual(
                input_module.terminal(
                    header=None,
                    defaultExit="q",
                    historyKey="ufw",
                    prompt="> ",
                    showExit=False,
                ),
                "status",
            )

        self.assertEqual(readline.history, ["outside"])
        self.assertEqual(input_module._terminal_histories["ufw"], ["status"])

        def second_input(_prompt):
            self.assertEqual(readline.history, ["status"])
            readline.add_history(":list")
            return ":list"

        with (
            patch.object(input_module, "_get_terminal_readline", return_value=readline),
            patch("builtins.input", side_effect=second_input),
        ):
            self.assertEqual(
                input_module.terminal(
                    header=None,
                    defaultExit="q",
                    historyKey="ufw",
                    prompt="> ",
                    showExit=False,
                ),
                ":list",
            )

        self.assertEqual(input_module._terminal_histories["ufw"], ["status", ":list"])
        self.assertEqual(readline.history, ["outside"])

    def test_default_exit_is_not_kept_in_history(self):
        readline = FakeReadline()

        def fake_input(_prompt):
            readline.add_history("q")
            return "q"

        with (
            patch.object(input_module, "_get_terminal_readline", return_value=readline),
            patch("builtins.input", side_effect=fake_input),
        ):
            self.assertIsNone(
                input_module.terminal(
                    header=None,
                    defaultExit="q",
                    historyKey="ufw",
                    showExit=False,
                )
            )

        self.assertEqual(input_module._terminal_histories["ufw"], [])

    def test_dispatcher_passes_context_args_and_builds_dynamic_help(self):
        owner = object()
        seen = []

        def info(ctx, args):
            seen.append((ctx.owner, args))
            return "INFO " + args

        commands = {
            "help": input_module.terminal_command(
                lambda ctx, _args: ctx.help(),
                "show help",
            ),
            "info": input_module.terminal_command(
                info,
                lambda _ctx: "<name> = show profile info",
            ),
        }

        with (
            patch.object(input_module, "_get_terminal_readline", return_value=None),
            patch.object(input_module, "printBlock"),
            patch.object(input_module, "cls"),
            patch("builtins.input", side_effect=[":info Apache Full", "q"]),
        ):
            result = input_module.terminal(
                title="Demo",
                commands=commands,
                context=owner,
                historyKey="dispatch-test",
            )

        self.assertIsNone(result)
        self.assertEqual(seen, [(owner, "Apache Full")])

        ctx = input_module.terminal_context(owner)
        ctx.commands = commands
        ctx.fnPrefix = ":"
        self.assertEqual(
            list(ctx.help()),
            [":help    show help", ":info    <name> = show profile info"],
        )

    def test_structured_blocks_are_rendered_and_history_file_is_written(self):
        header = c_menu_module.c_menu_block_items()
        header.append(("Console", "c"))
        footer = c_menu_module.c_menu_block_items()
        footer.append(("State", "ready"))

        with TemporaryDirectory() as tmp:
            history_file = str(Path(tmp) / "history.txt")
            with (
                patch.object(input_module, "_get_terminal_readline", return_value=None),
                patch.object(input_module, "printBlock") as print_block,
                patch("builtins.input", return_value="show"),
            ):
                self.assertEqual(
                    input_module.terminal(
                        header=header,
                        title="Demo",
                        footer=footer,
                        defaultExit="q",
                        historyKey="demo",
                        historyFile=history_file,
                        minMessageWidth=80,
                    ),
                    "show",
                )

            print_block.assert_called_once()
            self.assertEqual(Path(history_file).read_text(encoding="utf-8"), "show\n")


if __name__ == "__main__":
    unittest.main()
