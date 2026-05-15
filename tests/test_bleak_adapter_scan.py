from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from timiniprint.transport.bluetooth.adapters.bleak_adapter import _BleakBleAdapter


class _FakeDevice:
    def __init__(self, name: str, address: str) -> None:
        self.name = name
        self.address = address


class _BluezInProgressError(RuntimeError):
    pass


class BleakAdapterScanTests(unittest.TestCase):
    def test_scan_retries_bluez_in_progress_and_succeeds(self) -> None:
        class _FakeBleakScanner:
            calls = 0

            @classmethod
            async def discover(cls, timeout: float):
                _ = timeout
                cls.calls += 1
                if cls.calls < 3:
                    raise _BluezInProgressError(
                        "[org.bluez.Error.InProgress] Operation already in progress"
                    )
                return [_FakeDevice("TiMini", "AA:BB:CC:DD:EE:FF")]

        fake_bleak = types.SimpleNamespace(BleakScanner=_FakeBleakScanner)

        with patch.dict("sys.modules", {"bleak": fake_bleak}), patch(
            "timiniprint.transport.bluetooth.adapters.bleak_adapter.time.sleep",
            return_value=None,
        ):
            adapter = _BleakBleAdapter()
            devices = adapter.scan_blocking(timeout=0.1)

        self.assertEqual(_FakeBleakScanner.calls, 3)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].address, "AA:BB:CC:DD:EE:FF")

    def test_scan_raises_after_retries_for_bluez_in_progress(self) -> None:
        class _FakeBleakScanner:
            calls = 0

            @classmethod
            async def discover(cls, timeout: float):
                _ = timeout
                cls.calls += 1
                raise _BluezInProgressError(
                    "[org.bluez.Error.InProgress] Operation already in progress"
                )

        fake_bleak = types.SimpleNamespace(BleakScanner=_FakeBleakScanner)

        with patch.dict("sys.modules", {"bleak": fake_bleak}), patch(
            "timiniprint.transport.bluetooth.adapters.bleak_adapter.time.sleep",
            return_value=None,
        ):
            adapter = _BleakBleAdapter()
            with self.assertRaisesRegex(RuntimeError, "BLE scan failed"):
                adapter.scan_blocking(timeout=0.1)

        self.assertEqual(_FakeBleakScanner.calls, 4)

    def test_scan_does_not_retry_unrelated_errors(self) -> None:
        class _FakeBleakScanner:
            calls = 0

            @classmethod
            async def discover(cls, timeout: float):
                _ = timeout
                cls.calls += 1
                raise RuntimeError("adapter disconnected")

        fake_bleak = types.SimpleNamespace(BleakScanner=_FakeBleakScanner)

        with patch.dict("sys.modules", {"bleak": fake_bleak}), patch(
            "timiniprint.transport.bluetooth.adapters.bleak_adapter.time.sleep",
            return_value=None,
        ):
            adapter = _BleakBleAdapter()
            with self.assertRaisesRegex(RuntimeError, "BLE scan failed"):
                adapter.scan_blocking(timeout=0.1)

        self.assertEqual(_FakeBleakScanner.calls, 1)


if __name__ == "__main__":
    unittest.main()
