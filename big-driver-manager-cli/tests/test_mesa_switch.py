"""Mesa variant switch: never removes what depends on Mesa.

On 2026-10-24 switching to mesa-tkg removed the whole Plasma desktop: the
old flow ran ``pacman -Rnc --noconfirm mesa ...`` and -c is --cascade, which
removes every package that depends on mesa (363 on a Plasma install). These
tests pin the replacement: a plan from pacman's metadata, one transaction
that replaces the old variant, and a rollback.
"""

import argparse
import json
import unittest
from unittest.mock import patch

from core import mesa_cli
from core.mesa_manager import (
    MESA_DRIVERS,
    MesaManager,
    parse_pacman_info,
    plan_mesa_switch,
)

TKG = {
    "id": "tkg-stable",
    "name": "Tkg-Stable",
    "packages": ["mesa-tkg-stable", "lib32-mesa-tkg-stable"],
    "conflicts": [
        "mesa",
        "lib32-mesa",
        "vulkan-intel",
        "vulkan-mesa-implicit-layers",
        "mesa-amber",
    ],
}

# What mesa-tkg-stable's PKGBUILD declares.
TKG_INFO = {
    "mesa-tkg-stable": {
        "Provides": ["mesa=26.2.2-1", "vulkan-intel=26.2.2-1", "opengl-driver"],
        "Conflicts With": ["mesa", "vulkan-intel", "vulkan-mesa-layers"],
    },
    "lib32-mesa-tkg-stable": {
        "Provides": ["lib32-mesa=26.2.2-1"],
        "Conflicts With": ["lib32-mesa"],
    },
}

INSTALLED_INFO = {
    "mesa": {"Provides": ["libva-mesa-driver=1:26.2.2-1"]},
    "lib32-mesa": {"Depends On": ["mesa"]},
    "vulkan-intel": {
        "Provides": ["vulkan-driver"],
        "Depends On": ["vulkan-mesa-implicit-layers"],
    },
    "vulkan-mesa-implicit-layers": {},
    "kwin": {"Depends On": ["mesa", "libdrm"]},
    "qt6-base": {"Depends On": ["mesa"]},
    "plasma-desktop": {"Depends On": ["kwin"]},
}

INSTALLED = set(INSTALLED_INFO)


def _plan(**overrides):
    kwargs = {
        "driver": TKG,
        "installed": INSTALLED,
        "available": {"mesa-tkg-stable", "lib32-mesa-tkg-stable"},
        "target_info": TKG_INFO,
        "installed_info": INSTALLED_INFO,
    }
    kwargs.update(overrides)
    return plan_mesa_switch(**kwargs)


