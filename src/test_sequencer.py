# Test for Sequencer

import unittest

from sequencer import Sequencer

class TestAdd(unittest.TestCase):
    def test_foo(self):
        s = Sequencer()
        self.assertEqual(s.foo(), 5)

if __name__ == '__main__':
    unittest.main()

#~~


