"""CLI administrativo local. Provisionamento de usuários SEM credenciais padrão.

Uso (PowerShell):
    python -m app.cli create-user --name "Ana" --email ana@exemplo.com --role instructor
A senha é solicitada interativamente e nunca ecoada no terminal.
"""

import getpass
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User


def _prompt_password() -> str:
    password = getpass.getpass("Senha: ")
    confirm = getpass.getpass("Confirmar senha: ")
    if password != confirm:
        print("As senhas não coincidem.", file=sys.stderr)
        sys.exit(1)
    if len(password) < 8:
        print("A senha deve ter pelo menos 8 caracteres.", file=sys.stderr)
        sys.exit(1)
    return password


def create_user(name: str, email: str, role: str) -> None:
    role_enum = Role(role)
    if role_enum == Role.COORDINATOR:
        print(
            "AVISO: atribuição de papel privilegiado (coordinator) — confirme a autorização."
        )
    normalized = email.strip().lower()
    password = _prompt_password()
    with SessionLocal() as db:
        exists = db.scalar(select(User).where(User.email == normalized))
        if exists:
            print("Já existe usuário com este e-mail.", file=sys.stderr)
            sys.exit(1)
        user = User(
            name=name,
            email=normalized,
            password_hash=hash_password(password),
            role=role_enum,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Usuário criado: {user.email} (papel: {role_enum.value})")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] != "create-user":
        print("Uso: python -m app.cli create-user --name NOME --email EMAIL --role ROLE")
        sys.exit(2)
    args = sys.argv[2:]
    opts: dict[str, str] = {}
    for i in range(0, len(args) - 1, 2):
        opts[args[i].lstrip("-")] = args[i + 1]
    if not {"name", "email", "role"} <= opts.keys():
        print("Uso: python -m app.cli create-user --name NOME --email EMAIL --role ROLE")
        sys.exit(2)
    if opts["role"] not in ("participant", "instructor", "coordinator"):
        print("Papel inválido. Use: participant | instructor | coordinator", file=sys.stderr)
        sys.exit(2)
    create_user(opts["name"], opts["email"], opts["role"])


if __name__ == "__main__":
    main()
