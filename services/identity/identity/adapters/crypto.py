"""Cryptography adapter. No password or Bearer tokens are persisted in cleartext."""
from secrets import token_urlsafe

from pwdlib import PasswordHash


class Argon2Passwords:
    def __init__(self):
        self.hasher = PasswordHash.recommended()
        self.dummy_hash = self.hasher.hash(token_urlsafe(32))

    def hash(self, password: str) -> str:
        return self.hasher.hash(password)

    def verify(self, password: str, stored_hash: str) -> bool:
        return self.hasher.verify(password, stored_hash)

    def dummy_verify(self, password: str) -> None:
        self.hasher.verify(password, self.dummy_hash)


class RandomTokenGenerator:
    def new_token(self) -> str:
        return token_urlsafe(32)
