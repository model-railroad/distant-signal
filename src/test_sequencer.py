# Test for Sequencer


import unittest
from sequencer import *

class MockNeoWrapper(NeoWrapper):
    def __init__(self, target, max_len):
        super().__init__(target, max_len)
        self.num_copy = 0
        self.num_show = 0
        self.sleep_total = 0
        self.val_brightness = 1

    def copy(self):
        super().copy()
        self.num_copy += 1

    def show(self):
        self.num_show += 1

    def sleep(self, seconds: float):
        self.sleep_total += seconds

    def brightness(self, value: float):
        self.val_brightness = value

    def assertExpects(self, case, num_copy, num_show, sleep_total):
        case.assertEqual(self.num_copy, num_copy)
        case.assertEqual(self.num_show, num_show)
        case.assertEqual(self.sleep_total, sleep_total)


class TestRgb(unittest.TestCase):
    def test_rgb1(self):
        c = Rgb("#112233")
        self.assertEqual(c.r, 0x11)
        self.assertEqual(c.g, 0x22)
        self.assertEqual(c.b, 0x33)
        self.assertEqual(repr(c), "#112233")

    def test_rgb2(self):
        c = Rgb("223344")
        self.assertEqual(c.r, 0x22)
        self.assertEqual(c.g, 0x33)
        self.assertEqual(c.b, 0x44)
        self.assertEqual(repr(c), "#223344")

    def test_eq(self):
        self.assertEqual(Rgb("#112233"), Rgb("#112233"))
        self.assertEqual(Rgb("#112233"), Rgb("112233"))
        self.assertEqual(Rgb("112233"), Rgb("112233"))


class TestRgbCount(unittest.TestCase):
    def test_rgb_count(self):
        c = RgbCount("#112233", 42)
        self.assertEqual(c.rgb.r, 0x11)
        self.assertEqual(c.rgb.g, 0x22)
        self.assertEqual(c.rgb.b, 0x33)
        self.assertEqual(c.count, 42)
        self.assertEqual(repr(c), "<#112233,42>")

    def test_eq(self):
        self.assertEqual(RgbCount("#112233", 42), RgbCount("#112233", 42))
        self.assertEqual(RgbCount("#112233", 42), RgbCount("112233", 42))


