"""Offline tests for markets/calendars.py. Synthetic inputs only. No network, no datasets.
Run from the repository root with:
    python3 -B -m unittest discover -s markets -p "test_*.py"
"""
import ast
import os
import unittest

from markets import calendars as cal

DAY = 86400
T0 = 1609459200          # 2021-01-01T00:00:00Z, on a daily boundary


class CryptoCalendarTests(unittest.TestCase):
    def test_every_aligned_open_time_is_expected(self):
        c = cal.CryptoCalendar24x7()
        for k in range(0, 5):
            with self.subTest(k=k):
                self.assertTrue(c.is_expected(T0 + k * DAY, DAY))
        self.assertTrue(c.is_expected(0, DAY))

    def test_intraday_timeframe(self):
        c = cal.CryptoCalendar24x7()
        self.assertTrue(c.is_expected(T0 + 3600, 3600))
        self.assertFalse(c.is_expected(T0 + 1800, 3600))

    def test_unaligned_open_time_is_not_expected(self):
        self.assertFalse(cal.CryptoCalendar24x7().is_expected(T0 + 1, DAY))

    def test_name_is_stable(self):
        self.assertEqual(cal.CryptoCalendar24x7().name, "crypto-24x7")

    def test_invalid_inputs_are_refused(self):
        c = cal.CryptoCalendar24x7()
        bad = [(True, DAY), (False, DAY), (T0, True), (T0, False), (-1, DAY), (T0, 0), (T0, -DAY),
               (T0 + 0.0, DAY), (T0, 1.5), (None, DAY), ("1609459200", DAY)]
        for open_time_s, timeframe_s in bad:
            with self.subTest(open_time_s=open_time_s, timeframe_s=timeframe_s):
                with self.assertRaises(cal.CalendarError):
                    c.is_expected(open_time_s, timeframe_s)


class InterfaceTests(unittest.TestCase):
    def test_calendar_base_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            cal.Calendar()

    def test_custom_calendar_plugs_into_the_interface(self):
        class EveryOtherDay(cal.Calendar):
            name = "test-every-other-day"

            def is_expected(self, open_time_s, timeframe_s):
                open_time_s, timeframe_s = self._inputs(open_time_s, timeframe_s)
                return open_time_s % timeframe_s == 0 and (open_time_s // timeframe_s) % 2 == 0

        c = EveryOtherDay()
        self.assertTrue(c.is_expected(T0, DAY))
        self.assertFalse(c.is_expected(T0 + DAY, DAY))


class StubCalendarTests(unittest.TestCase):
    def test_equity_stub_refuses_to_guess(self):
        stub = cal.EquityCalendarStub()
        self.assertEqual(stub.name, "equity-stub")
        with self.assertRaises(cal.CalendarNotImplemented):
            stub.is_expected(T0, DAY)

    def test_fx_stub_refuses_to_guess(self):
        stub = cal.FxCalendarStub()
        self.assertEqual(stub.name, "fx-stub")
        with self.assertRaises(cal.CalendarNotImplemented):
            stub.is_expected(T0, DAY)

    def test_stub_refusal_is_a_calendar_error(self):
        self.assertTrue(issubclass(cal.CalendarNotImplemented, cal.CalendarError))

    def test_stubs_still_check_their_inputs(self):
        # Invalid input is a CalendarError, not a CalendarNotImplemented, so the failure reason is clear.
        with self.assertRaises(cal.CalendarError) as ctx:
            cal.EquityCalendarStub().is_expected(True, DAY)
        self.assertNotIsInstance(ctx.exception, cal.CalendarNotImplemented)


class BoundaryTests(unittest.TestCase):
    def test_calendars_module_imports_only_the_standard_library_and_nothing_networked(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendars.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        self.assertEqual(names, {"abc"})


if __name__ == "__main__":
    unittest.main()