class TestPlan(unittest.TestCase):
    def test_declared_conflicts_are_replaced_by_pacman(self):
        plan = _plan()
        self.assertTrue(plan.allowed, plan.problems)
        self.assertEqual(plan.install, ["mesa-tkg-stable", "lib32-mesa-tkg-stable"])
        self.assertEqual(plan.replaced, ["mesa", "lib32-mesa", "vulkan-intel"])

    def test_undeclared_conflict_goes_first_only_when_its_users_leave_too(self):
        # vulkan-mesa-implicit-layers: mesa-tkg ships its files without
        # declaring the conflict; only vulkan-intel (replaced) needs it.
        self.assertEqual(_plan().remove_first, ["vulkan-mesa-implicit-layers"])

    def test_desktop_packages_are_never_in_the_plan(self):
        plan = _plan()
        touched = set(plan.replaced) | set(plan.remove_first)
        self.assertFalse(touched & {"kwin", "qt6-base", "plasma-desktop"})

    def test_refuses_when_a_staying_package_needs_a_removed_one(self):
        # render-menu-options needs vulkan-mesa-implicit-layers, which the
        # new variant does not provide.
        info = dict(INSTALLED_INFO)
        info["render-menu-options"] = {"Depends On": ["vulkan-mesa-implicit-layers"]}
        plan = _plan(installed=set(info), installed_info=info)
        self.assertFalse(plan.allowed)
        self.assertIn("render-menu-options", plan.problems[0])

    def test_refuses_when_the_new_variant_lacks_a_provide(self):
        # mesa-amber does not provide libva-mesa-driver, which biglinux-vaapi
        # needs: pacman refuses, and the plan says why before anything runs.
        amber = {
            "id": "amber",
            "name": "Amber",
            "packages": ["mesa-amber"],
            "conflicts": ["mesa"],
        }
        info = dict(INSTALLED_INFO)
        info["biglinux-vaapi"] = {"Depends On": ["libva-mesa-driver"]}
        plan = plan_mesa_switch(
            amber,
            set(info),
            {"mesa-amber"},
            {"mesa-amber": {"Provides": ["mesa=21.3.9"], "Conflicts With": ["mesa"]}},
            info,
        )
        self.assertFalse(plan.allowed)
        self.assertEqual(len(plan.problems), 1)
        self.assertIn("libva-mesa-driver", plan.problems[0])
        self.assertIn("biglinux-vaapi", plan.problems[0])

    def test_a_dependency_another_staying_package_provides_is_fine(self):
        info = dict(INSTALLED_INFO)
        info["steam"] = {"Depends On": ["vulkan-driver"]}
        info["vulkan-nouveau"] = {"Provides": ["vulkan-driver"]}
        plan = _plan(installed=set(info), installed_info=info)
        self.assertTrue(plan.allowed, plan.problems)

    def test_missing_main_package_refuses(self):
        plan = _plan(available={"lib32-mesa-tkg-stable"})
        self.assertFalse(plan.allowed)

    def test_missing_lib32_refuses_when_32_bit_mesa_is_installed(self):
        # Removing lib32-mesa without its tkg twin would take Steam with it.
        plan = _plan(available={"mesa-tkg-stable"})
        self.assertFalse(plan.allowed)
        self.assertIn("lib32-mesa-tkg-stable", plan.problems[0])

    def test_missing_lib32_is_skipped_without_32_bit_mesa(self):
        installed = {p for p in INSTALLED if not p.startswith("lib32-")}
        plan = _plan(installed=installed, available={"mesa-tkg-stable"})
        self.assertTrue(plan.allowed, plan.problems)
        self.assertEqual(plan.skipped, ["lib32-mesa-tkg-stable"])

    def test_conflict_declared_by_the_installed_package_counts(self):
        # Back to stable: mesa does not name mesa-tkg-stable, but
        # mesa-tkg-stable conflicts with mesa, so pacman replaces it.
        stable = {
            "id": "stable",
            "name": "Stable",
            "packages": ["mesa"],
            "conflicts": ["mesa-tkg-stable"],
        }
        plan = plan_mesa_switch(
            stable,
            {"mesa-tkg-stable", "kwin"},
            {"mesa"},
            {"mesa": {"Provides": [], "Conflicts With": []}},
            {
                "mesa-tkg-stable": {
                    "Provides": ["mesa=26.2.2-1"],
                    "Conflicts With": ["mesa"],
                },
                "kwin": {"Depends On": ["mesa"]},
            },
        )
        self.assertTrue(plan.allowed, plan.problems)
        self.assertEqual(plan.replaced, ["mesa-tkg-stable"])
        self.assertEqual(plan.remove_first, [])

    def test_unknown_driver(self):
        mgr = MesaManager()
        plan = mgr.plan_switch("nope")
        self.assertFalse(plan.allowed)


class TestParsePacmanInfo(unittest.TestCase):
    def test_fields_none_versions_and_wrapped_lines(self):
        out = (
            "Name            : mesa-tkg-stable\n"
            "Provides        : mesa=26.2.2-1  vulkan-intel=26.2.2-1\n"
            "                  opengl-driver\n"
            "Conflicts With  : mesa\n"
            "Required By     : None\n"
            "\n"
            "Name            : mesa-tkg-stable\n"
            "Provides        : other\n"
            "\n"
            "Name            : lib32-mesa\n"
            "Required By     : steam\n"
        )
        info = parse_pacman_info(out)
        self.assertEqual(
            info["mesa-tkg-stable"]["Provides"],
            ["mesa=26.2.2-1", "vulkan-intel=26.2.2-1", "opengl-driver"],
        )
        self.assertEqual(info["mesa-tkg-stable"]["Required By"], [])
        self.assertEqual(info["lib32-mesa"]["Required By"], ["steam"])


class TestDriversJson(unittest.TestCase):
    def test_tkg_variants_bring_their_32_bit_package(self):
        drivers = {d["id"]: d for d in MESA_DRIVERS}
        for variant in ("tkg-stable", "tkg-git"):
            with self.subTest(variant=variant):
                packages = drivers[variant]["packages"]
                self.assertIn("lib32-mesa-" + variant, packages)

    def test_every_variant_conflicts_with_the_32_bit_packages_of_the_others(self):
        drivers = {d["id"]: d for d in MESA_DRIVERS}
        for variant, driver in drivers.items():
            for other, other_driver in drivers.items():
                if other == variant:
                    continue
                for package in other_driver["packages"]:
                    if (
                        package.startswith(("mesa", "lib32-mesa"))
                        and package not in (driver["packages"])
                    ):
                        if package == "mesa-utils":
                            continue
                        with self.subTest(variant=variant, package=package):
                            self.assertIn(package, driver["conflicts"])

    def test_tools_are_not_conflicts(self):
        # mesa-utils (glxinfo) works with every variant; removing it took
        # its dependents with it.
        for driver in MESA_DRIVERS:
            with self.subTest(driver=driver["id"]):
                self.assertNotIn("mesa-utils", driver["conflicts"])


