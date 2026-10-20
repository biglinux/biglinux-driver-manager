"""main.py: the interface entry point."""

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "usr", "share", "big-driver-manager"),
)


class TestMainEntrypoint(unittest.TestCase):
    def test_main_initializes_signals_and_runs_application(self):
        fake_ui_module = types.ModuleType("ui.application")
        fake_app = MagicMock()
        fake_app.run.return_value = 7
        fake_ui_module.KernelManagerApplication = MagicMock(return_value=fake_app)

        with (
            patch.dict(sys.modules, {"ui.application": fake_ui_module}),
            patch("signal.signal") as signal_mock,
        ):
            if "main" in sys.modules:
                sys.modules.pop("main", None)
            import main

            result = main.main()

        self.assertEqual(result, 7)
        self.assertEqual(signal_mock.call_count, 2)
        fake_app.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
