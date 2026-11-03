"""Primitivas de segurança: hash de senhas (Argon2) e tokens de sessão."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False
    except Exception:
        # Hash malformado etc.: tratar como credencial inválida, sem vazar detalhes.
        return False


def new_session_token() -> str:
    """Token aleatório não previsível (256 bits) — é o que vai no cookie."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Somente o hash do token é persistido; o token puro nunca vai ao banco."""
    import hashlib

    return hashlib.sha256(token.encode("utf-8")).hexdigest()