class TestInstructionFill(unittest.TestCase):
    def test_fill_static(self):
        nw = MockNeoWrapper([(0,0,0)] * 11, 11)
        i = InstructionFill(nw, delay_s=0, runs=[RgbCount("FF0000", 1), RgbCount("00FF00", 2), RgbCount("0000FF", 3)])
        self.assertIsNone(i.start())
        self.assertEqual(nw._target, [
            (0xFF,    0,    0),
            (   0, 0xFF,    0),
            (   0, 0xFF,    0),
            (   0,    0, 0xFF),
            (   0,    0, 0xFF),
            (   0,    0, 0xFF),
            (0xFF,    0,    0),
            (   0, 0xFF,    0),
            (   0, 0xFF,    0),
            (   0,    0, 0xFF),
            (   0,    0, 0xFF),
        ])
        self.assertIsNone(i.step())
        nw.assertExpects(self, num_copy=1, num_show=1, sleep_total=0)

    def test_fill_static_len(self):
        nw = MockNeoWrapper([(0,0,0)] * 5, 5)
        nw.len = 3
        i = InstructionFill(nw, delay_s=0, runs=[RgbCount("FF0000", 1), RgbCount("00FF00", 2), RgbCount("0000FF", 3)])
        self.assertIsNone(i.start())
        self.assertEqual(nw._target, [
            (0xFF,    0,    0),
            (   0, 0xFF,    0),
            (   0, 0xFF,    0),
            (   0,    0,    0),     # outside len range
            (   0,    0,    0),     # outside len range
        ])
        self.assertIsNone(i.step())
        nw.assertExpects(self, num_copy=1, num_show=1, sleep_total=0)

    def test_slow_fill(self):
        nw = MockNeoWrapper([(0,0,0)] * 4, 4)
        i = InstructionFill(nw, delay_s=0.25, runs=[RgbCount("FF0000", 1), RgbCount("00FF00", 2)])

        self.assertEqual(i.start(), i)
        self.assertEqual(nw._target, [
            (0xFF,    0,    0),
            (   0,    0,    0),
            (   0,    0,    0),
            (   0,    0,    0),
        ])
        nw.assertExpects(self, num_copy=1, num_show=1, sleep_total=0.25)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [
            (0xFF,    0,    0),
            (   0, 0xFF,    0),
            (   0,    0,    0),
            (   0,    0,    0),
        ])
        nw.assertExpects(self, num_copy=2, num_show=2, sleep_total=0.50)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [
            (0xFF,    0,    0),
            (   0, 0xFF,    0),
            (   0, 0xFF,    0),
            (   0,    0,    0),
        ])
        nw.assertExpects(self, num_copy=3, num_show=3, sleep_total=0.75)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [
            (0xFF,    0,    0),
            (   0, 0xFF,    0),
            (   0, 0xFF,    0),
            (0xFF,    0,    0),
        ])
        nw.assertExpects(self, num_copy=4, num_show=4, sleep_total=1.00)

        self.assertIsNone(i.step())
        nw.assertExpects(self, num_copy=4, num_show=4, sleep_total=1.00)

    def test_slow_fill_len(self):
        nw = MockNeoWrapper([(0,0,0)] * 4, 4)
        nw.len = 2
        i = InstructionFill(nw, delay_s=0.25, runs=[RgbCount("FF0000", 1), RgbCount("00FF00", 2)])

        self.assertEqual(i.start(), i)
        self.assertEqual(nw._target, [
            (0xFF,    0,    0),
            (   0,    0,    0),
            (   0,    0,    0),
            (   0,    0,    0),
        ])
        nw.assertExpects(self, num_copy=1, num_show=1, sleep_total=0.25)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [
            (0xFF,    0,    0),
            (   0, 0xFF,    0),
            (   0,    0,    0),
            (   0,    0,    0),
        ])
        nw.assertExpects(self, num_copy=2, num_show=2, sleep_total=0.50)

        self.assertIsNone(i.step())
        self.assertEqual(nw._target, [
            (0xFF,    0,    0),
            (   0, 0xFF,    0),
            (   0,    0,    0),
            (   0,    0,    0),
        ])
        nw.assertExpects(self, num_copy=2, num_show=2, sleep_total=0.50)


