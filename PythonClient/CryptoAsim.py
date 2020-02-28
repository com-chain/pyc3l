from web3 import Web3
from web3.eth import Eth
from eth_account import Account
from Crypto import Random
from Crypto.Cipher import AES
from Crypto.PublicKey import ECC
from Crypto.Hash import SHA256, SHA512
import struct
import base64
import hmac
import hashlib


""""
/// Code adapted from https://github.com/LimelabsTech/eth-ecies  
Match (tested against) the JS code of Biletujo  
"""


BS = 16
def pad(data):
    padding = BS - len(data) % BS
    return data + padding * struct.pack("B", padding)

def unpad(data):
    return data[0:-data[-1]]

def AES256CbcDecrypt(hex_data, key=b'0'*32, iv=b'0'*16):
    data = bytearray.fromhex(hex_data)
    aes = AES.new(key, AES.MODE_CBC, iv)
    return unpad(aes.decrypt(data))

def AES256CbcEncrypt(bin_data, key=b'0'*32, iv=b'0'*16):
    aes = AES.new(key, AES.MODE_CBC, iv)
    return aes.encrypt(pad(bin_data))
    
def encode_key(pub_key):
    return pub_key.pointQ.x.to_bytes(32)+ pub_key.pointQ.y.to_bytes(32)  
    
def decode_key(encoded_pub_key):
    x = encoded_pub_key[:32]
    y = encoded_pub_key[32:]
    return ECC.EccPoint(int.from_bytes(x,byteorder='big'), int.from_bytes(y,byteorder='big')) 
    
def derive(private_key, pub_ecc_point):
    return (pub_ecc_point*private_key.d).x  
    
    
def EncryptMessage(publicKey_hex, plainText_string):
    if publicKey_hex[:2]=='0x':
        publicKey_hex=publicKey_hex[2:]
    
    # Generate the temporary key 
    ephemPrivKey = ECC.generate(curve='secp256r1')
    ephemPubKey = ephemPrivKey.public_key()
    ephemPubKeyEncoded = encode_key(ephemPubKey)
    
    # Load the public key
    publicKey = bytearray.fromhex(publicKey_hex)
    pub = ECC.EccPoint(int.from_bytes(publicKey[:int(len(publicKey)/2)],byteorder='big'), int.from_bytes(publicKey[int(len(publicKey)/2):],byteorder='big'))
    
    # ECDH => get the shared secret
    px = derive(ephemPrivKey,pub) 
    
    # compute the encription and MAC keys
    hash_px = SHA512.new(data=px.to_bytes()).digest()
    encryptionKey = hash_px[:32]
    macKey = hash_px[32:]
    
    # cipher the plain text
    iv = Random.get_random_bytes(16)
    plaintext = plainText_string.encode(encoding='utf_8') 
    ciphertext = AES256CbcEncrypt(plaintext,encryptionKey,iv)
    
    # compute the MAC
    dataToMac = iv + ephemPubKeyEncoded + ciphertext
    mac = hmac.new(macKey, dataToMac, 'sha256').digest()
    
    #build the output
    serializedCiphertext = iv + ephemPubKeyEncoded + mac + ciphertext
    return serializedCiphertext.hex()
    
    
    
def DecryptMessage(privateKey_hey, encrypted_hex):
    if privateKey_hey[:2]=='0x':
        privateKey_hey=privateKey_hey[2:]
    if encrypted_hex[:2]=='0x':
        encrypted_hex=encrypted_hex[2:]

    # get the components 
    encrypted = bytearray.fromhex(encrypted_hex)
    iv = encrypted[:16]
    ephemPubKeyEncoded = encrypted[16:80]
    mac = encrypted[80:112]
    ciphertext = encrypted[112:]
    
    # recover the temporary public key
    ephemPubKey = decode_key(ephemPubKeyEncoded)
    
    # load the private key
    privKey = ECC.construct(curve='secp256r1', d=int(privateKey_hey,16))
    
    # ECDH => get the shared secret
    px = derive(privKey, ephemPubKey)
    
    # compute the encription and MAC keys
    hash_px = SHA512.new(data=px.to_bytes()).digest()
    encryptionKey = hash_px[:32]
    macKey = hash_px[32:]
    
    # check the MAC
    dataToMac = iv + ephemPubKeyEncoded + ciphertext
    computed_mac = hmac.new(macKey, dataToMac, 'sha256').digest()
    if computed_mac!=mac:
        raise ValueError("MAC missmatch")
        
    #decipher the text
    plaintext = AES256CbcDecrypt(ciphertext.hex(), encryptionKey, iv)
    return plaintext.decode("utf-8")
