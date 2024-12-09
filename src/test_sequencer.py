# Test for Sequencer


import unittest
from sequencer import *

class MockNeoWrapper(NeoWrapper):
    def __init__(self, target, len):
        super().__init__(target, len)
        self.num_copy = 0
        self.num_show = 0
        self.sleep_total = 0

    def copy(self):
        super().copy()
        self.num_copy += 1

    def show(self):
        self.num_show += 1

    def sleep(self, seconds: float):
        self.sleep_total += seconds

    def assertExpects(self, num_copy, num_show, sleep_total):
        assert(self.num_copy == num_copy)
        assert(self.num_show == num_show)
        assert(self.sleep_total == sleep_total)


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
        i = InstructionFill(nw, delay=0, runs=[RgbCount("FF0000", 1), RgbCount("00FF00", 2), RgbCount("0000FF", 3)])
        self.assertEqual(i.start(), None)
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
        self.assertEqual(i.step(), None)
        nw.assertExpects(num_copy=1, num_show=1, sleep_total=0)


class TestSequencer(unittest.TestCase):
    def test_seq1(self):
        nw = MockNeoWrapper([(0,0,0)], 1)
        s = Sequencer(nw)
        s.parse("Fill #FF0000 2  #00FF00 3  #0000FF 4 ; Slide 0.5 42 ; SlowFill 0.42 #FFEEDD 10  #FF0000 11  #00FF00 12  #0000FF 13")
        self.assertEqual(s._instructions, [
            InstructionFill(nw, delay=0, runs=[RgbCount("FF0000", 2), RgbCount("00FF00", 3), RgbCount("0000FF", 4)]),
            InstructionSlide(nw, delay=0.5, count=42),
            InstructionFill(nw, delay=0.42, runs=[RgbCount("FFEEDD", 10), RgbCount("FF0000", 11), RgbCount("00FF00", 12), RgbCount("0000FF", 13)]),
        ])


if __name__ == '__main__':
    unittest.main()


#~~