class TestSwitch(unittest.TestCase):
    """The root side: the exact pacman sequence."""

    def _switch(self, plan, results):
        calls = []
        answers = iter(results)

        def pacman(arguments):
            calls.append(arguments)
            return next(answers, True)

        with (
            patch.object(mesa_cli, "_pacman", side_effect=pacman),
            patch.object(
                mesa_cli,
                "_installed_as_dependency",
                return_value={"vulkan-mesa-implicit-layers"},
            ),
        ):
            code = mesa_cli._switch(plan)
        return code, calls

    def test_sequence(self):
        code, calls = self._switch(_plan(), [True, True, True])
        self.assertEqual(code, mesa_cli.EXIT_OK)
        self.assertEqual(
            calls,
            [
                [
                    "-Sw",
                    "--noconfirm",
                    "--ask",
                    "4",
                    "mesa-tkg-stable",
                    "lib32-mesa-tkg-stable",
                ],
                ["-Rdd", "--noconfirm", "vulkan-mesa-implicit-layers"],
                [
                    "-S",
                    "--noconfirm",
                    "--needed",
                    "--ask",
                    "4",
                    "mesa-tkg-stable",
                    "lib32-mesa-tkg-stable",
                ],
            ],
        )

    def test_never_cascades_and_never_removes_the_desktop(self):
        _code, calls = self._switch(_plan(), [True, True, True])
        for call in calls:
            if call[0].startswith("-R"):
                self.assertNotIn("c", call[0][2:])
                self.assertNotIn("mesa", call)
            self.assertNotIn("--overwrite", call)

    def test_download_failure_changes_nothing(self):
        code, calls = self._switch(_plan(), [False])
        self.assertEqual(code, mesa_cli.EXIT_FAILED)
        self.assertEqual(len(calls), 1)

    def test_failed_transaction_puts_back_what_was_removed_first(self):
        code, calls = self._switch(_plan(), [True, True, False, True, True])
        self.assertEqual(code, mesa_cli.EXIT_FAILED)
        self.assertEqual(
            calls[3], ["-S", "--noconfirm", "--needed", "vulkan-mesa-implicit-layers"]
        )
        # It was a dependency before: it stays one.
        self.assertEqual(calls[4], ["-D", "--asdeps", "vulkan-mesa-implicit-layers"])


class TestCli(unittest.TestCase):
    def _args(self, **kw):
        base = {
            "mesa_action": "apply",
            "variant": "tkg-stable",
            "yes": True,
            "confirmed": False,
        }
        base.update(kw)
        return argparse.Namespace(**base)

    def test_blocked_plan_runs_nothing(self):
        blocked = _plan(available=set())
        with (
            patch.object(MesaManager, "plan_switch", return_value=blocked),
            patch.object(mesa_cli, "_switch") as switch,
            patch.object(mesa_cli, "is_root", return_value=True),
        ):
            code = mesa_cli.run(self._args())
        self.assertEqual(code, mesa_cli.EXIT_FAILED)
        switch.assert_not_called()

    def test_not_root_elevates_with_the_confirmed_request(self):
        with (
            patch.object(MesaManager, "plan_switch", return_value=_plan()),
            patch.object(mesa_cli, "is_root", return_value=False),
            patch.object(mesa_cli.kernel_cli, "elevate", return_value=0) as elevate,
        ):
            mesa_cli.run(self._args())
        elevate.assert_called_once_with(["mesa", "apply", "tkg-stable", "--confirmed"])

    def test_plan_json(self):
        with (
            patch.object(MesaManager, "plan_switch", return_value=_plan()),
            patch("builtins.print") as printed,
        ):
            code = mesa_cli.run(
                argparse.Namespace(mesa_action="plan", variant="tkg-stable", json=True)
            )
        self.assertEqual(code, mesa_cli.EXIT_OK)
        data = json.loads(printed.call_args.args[0])
        self.assertEqual(data["remove_first"], ["vulkan-mesa-implicit-layers"])


if __name__ == "__main__":
    unittest.main()
