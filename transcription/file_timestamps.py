# -*- coding: utf-8 -*-
"""Utilities for normalizing file timestamps after artifact generation."""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path


def set_creation_time_now(file_path: str | Path) -> None:
    """Set filesystem creation time to current timestamp on Windows.

    Falls back to os.utime on non-Windows platforms.
    """
    set_file_times(file_path, datetime.now())


def set_file_times(file_path: str | Path, when: datetime) -> None:
    """Set file creation time (Windows) plus modified/accessed time."""
    path = Path(file_path)
    if not path.exists():
        return

    when_ts = when.timestamp()

    if os.name != "nt":
        os.utime(path, (when_ts, when_ts))
        return

    # Windows FILETIME counts 100-ns intervals since 1601-01-01 UTC.
    epoch_as_filetime = 11644473600
    now_filetime = int((when_ts + epoch_as_filetime) * 10_000_000)

    try:
        import ctypes
        from ctypes import wintypes

        file_write_attributes = 0x0100
        open_existing = 3
        file_share_read = 0x00000001
        file_share_write = 0x00000002
        file_share_delete = 0x00000004
        invalid_handle_value = wintypes.HANDLE(-1).value

        class FILETIME(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD),
            ]

        ft = FILETIME(
            now_filetime & 0xFFFFFFFF,
            (now_filetime >> 32) & 0xFFFFFFFF,
        )

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE

        kernel32.SetFileTime.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
        ]
        kernel32.SetFileTime.restype = wintypes.BOOL

        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateFileW(
            str(path),
            file_write_attributes,
            file_share_read | file_share_write | file_share_delete,
            None,
            open_existing,
            0,
            None,
        )
        if handle == invalid_handle_value:
            return

        try:
            if not kernel32.SetFileTime(handle, ctypes.byref(ft), None, None):
                return
            # Keep displayed timestamps consistent in Explorer columns.
            os.utime(path, (when_ts, when_ts))
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        # Keep export pipeline resilient if timestamp update is unavailable.
        return
