import pytest

from ciris_engine.secrets.encryption import SecretsEncryption


def test_roundtrip_encryption():
    enc = SecretsEncryption()
    secret = "super_secret_value"
    encrypted, salt, nonce = enc.encrypt_secret(secret)

    assert len(salt) == 16
    assert len(nonce) == 12
    assert encrypted != secret.encode()

    decrypted = enc.decrypt_secret(encrypted, salt, nonce)
    assert decrypted == secret


def test_encryption_randomness():
    enc = SecretsEncryption()
    secret = "value"
    e1 = enc.encrypt_secret(secret)
    e2 = enc.encrypt_secret(secret)

    # salt or nonce should differ, leading to different ciphertext
    assert e1 != e2
    assert e1[0] != e2[0] or e1[1] != e2[1] or e1[2] != e2[2]


def test_invalid_master_key_length():
    with pytest.raises(ValueError):
        SecretsEncryption(b"short")


def test_rotate_master_key():
    enc = SecretsEncryption()
    original = enc.get_master_key()
    new_key = enc.rotate_master_key()

    assert len(new_key) == 32
    assert new_key != original


def test_rotate_master_key_invalid_length():
    enc = SecretsEncryption()
    with pytest.raises(ValueError):
        enc.rotate_master_key(b"bad")


def test_generate_key_from_password():
    salt = b"\x01" * 16
    key1, s1 = SecretsEncryption.generate_key_from_password("password", salt)
    key2, s2 = SecretsEncryption.generate_key_from_password("password", salt)

    assert s1 == s2 == salt
    assert key1 == key2

    key3, s3 = SecretsEncryption.generate_key_from_password("password")
    assert s3 != salt
    assert key3 != key1


def test_test_encryption_method():
    enc = SecretsEncryption()
    assert enc.test_encryption() is True


def test_rotate_with_supplied_key():
    enc = SecretsEncryption()
    new_key = b"z" * 32
    rotated = enc.rotate_master_key(new_key)
    assert rotated == new_key
    assert enc.get_master_key() == new_key

def test_decrypt_with_wrong_nonce():
    enc = SecretsEncryption()
    secret = "val"
    encrypted, salt, nonce = enc.encrypt_secret(secret)
    with pytest.raises(Exception):
        enc.decrypt_secret(encrypted, salt, b"badnonce123456")

