"""SSH credential helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SSHCredentials:
    """Normalized credential payload from CLI/config."""

    host: str
    username: str
    port: int = 22
    auth_method: str = "password"
    password: Optional[str] = None
    key_path: Optional[str] = None
    passphrase: Optional[str] = None
    timeout: int = 20

    def validate(self) -> None:
        if self.auth_method == "password" and not self.password:
            raise ValueError("Password authentication selected but no password provided")
        if self.auth_method == "key" and not self.key_path:
            raise ValueError("Key authentication selected but no key_path provided")
