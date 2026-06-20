from .exceptions import InvalidHashError as InvalidHashError
from .exceptions import VerificationError as VerificationError

class Type:
    ID: Type

class PasswordHasher:
    def __init__(
        self,
        time_cost: int = ...,
        memory_cost: int = ...,
        parallelism: int = ...,
        hash_len: int = ...,
        salt_len: int = ...,
        encoding: str = ...,
        type: Type = ...,
    ) -> None: ...
    def hash(self, password: str) -> str: ...
    def verify(self, hash: str, password: str) -> bool: ...
    def check_needs_rehash(self, hash: str) -> bool: ...
