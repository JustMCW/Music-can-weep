import unittest

import convert

class Test_Convert(unittest.TestCase):
    """ Convert module test """

    def test_extract_int(self):
        self.assertEqual(convert.extract_int_from_str("A1000"),1000)
        self.assertEqual(convert.extract_int_from_str("A 12"),12)

        with self.assertRaises(ValueError):
            convert.extract_int_from_str("trolled")

    def test_length_format(self):
        self.assertEqual(convert.length_format(60),"1:00")
        self.assertEqual(convert.length_format(30),"0:30")
        self.assertEqual(convert.length_format(3600),"1:00:00")
        self.assertEqual(convert.length_format(3672),"1:01:12")

    def test_timestr_to_sec(self):
        self.assertEqual(convert.timestr_to_sec("9"),9)
        self.assertEqual(convert.timestr_to_sec("9:00"),9*60)
        self.assertEqual(convert.timestr_to_sec("5:12"),5*60 + 12)
        self.assertEqual(convert.timestr_to_sec("12:05:12"),12*3600 + 5*60 + 12)

        self.assertAlmostEqual(convert.timestr_to_sec_ms("9"),9)
        self.assertAlmostEqual(convert.timestr_to_sec_ms("9:00.100"),9*60+0.1)
        self.assertAlmostEqual(convert.timestr_to_sec_ms("5:12.690"),5*60 + 12 + 0.69)
        self.assertAlmostEqual(convert.timestr_to_sec_ms("12:05:120"),12*3600 + 5*60 + 12)


if __name__ == "__main__":
    unittest.main()
