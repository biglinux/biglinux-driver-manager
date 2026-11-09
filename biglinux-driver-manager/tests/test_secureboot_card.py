"""The Secure Boot card of the kernel page, on the fake GTK."""

from __future__ import annotations

import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "usr", "share", "big-driver-manager"),
)

from gi_fakes import install_fake_gi, reload_ui_modules

install_fake_gi()


class ProgressSpy:
    def __init__(self) -> None:
        self.shown, self.success, self.errors = [], [], []

    def show_progress(self, title, message, cancel_callback=None) -> None:
        self.shown.append(title)

    def update_progress(self, fraction, text) -> None:
        pass

    def append_terminal_output(self, line) -> None:
        pass

    def show_success(self, message) -> None:
        self.success.append(message)

    def show_error(self, message) -> None:
        self.errors.append(message)


class TestSecureBootCard(unittest.TestCase):
    def setUp(self):
        reload_ui_modules()
        self.mod = importlib.import_module("ui.secureboot_card")
        self.sb = importlib.import_module("core.secureboot")
        self.card = self.mod.SecureBootCard()
        self.card.refresh = MagicMock()  # no pacman in tests

    def test_hidden_where_unavailable(self):
        self.card._show_state(self.sb.UNAVAILABLE)
        self.assertFalse(self.card.get_visible())

    def test_every_state_says_something_and_offers_one_action(self):
        for state, label in (
            (self.sb.OFF, "Enable"),
            (self.sb.PENDING, "Disable"),
            (self.sb.ACTIVE, "Disable"),
            (self.sb.GAMES, "Disable"),
        ):
            with self.subTest(state=state):
                self.card._show_state(state)
                self.assertTrue(self.card.get_visible())
                self.assertTrue(self.mod.state_text(state))
                self.assertEqual(self.card._button.get_label(), label)

    def test_the_steps_give_the_password(self):
        self.assertIn(self.sb.MOK_PASSWORD, self.mod.confirm_steps())
        self.assertIn(self.sb.MOK_PASSWORD, self.mod.state_text(self.sb.PENDING))

    def _run(self, state, *, success):
        self.card._show_state(state)
        progress = ProgressSpy()
        self.card.set_progress_dialog(progress)
        manager = MagicMock()
        manager.last_error_hint = None
        self.card.manager = manager
        self.card._on_response(None, "go")
        action = manager.enable if state == self.sb.OFF else manager.disable
        action.assert_called_once()
        complete = action.call_args.kwargs["complete_callback"]
        complete(success)
        return progress

    def test_enable_installs_and_reports(self):
        progress = self._run(self.sb.OFF, success=True)
        self.assertEqual(progress.shown, ["Enabling Secure Boot"])
        self.assertTrue(progress.success)
        self.card.refresh.assert_called()

    def test_disable_removes_and_reports_a_failure(self):
        progress = self._run(self.sb.ACTIVE, success=False)
        self.assertEqual(progress.shown, ["Disabling Secure Boot"])
        self.assertTrue(progress.errors)

    def test_cancel_does_nothing(self):
        self.card._show_state(self.sb.OFF)
        self.card.manager = MagicMock()
        self.card._on_response(None, "cancel")
        self.card.manager.enable.assert_not_called()


if __name__ == "__main__":
    unittest.main()