class TestInstructionSlide(unittest.TestCase):
    def test_slide(self):
        nw = MockNeoWrapper([(0,0,0), (1,1,1), (2,2,2), (3,3,3), (4,4,4)], 5)
        i = InstructionSlide(nw, delay_s=-0.5, count=8)

        self.assertEqual(i.start(), i)
        self.assertEqual(nw._target, [(1,1,1), (2,2,2), (3,3,3), (4,4,4), (0,0,0), ])
        nw.assertExpects(self, num_copy=1, num_show=1, sleep_total=0.5)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(2,2,2), (3,3,3), (4,4,4), (0,0,0), (1,1,1), ])
        nw.assertExpects(self, num_copy=2, num_show=2, sleep_total=1.0)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(3,3,3), (4,4,4), (0,0,0), (1,1,1), (2,2,2), ])
        nw.assertExpects(self, num_copy=3, num_show=3, sleep_total=1.5)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(4,4,4), (0,0,0), (1,1,1), (2,2,2), (3,3,3), ])
        nw.assertExpects(self, num_copy=4, num_show=4, sleep_total=2.0)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(0,0,0), (1,1,1), (2,2,2), (3,3,3), (4,4,4), ])
        nw.assertExpects(self, num_copy=5, num_show=5, sleep_total=2.5)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(1,1,1), (2,2,2), (3,3,3), (4,4,4), (0,0,0), ])
        nw.assertExpects(self, num_copy=6, num_show=6, sleep_total=3.0)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(2,2,2), (3,3,3), (4,4,4), (0,0,0), (1,1,1), ])
        nw.assertExpects(self, num_copy=7, num_show=7, sleep_total=3.5)

        self.assertIsNone(i.step())
        self.assertEqual(nw._target, [(3,3,3), (4,4,4), (0,0,0), (1,1,1), (2,2,2), ])
        nw.assertExpects(self, num_copy=8, num_show=8, sleep_total=4.0)

    def test_slide_len(self):
        nw = MockNeoWrapper([(0,0,0), (1,1,1), (2,2,2), (3,3,3), (4,4,4)], 5)
        nw.len = 2
        i = InstructionSlide(nw, delay_s=-0.5, count=8)

        self.assertEqual(i.start(), i)
        self.assertEqual(nw._target, [(1,1,1), (0,0,0), (2,2,2), (3,3,3), (4,4,4), ])
        nw.assertExpects(self, num_copy=1, num_show=1, sleep_total=0.5)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(0,0,0), (1,1,1), (2,2,2), (3,3,3), (4,4,4), ])
        nw.assertExpects(self, num_copy=2, num_show=2, sleep_total=1.0)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(1,1,1), (0,0,0), (2,2,2), (3,3,3), (4,4,4), ])
        nw.assertExpects(self, num_copy=3, num_show=3, sleep_total=1.5)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(0,0,0), (1,1,1), (2,2,2), (3,3,3), (4,4,4), ])
        nw.assertExpects(self, num_copy=4, num_show=4, sleep_total=2.0)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(1,1,1), (0,0,0), (2,2,2), (3,3,3), (4,4,4), ])
        nw.assertExpects(self, num_copy=5, num_show=5, sleep_total=2.5)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(0,0,0), (1,1,1), (2,2,2), (3,3,3), (4,4,4), ])
        nw.assertExpects(self, num_copy=6, num_show=6, sleep_total=3.0)

        self.assertEqual(i.step(), i)
        self.assertEqual(nw._target, [(1,1,1), (0,0,0), (2,2,2), (3,3,3), (4,4,4), ])
        nw.assertExpects(self, num_copy=7, num_show=7, sleep_total=3.5)

        self.assertIsNone(i.step())
        self.assertEqual(nw._target, [(0,0,0), (1,1,1), (2,2,2), (3,3,3), (4,4,4), ])
        nw.assertExpects(self, num_copy=8, num_show=8, sleep_total=4.0)


class TestSequencer(unittest.TestCase):
    def test_seq1(self):
        nw = MockNeoWrapper([(0,0,0)] * 20, 20)
        self.assertEqual(nw.val_brightness, 1)
        self.assertEqual(nw.len, 20)

        s = Sequencer(nw)
        s.parse("Length 10 ; Brightness 0.5 ; Fill #FF0000 2  #00FF00 3  #0000FF 4 ; Slide 0.5 42 ; SlowFill 0.42 #FFEEDD 10  #FF0000 11  #00FF00 12  #0000FF 13")
        self.assertEqual(s._instructions, [
            InstructionFill(nw, delay_s=0, runs=[RgbCount("FF0000", 2), RgbCount("00FF00", 3), RgbCount("0000FF", 4)]),
            InstructionSlide(nw, delay_s=0.5, count=42),
            InstructionFill(nw, delay_s=0.42, runs=[RgbCount("FFEEDD", 10), RgbCount("FF0000", 11), RgbCount("00FF00", 12), RgbCount("0000FF", 13)]),
        ])
        self.assertEqual(nw.val_brightness, 0.5)
        self.assertEqual(nw.len, 10)


if __name__ == '__main__':
    unittest.main()


#~~



