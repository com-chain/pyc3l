import unittest
from pyc3l.ApiHandling import ApiHandling
from pyc3l.ApiCommunication import ApiCommunication

class test_ApiCommunication(unittest.TestCase):

    def test_encodeNumber(self):
        # with 
        api_handling = ApiHandling()
        api_com = ApiCommunication(api_handling, 'Lemanopolis')

        # When
        number_m10 = -10
        number_m1 = -1
        number_0 = 0
        number_1 = 1
        number_10 = 10
        number_100 = 100
        number_1000 = 1000
        
        #then
        self.assertEqual(api_com.encodeNumber(number_m10), 'fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff6')
        self.assertEqual(api_com.encodeNumber(number_m1), 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff')
        self.assertEqual(api_com.encodeNumber(number_0), '0000000000000000000000000000000000000000000000000000000000000000')
        self.assertEqual(api_com.encodeNumber(number_1), '0000000000000000000000000000000000000000000000000000000000000001')
        self.assertEqual(api_com.encodeNumber(number_10), '000000000000000000000000000000000000000000000000000000000000000a')
        self.assertEqual(api_com.encodeNumber(number_100), '0000000000000000000000000000000000000000000000000000000000000064')
        self.assertEqual(api_com.encodeNumber(number_1000), '00000000000000000000000000000000000000000000000000000000000003e8')
        
    def test_decodeNumber(self):
        # with 
        api_handling = ApiHandling()
        api_com = ApiCommunication(api_handling, 'Lemanopolis')

        # When
        number_m10 = 'fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff6'
        number_m1 = 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        number_0 = '0000000000000000000000000000000000000000000000000000000000000000'
        number_1 = '0000000000000000000000000000000000000000000000000000000000000001'
        number_10 = '000000000000000000000000000000000000000000000000000000000000000a'
        number_100 = '0000000000000000000000000000000000000000000000000000000000000064'
        number_1000 = '00000000000000000000000000000000000000000000000000000000000003e8'
        
        #then
        self.assertEqual(api_com.decodeNumber(number_m10), -10)
        self.assertEqual(api_com.decodeNumber(number_m1), -1)
        self.assertEqual(api_com.decodeNumber(number_0), 0)
        self.assertEqual(api_com.decodeNumber(number_1), 1)
        self.assertEqual(api_com.decodeNumber(number_10), 10)
        self.assertEqual(api_com.decodeNumber(number_100), 100)
        self.assertEqual(api_com.decodeNumber(number_1000), 1000)

    def test_encodeAddressForTransaction(self):
        # with 
        api_handling = ApiHandling()
        api_com = ApiCommunication(api_handling, 'Lemanopolis')
        
        # When
        address_1 = '0xE00000000000000000000000000000000000000E'
        address_2 = 'E00000000000000000000000000000000000000E'
        address_3 = 'E000000000000000000000000000000000000000E'
        address_4 = 'E0000000000000000000000000000000000000E'
        
        #then
        self.assertEqual(api_com.encodeAddressForTransaction(address_1), '000000000000000000000000E00000000000000000000000000000000000000E')
        self.assertEqual(api_com.encodeAddressForTransaction(address_2), '000000000000000000000000E00000000000000000000000000000000000000E')
        
        with self.assertRaises(Exception):
            api_com.encodeAddressForTransaction(address_3)
        with self.assertRaises(Exception):
            api_com.encodeAddressForTransaction(address_4)

    def test_buildInfoData(self):
        # with 
        api_handling = ApiHandling()
        api_com = ApiCommunication(api_handling, 'Lemanopolis')
        
        # When
        function_1 = "0x11111111"
        function_2 = "11111111"
        address_1 = '0xE00000000000000000000000000000000000000E'
        address_2 = 'E00000000000000000000000000000000000000E'
        
        #then
        self.assertEqual(api_com.buildInfoData(function_1, address_1), '0x11111111000000000000000000000000E00000000000000000000000000000000000000E')
        self.assertEqual(api_com.buildInfoData(function_2, address_1), '0x11111111000000000000000000000000E00000000000000000000000000000000000000E')
        self.assertEqual(api_com.buildInfoData(function_1, address_2), '0x11111111000000000000000000000000E00000000000000000000000000000000000000E')
        self.assertEqual(api_com.buildInfoData(function_2, address_2), '0x11111111000000000000000000000000E00000000000000000000000000000000000000E')
        
        
        
if __name__ == '__main__':
    unittest.main()
