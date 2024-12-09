# Test for Sequencer


import unittest
from sequencer import *


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


class TestSequencer(unittest.TestCase):
    def test_seq1(self):
        s = Sequencer()
        s.parse("Fill #FF0000 2  #00FF00 3  #0000FF 4 ; Slide 0.5 42 ; SlowFill 0.42 #FFEEDD 10  #FF0000 11  #00FF00 12  #0000FF 13")
        self.assertEqual(s._instructions, [
            InstructionFill(delay=0, runs=[RgbCount("FF0000", 2), RgbCount("00FF00", 3), RgbCount("0000FF", 4)]),
            InstructionSlide(delay=0.5, count=42),
            InstructionFill(delay=0.42, runs=[RgbCount("FFEEDD", 10), RgbCount("FF0000", 11), RgbCount("00FF00", 12), RgbCount("0000FF", 13)]),
        ])


if __name__ == '__main__':
    unittest.main()


#~~



