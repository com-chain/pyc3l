import unittest
from pyc3l.ApiHandling import ApiHandling
from pyc3l.ApiCommunication import (
    encodeNumber,
    decodeNumber,
    encodeAddressForTransaction,
    buildInfoData
)


class test_ApiCommunication(unittest.TestCase):
    def test_encodeNumber(self):

        ORACLE = {
            "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff6": -10,
            "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff": -1,
            "0000000000000000000000000000000000000000000000000000000000000000": 0,
            "0000000000000000000000000000000000000000000000000000000000000001": 1,
            "000000000000000000000000000000000000000000000000000000000000000a": 10,
            "0000000000000000000000000000000000000000000000000000000000000064": 100,
            "00000000000000000000000000000000000000000000000000000000000003e8": 1000,
        }

        for encoded, to_encode in ORACLE.items():
            self.assertEqual(encodeNumber(to_encode), encoded)
            self.assertEqual(to_encode, decodeNumber(encoded))

    def test_encodeAddressForTransaction(self):

        # When
        address_1 = "0xE00000000000000000000000000000000000000E"
        address_2 = "E00000000000000000000000000000000000000E"
        address_3 = "E000000000000000000000000000000000000000E"
        address_4 = "E0000000000000000000000000000000000000E"

        # then
        self.assertEqual(
            encodeAddressForTransaction(address_1),
            "000000000000000000000000E00000000000000000000000000000000000000E",
        )
        self.assertEqual(
            encodeAddressForTransaction(address_2),
            "000000000000000000000000E00000000000000000000000000000000000000E",
        )

        with self.assertRaises(Exception):
            encodeAddressForTransaction(address_3)
        with self.assertRaises(Exception):
            encodeAddressForTransaction(address_4)

    def test_buildInfoData(self):

        # When
        function_1 = "0x11111111"
        function_2 = "11111111"
        address_1 = "0xE00000000000000000000000000000000000000E"
        address_2 = "E00000000000000000000000000000000000000E"

        # then
        self.assertEqual(
            buildInfoData(function_1, address_1),
            "0x11111111000000000000000000000000E00000000000000000000000000000000000000E",
        )
        self.assertEqual(
            buildInfoData(function_2, address_1),
            "0x11111111000000000000000000000000E00000000000000000000000000000000000000E",
        )
        self.assertEqual(
            buildInfoData(function_1, address_2),
            "0x11111111000000000000000000000000E00000000000000000000000000000000000000E",
        )
        self.assertEqual(
            buildInfoData(function_2, address_2),
            "0x11111111000000000000000000000000E00000000000000000000000000000000000000E",
        )


if __name__ == "__main__":
    unittest.main()
