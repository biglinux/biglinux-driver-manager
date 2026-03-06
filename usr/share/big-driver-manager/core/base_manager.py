#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Base Manager

This module provides a base class for all manager classes (Kernel, Mesa, Package)
containing shared functionality for progress handling, output callbacks, and
thread management.
"""

import re
import subprocess
import threading
import time
from typing import Callable

from core.constants import (
    SUDO_COMMAND,
    PROGRESS_UPDATE_INTERVAL,
    STATUS_UPDATE_INTERVAL,
)
from core.logging_config import get_logger
from core.subprocess_env import subprocess_env
from utils.i18n import _

_logger = get_logger("BaseManager")


class BaseManager:
    """Base class for package/kernel/mesa managers with shared functionality."""

    def __init__(self, *, thread_launcher: Callable | None = None):
        """Initialize the base manager.

        Args:
            thread_launcher: Optional callable(target, args) that starts work
                asynchronously. Defaults to launching a daemon thread.
        """
        self.sudo_command = SUDO_COMMAND
        self._current_process: subprocess.Popen | None = None
        self._cancelled = False
        self._last_output_lines: list[str] = []
        self._thread_launcher = thread_launcher or self._default_launcher

    @staticmethod
    def _default_launcher(target: Callable, args: tuple) -> None:
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()

    def cancel_operation(self):
        """Cancel the current operation by terminating the subprocess."""
        self._cancelled = True
        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.terminate()
                # Give it a moment to terminate gracefully
                try:
                    self._current_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate
                    self._current_process.kill()
                    self._current_process.wait()
            except Exception as e:
                _logger.error("Error terminating process: %s", e)

    def _run_pacman_command(
        self,
        args: list[str],
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
        operation_name: str = "Operation",
    ) -> None:
        """
        Run a pacman command in a background thread with progress tracking.

        Args:
            args: List of arguments to pass to pacman
            progress_callback: Callback for progress updates (fraction, text)
            output_callback: Callback for terminal output
            complete_callback: Callback for completion (success: bool)
            operation_name: Name of the operation for progress messages
        """
        self._thread_launcher(
            self._execute_command_thread,
            (
                args,
                progress_callback,
                output_callback,
                complete_callback,
                operation_name,
            ),
        )

    # Retry delays (in seconds) for transient pacman errors (e.g. db.lck)
    _RETRY_DELAYS = (5, 10)

    def _execute_command_thread(
        self,
        args: list[str],
        progress_callback: Callable | None,
        output_callback: Callable | None,
        complete_callback: Callable | None,
        operation_name: str,
    ) -> None:
        """
        Thread function for executing pacman commands.

        On transient errors (database lock), retries up to 2 times with
        increasing delays before reporting failure.

        Args:
            args: List of arguments for pacman
            progress_callback: Callback for progress updates
            output_callback: Callback for terminal output
            complete_callback: Callback for completion notification
            operation_name: Name of the operation
        """
        self._cancelled = False
        cmd = [self.sudo_command, "pacman"] + args

        for attempt in range(1 + len(self._RETRY_DELAYS)):
            success = self._run_single_attempt(
                cmd, attempt, progress_callback, output_callback, operation_name
            )
            if success is None:
                # Exception occurred — already reported
                if complete_callback:
                    complete_callback(False)
                return
            if success or self._cancelled:
                break
            if not self._is_retryable_error():
                break
            if attempt < len(self._RETRY_DELAYS):
                delay = self._RETRY_DELAYS[attempt]
                self._output(
                    output_callback,
                    _("Database locked. Retrying in {} seconds...").format(delay),
                )
                self._progress(
                    progress_callback,
                    0.0,
                    _("Waiting {} s before retry...").format(delay),
                )
                time.sleep(delay)
                self._output(
                    output_callback,
                    _("Retry attempt {} of {}...").format(
                        attempt + 1, len(self._RETRY_DELAYS)
                    ),
                )

        returncode = self._current_process.returncode if self._current_process else 1
        self._current_process = None
        self._report_result(
            bool(success),
            operation_name,
            progress_callback,
            output_callback,
            complete_callback,
            returncode,
        )

    def _run_single_attempt(
        self,
        cmd: list[str],
        attempt: int,
        progress_callback: Callable | None,
        output_callback: Callable | None,
        operation_name: str,
    ) -> bool | None:
        """
        Execute one attempt of the pacman command.

        Returns True on success, False on failure, None on exception.
        """
        if attempt == 0:
            self._output(output_callback, _("Starting {}...").format(operation_name))
            self._output(output_callback, _("Command: {}").format(" ".join(cmd)))
        self._progress(
            progress_callback, 0.1, _("Starting {}...").format(operation_name)
        )

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=subprocess_env(),
            )
            self._current_process = process

            self._read_process_output(process, progress_callback, output_callback)

            success = self._finalize_process(process)
            return success

        except Exception as e:
            self._current_process = None
            error_msg = _("Error: {}").format(str(e))
            self._progress(progress_callback, 0.0, error_msg)
            self._output(output_callback, error_msg)
            return None

    def _is_retryable_error(self) -> bool:
        """Check if the last error was a transient database lock."""
        combined = " ".join(self._last_output_lines).lower()
        return "unable to lock database" in combined

    def _read_process_output(
        self,
        process: subprocess.Popen,
        progress_callback: Callable | None,
        output_callback: Callable | None,
    ) -> float:
        """Read process stdout line by line, updating progress and output."""
        progress = 0.1
        status_text: str | None = None
        last_progress_update = time.time()
        last_line_time = time.time()
        self._last_output_lines = []

        if not process.stdout:
            return progress

        for line in iter(process.stdout.readline, ""):
            if self._cancelled:
                self._output(output_callback, _("Operation cancelled by user."))
                break

            line = line.strip()
            if line:
                self._output(output_callback, line)
                self._last_output_lines.append(line)
                # Keep only last 50 lines to bound memory
                if len(self._last_output_lines) > 50:
                    self._last_output_lines.pop(0)
                last_line_time = time.time()
                progress, parsed_text = self._parse_progress(line, progress)
                if parsed_text:
                    status_text = parsed_text

            current_time = time.time()
            if current_time - last_progress_update > PROGRESS_UPDATE_INTERVAL:
                self._progress(progress_callback, progress, status_text)
                last_progress_update = current_time

            if current_time - last_line_time > STATUS_UPDATE_INTERVAL:
                self._output(
                    output_callback,
                    _("Still working... ({:.0%} complete)").format(progress),
                )
                last_line_time = current_time

            time.sleep(0.01)

        return progress

    def _finalize_process(self, process: subprocess.Popen) -> bool:
        """Wait for process to finish and return success status."""
        if not self._cancelled:
            process.wait()
            return process.returncode == 0
        return False

    def _report_result(
        self,
        success: bool,
        operation_name: str,
        progress_callback: Callable | None,
        output_callback: Callable | None,
        complete_callback: Callable | None,
        returncode: int,
    ) -> None:
        """Report operation result to callbacks."""
        if self._cancelled:
            self._progress(progress_callback, 0.0, _("Operation cancelled"))
            self._output(output_callback, _("Operation was cancelled."))
            if complete_callback:
                complete_callback(False)
        elif success:
            self._progress(
                progress_callback, 1.0, _("{}  complete!").format(operation_name)
            )
            self._output(
                output_callback,
                _("{}  completed successfully.").format(operation_name),
            )
            if complete_callback:
                complete_callback(True)
        else:
            self._progress(
                progress_callback, 0.0, _("{}  failed.").format(operation_name)
            )
            self._output(
                output_callback,
                _("{}  failed (exit code: {})").format(operation_name, returncode),
            )
            self._suggest_error_recovery(output_callback)
            if complete_callback:
                complete_callback(False)

    # Common pacman error patterns mapped to user-friendly suggestions
    _ERROR_SUGGESTIONS: list[tuple[str, str]] = [
        (
            "target not found",
            _(
                "Package not found in repositories. "
                "The package name may have changed or been removed.\n"
                "Suggestion: Try refreshing the database with "
                "'sudo pacman -Sy' and search for the correct name."
            ),
        ),
        (
            "failed to commit transaction",
            _(
                "A conflict prevented the operation from completing.\n"
                "Suggestion: Clean the cache and update with "
                "'sudo pacman -Scc' followed by 'sudo pacman -Syyu'."
            ),
        ),
        (
            "conflicting files",
            _(
                "Some files from this package already exist on the system.\n"
                "Suggestion: Check which package owns the file with "
                "'pacman -Qo <file_path>' and resolve the conflict."
            ),
        ),
        (
            "could not satisfy dependencies",
            _(
                "Required dependencies could not be resolved.\n"
                "Suggestion: Update the full system first with 'sudo pacman -Syu'."
            ),
        ),
        (
            "signature from .* is unknown trust",
            _(
                "Package signature could not be verified.\n"
                "Suggestion: Update your keyrings with "
                "'sudo pacman -S archlinux-keyring manjaro-keyring'."
            ),
        ),
        (
            "unable to lock database",
            _(
                "The package database is locked by another process.\n"
                "If no other package manager is running, "
                "remove the lock with 'sudo rm /var/lib/pacman/db.lck'."
            ),
        ),
        (
            "no space left on device",
            _(
                "Not enough disk space to complete the operation.\n"
                "Suggestion: Free space by clearing the package cache "
                "with 'sudo pacman -Scc'."
            ),
        ),
        (
            "failed retrieving file",
            _(
                "Could not download required files.\n"
                "Suggestion: Check your internet connection. "
                "If the problem persists, try updating your mirror list."
            ),
        ),
        (
            "invalid or corrupted package",
            _(
                "A downloaded package is corrupted.\n"
                "Suggestion: Clear the cache with 'sudo pacman -Scc' "
                "and try again."
            ),
        ),
    ]

    def _suggest_error_recovery(self, output_callback: Callable | None) -> None:
        """Check collected output for known error patterns and suggest fixes."""
        combined = " ".join(self._last_output_lines).lower()
        for pattern, suggestion in self._ERROR_SUGGESTIONS:
            if re.search(pattern, combined):
                self._output(output_callback, f"💡 {suggestion}")
                return

    # Keyword → fixed progress mapping for pacman output phases
    _PROGRESS_KEYWORDS: list[tuple[str, float, str]] = [
        ("generating grub configuration", 0.9, _("Generating GRUB configuration...")),
        ("running post-transaction hooks", 0.8, _("Running post-transaction hooks...")),
        ("installing", 0.5, _("Installing packages...")),
        ("removing", 0.5, _("Removing packages...")),
        ("checking for file conflicts", 0.4, _("Checking for file conflicts...")),
        ("checking dependencies", 0.2, _("Checking dependencies...")),
        (
            "synchronizing package databases",
            0.1,
            _("Synchronizing package databases..."),
        ),
    ]

    def _parse_progress(
        self, line: str, current_progress: float
    ) -> tuple[float, str | None]:
        """
        Parse a line of output to estimate progress.

        Args:
            line: Output line to parse
            current_progress: Current progress value

        Returns:
            Tuple of (updated progress value, status text or None)
        """
        line_lower = line.lower()

        # Download phase (10-50%) — parse percentage or (n/total)
        if "download" in line_lower:
            new_progress = self._parse_download_progress(line, current_progress)
            if new_progress != current_progress:
                return new_progress, _("Downloading packages...")
            return current_progress, None

        # Keyword-based fixed progress values
        for keyword, progress, label in self._PROGRESS_KEYWORDS:
            if keyword in line_lower:
                return max(current_progress, progress), label

        return current_progress, None

    def _parse_download_progress(self, line: str, current_progress: float) -> float:
        """Extract download progress from percentage or (n/total) patterns."""
        percent_match = re.search(r"(\d+)%", line)
        if percent_match:
            percent = float(percent_match.group(1))
            return 0.1 + (percent / 100.0) * 0.4

        match = re.search(r"\((\d+)/(\d+)\)", line)
        if match:
            current = int(match.group(1))
            total = int(match.group(2))
            return 0.1 + (current / total) * 0.4

        return current_progress

    def _progress(
        self, callback: Callable | None, fraction: float, text: str | None
    ) -> None:
        """
        Send progress update if callback is provided.

        Args:
            callback: Progress callback function
            fraction: Progress fraction (0.0 to 1.0)
            text: Optional text to display
        """
        if callback:
            callback(fraction, text)

    def _output(self, callback: Callable | None, text: str) -> None:
        """
        Send output text if callback is provided.

        Args:
            callback: Output callback function
            text: Text to output
        """
        if callback:
            callback(text)
