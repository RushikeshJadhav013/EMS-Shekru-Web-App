"""Chat helpers (MySQL-only; no Firebase)."""


def conversation_id(user1: int, user2: int) -> str:
    return "_".join(sorted([str(user1), str(user2)]))
