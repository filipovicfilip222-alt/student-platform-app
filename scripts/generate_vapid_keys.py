"""Generiše VAPID par (Public/Private) za Web Push (KORAK 1 Prompta 2).

VAPID = Voluntary Application Server Identification (RFC 8292). Push
servisi (Mozilla Autopush, Google FCM, Apple) zahtevaju da server koji
šalje push poruku potpiše JWT sa privatnim ključem ECDSA P-256 krive,
i da klijentskom browseru pri ``PushManager.subscribe()`` proslediš
pripadajući javni ključ. Tako svaki push servis može da verifikuje
autorstvo bez deljenja simetričnog secret-a.

Ovaj skript štampa par u formatu kompatibilnom sa ``pywebpush`` /
Web Push standardom:
  - **Privatni ključ**: base64-url enkodirani 32-bajtni raw scalar
    EC P-256 privatnog ključa (NE PEM blob — ``pywebpush.webpush(vapid_private_key=...)``
    direktno prihvata bilo koji od ova 2 formata, ali raw je manji i
    konzistentan sa ``py_vapid`` semantikom).
  - **Javni ključ**: base64-url enkodirani 65-bajtni nezakomprimovani
    EC P-256 javni ključ (``\x04`` prefiks + 32B X + 32B Y). Ovo je
    eksplicitan format koji ``PushManager.subscribe({applicationServerKey})``
    očekuje na frontendu.

Pokretanje (sa Docker compose stack-a):

    docker compose run --rm backend python scripts/generate_vapid_keys.py

Output kopiraj u ``backend/.env`` (i u ``.env.example`` kao prazne stub-ove
ako ih commit-uješ; ne commit-uj realne ključeve).

Ne traži dodatne dependency-je — koristi ``cryptography`` koji je već u
``requirements.txt`` (hard dep ``pywebpush``-a).
"""

from __future__ import annotations

import base64

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url_encode(data: bytes) -> str:
    """Base64-URL enkoder bez paddinga (Web Push spec)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_vapid_pair() -> tuple[str, str]:
    """Vrati (public_key_b64url, private_key_b64url).

    Reprodukuje algoritam iz ``py_vapid.Vapid01.generate_keys`` ali bez
    dodatne zavisnosti — sve preko ``cryptography``.
    """
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

    private_numbers = private_key.private_numbers()
    raw_private = private_numbers.private_value.to_bytes(32, "big")

    public_numbers = private_key.public_key().public_numbers()
    raw_public = (
        b"\x04"
        + public_numbers.x.to_bytes(32, "big")
        + public_numbers.y.to_bytes(32, "big")
    )

    return _b64url_encode(raw_public), _b64url_encode(raw_private)


def main() -> None:
    public_key, private_key = generate_vapid_pair()

    print("# ── VAPID par generisan — kopiraj u backend/.env ────────────")
    print(f"VAPID_PUBLIC_KEY={public_key}")
    print(f"VAPID_PRIVATE_KEY={private_key}")
    print("VAPID_SUBJECT=mailto:dev@studentska-platforma.local")
    print()
    print(f"# Public key length:  {len(public_key)} chars  (host → frontend)")
    print(f"# Private key length: {len(private_key)} chars  (server only — NE commit-uj)")


if __name__ == "__main__":
    main()
