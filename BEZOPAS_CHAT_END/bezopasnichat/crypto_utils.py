from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
from Crypto.Hash import SHA256
import base64

RSA_KEY_LENGTH = 2048
AES_KEY_LENGTH = 32  # 256 бит

def generate_rsa_keypair():
    key = RSA.generate(RSA_KEY_LENGTH)
    private_key = key.export_key().decode()
    public_key = key.publickey().export_key().decode()
    return private_key, public_key

def generate_aes_key():
    return get_random_bytes(AES_KEY_LENGTH)

def encrypt_aes_key_with_rsa(aes_key, public_key_pem):
    recipient_key = RSA.import_key(public_key_pem)
    cipher_rsa = PKCS1_OAEP.new(recipient_key, hashAlgo=SHA256)
    enc_key = cipher_rsa.encrypt(aes_key)
    return base64.b64encode(enc_key).decode()

def decrypt_aes_key_with_rsa(encrypted_aes_key_b64, private_key_pem):
    private_key = RSA.import_key(private_key_pem)
    cipher_rsa = PKCS1_OAEP.new(private_key, hashAlgo=SHA256)
    enc_key = base64.b64decode(encrypted_aes_key_b64)
    aes_key = cipher_rsa.decrypt(enc_key)
    return aes_key