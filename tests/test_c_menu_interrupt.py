from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "_jblibs_testpkg"

if PACKAGE_NAME not in sys.modules:
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(ROOT)]
    package.__package__ = PACKAGE_NAME
    sys.modules[PACKAGE_NAME] = package

c_menu_module = importlib.import_module(f"{PACKAGE_NAME}.c_menu")


class CMenuKeyboardInterruptTests(unittest.TestCase):
    def run_with_mocked_screen(self, menu, get_key_side_effect):
        with (
            patch.object(menu, "run_refresh", return_value=True),
            patch.object(c_menu_module, "getKey", side_effect=get_key_side_effect),
            patch.object(c_menu_module, "sleep"),
            patch.object(c_menu_module, "cls"),
        ):
            return menu.run()

    def test_ctrl_c_while_waiting_exits_through_on_exit_menu(self):
        menu = c_menu_module.c_menu(menu=[], quitEnable=False)
        menu.onExitMenu = Mock(return_value=None)

        result = self.run_with_mocked_screen(menu, KeyboardInterrupt())

        self.assertIsNone(result)
        menu.onExitMenu.assert_called_once_with()

    def test_ctrl_c_respects_on_exit_veto_and_keeps_menu_running(self):
        menu = c_menu_module.c_menu(menu=[], quitEnable=False)
        menu.onExitMenu = Mock(side_effect=[False, None])

        result = self.run_with_mocked_screen(
            menu,
            [KeyboardInterrupt(), KeyboardInterrupt()],
        )

        self.assertIsNone(result)
        self.assertEqual(menu.onExitMenu.call_count, 2)
        self.assertIsInstance(menu.lastReturn, c_menu_module.onSelReturn)

    def test_keyboard_interrupt_from_active_action_is_not_swallowed(self):
        def interrupted_action(_item):
            raise KeyboardInterrupt()

        item = c_menu_module.c_menu_item(
            "Interrupting action",
            "a",
            interrupted_action,
        )
        menu = c_menu_module.c_menu(menu=[item], quitEnable=False)

        with self.assertRaises(KeyboardInterrupt):
            self.run_with_mocked_screen(menu, ["a", "\r"])


if __name__ == "__main__":
    unittest.main()
