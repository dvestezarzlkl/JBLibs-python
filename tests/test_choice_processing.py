from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "_jblibs_choice_testpkg"

if PACKAGE_NAME not in sys.modules:
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(ROOT)]
    package.__package__ = PACKAGE_NAME
    sys.modules[PACKAGE_NAME] = package

term_module = importlib.import_module(f"{PACKAGE_NAME}.term")
c_menu_module = importlib.import_module(f"{PACKAGE_NAME}.c_menu")
input_module = importlib.import_module(f"{PACKAGE_NAME}.input")
from .test_terminal_input import TerminalInputTests


class ProcessingMessageTests(unittest.TestCase):
    def test_format_supports_python_placeholder_and_percent_alias(self):
        self.assertEqual(
            term_module.format_processing_message(
                "Processing {value} / %v%",
                "\x1b[31mApply\x1b[0m",
            ),
            "Processing Apply / Apply",
        )

    def test_empty_template_disables_output(self):
        with patch("builtins.print") as print_mock:
            term_module.print_processing_status("", "Apply")
        print_mock.assert_not_called()


class CMenuProcessingTests(unittest.TestCase):
    def test_callable_action_emits_feedback_before_callback(self):
        events = []

        def action(_item):
            events.append(("callback", None))
            return c_menu_module.onSelReturn()

        item = c_menu_module.c_menu_item("Apply firewall", "a", action)
        menu = c_menu_module.c_menu(menu=[item], quitEnable=False)

        def progress(template, value):
            events.append(("progress", (template, value)))

        with (
            patch.object(menu, "run_refresh", return_value=True),
            patch.object(c_menu_module, "getKey", side_effect=["a", "\r", KeyboardInterrupt()]),
            patch.object(c_menu_module, "sleep"),
            patch.object(c_menu_module, "cls"),
            patch.object(c_menu_module, "print_processing_status", side_effect=progress),
        ):
            menu.run()

        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[0][0], "progress")
        self.assertEqual(events[1][0], "callback")
        self.assertEqual(events[0][1][0], c_menu_module.TXT_PROCESSING_CHOICE)
        self.assertIn("Apply firewall", events[0][1][1])

    def test_item_can_disable_feedback(self):
        item = c_menu_module.c_menu_item(
            "Instant action",
            "i",
            lambda _item: c_menu_module.onSelReturn(),
            processingText="",
        )
        menu = c_menu_module.c_menu(menu=[item], quitEnable=False)

        with (
            patch.object(menu, "run_refresh", return_value=True),
            patch.object(c_menu_module, "getKey", side_effect=["i", "\r", KeyboardInterrupt()]),
            patch.object(c_menu_module, "sleep"),
            patch.object(c_menu_module, "cls"),
            patch.object(c_menu_module, "print_processing_status") as progress,
        ):
            menu.run()

        progress.assert_called_once_with("", item.label)


class InputProcessingTests(unittest.TestCase):
    def test_confirm_reports_localized_selected_value(self):
        with (
            patch.object(input_module, "printBlock"),
            patch.object(input_module, "getKey", return_value="y"),
            patch.object(input_module, "print_processing_status") as progress,
        ):
            result = input_module.confirm("Proceed?")

        self.assertTrue(result)
        progress.assert_called_once_with(
            input_module.TXT_PROCESSING_CHOICE,
            input_module.confirm_choices[0][1],
        )

    def test_select_reports_choice_after_internal_menu_is_removed(self):
        selected = c_menu_module.c_menu_item(
            "Webmin",
            "1",
            lambda _item: c_menu_module.onSelReturn(endMenu=True),
            data="webmin",
        )

        def fake_run(menu):
            self.assertTrue(all(
                not isinstance(item, c_menu_module.c_menu_item)
                or item.processingText == ""
                for item in menu.menu
            ))
            menu._selectedItem = selected

        with (
            patch.object(c_menu_module.c_menu, "run", fake_run),
            patch.object(c_menu_module.c_menu, "getLastSelItem", lambda menu: menu._selectedItem),
            patch.object(c_menu_module.c_menu, "getCalcWidth", return_value=80),
            patch.object(input_module, "reset"),
            patch.object(input_module, "print_processing_status") as progress,
        ):
            result = input_module.select(
                "Choose",
                [input_module.select_item("Webmin", data="webmin")],
            )

        self.assertIs(result.item, selected)
        self.assertEqual(result.calcWidth, 80)
        progress.assert_called_once_with(
            input_module.TXT_PROCESSING_CHOICE,
            selected.label,
        )


if __name__ == "__main__":
    unittest.main()
