from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Hash import SHA512
from ecdsa import SigningKey, SECP256k1, ECDH, VerifyingKey

import struct
import hmac


## Code adapted from https://github.com/LimelabsTech/eth-ecies
## Match (tested against) the JS code of Biletujo


BS = 16


def pad(data):
    padding = BS - len(data) % BS
    return data + padding * struct.pack("B", padding)


def unpad(data):
    return data[0 : -data[-1]]


def AES256CbcDecrypt(hex_data, key=b"0" * 32, iv=b"0" * 16):
    data = bytearray.fromhex(hex_data)
    aes = AES.new(key, AES.MODE_CBC, iv)
    return unpad(aes.decrypt(data))


def AES256CbcEncrypt(bin_data, key=b"0" * 32, iv=b"0" * 16):
    aes = AES.new(key, AES.MODE_CBC, iv)
    return aes.encrypt(pad(bin_data))


def EncryptMessage(publicKey_hex, plainText_string):
    if publicKey_hex[:2] == "0x":
        publicKey_hex = publicKey_hex[2:]
    publicKey_bin = bytearray.fromhex(publicKey_hex)

    # Generate the temporary key
    ecdh = ECDH(curve=SECP256k1)
    ecdh.generate_private_key()

    ephemPubKeyEncoded = bytearray.fromhex(ecdh.get_public_key().to_string().hex())

    # Load the public key
    publicKey = VerifyingKey.from_string(publicKey_bin, curve=SECP256k1)

    # ECDH => get the shared secret
    ecdh.load_received_public_key(publicKey)

    px = ecdh.generate_sharedsecret_bytes()

    # compute the encription and MAC keys
    hash_px = SHA512.new(data=px).digest()
    encryptionKey = hash_px[:32]
    macKey = hash_px[32:]

    # cipher the plain text
    iv = Random.get_random_bytes(16)
    plaintext = plainText_string.encode(encoding="utf_8")
    ciphertext = AES256CbcEncrypt(plaintext, encryptionKey, iv)

    # compute the MAC
    dataToMac = iv + bytearray([4]) + ephemPubKeyEncoded + ciphertext
    mac = hmac.new(macKey, dataToMac, "sha256").digest()

    # build the output
    serializedCiphertext = iv + bytearray([4]) + ephemPubKeyEncoded + mac + ciphertext
    return serializedCiphertext.hex()


def DecryptMessage(privateKey_hex, encrypted_hex):
    if privateKey_hex[:2] == "0x":
        privateKey_hex = privateKey_hex[2:]
    if encrypted_hex[:2] == "0x":
        encrypted_hex = encrypted_hex[2:]

    # get the components
    encrypted = bytearray.fromhex(encrypted_hex)
    iv = encrypted[:16]
    ephemPubKeyEncoded = encrypted[17:81]
    mac = encrypted[81:113]
    ciphertext = encrypted[113:]

    # recover the temporary public key
    ephemPubKey = VerifyingKey.from_string(ephemPubKeyEncoded, curve=SECP256k1)

    # load the private key
    priv_key = SigningKey.from_secret_exponent(int(privateKey_hex, 16), curve=SECP256k1)
    ecdh = ECDH(curve=SECP256k1, private_key=priv_key)

    # ECDH => get the shared secret
    ecdh.load_received_public_key(ephemPubKey)
    px = ecdh.generate_sharedsecret_bytes()

    # compute the encription and MAC keys
    hash_px = SHA512.new(data=px).digest()
    encryptionKey = hash_px[:32]
    macKey = hash_px[32:]

    # check the MAC
    dataToMac = iv + bytearray([4]) + ephemPubKeyEncoded + ciphertext
    computed_mac = hmac.new(macKey, dataToMac, "sha256").digest()
    if computed_mac != mac:
        raise ValueError("MAC missmatch")

    # decipher the text
    plaintext = AES256CbcDecrypt(ciphertext.hex(), encryptionKey, iv)
    return plaintext.decode("utf-8")
