import json
from dataclasses import dataclass
from django.core import signing
from django.utils import timezone

from .models import Usuario, UsuarioRol
from .tt_security import verify_and_upgrade_password

COOKIE_NAME = "tt_auth"
SIGNING_SALT = "talenttrack.tt_auth"
MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days


@dataclass
class TTUser:
    id: str
    email: str
    empresa_id: str | None
    empleado_id: str | None
    roles: list[str]

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.email or "Usuario"

    def has_role(self, name: str) -> bool:
        return name in (self.roles or [])

    @property
    def is_superadmin(self) -> bool:
        return self.has_role("SUPERADMIN")


class TTAnonymous:
    is_authenticated = False
    id = None
    email = ""
    empresa_id = None
    empleado_id = None
    roles: list[str] = []

    @property
    def display_name(self) -> str:
        return "Invitado"

    def has_role(self, name: str) -> bool:
        return False

    @property
    def is_superadmin(self) -> bool:
        return False


def _sign_payload(payload: dict) -> str:
    signer = signing.TimestampSigner(salt=SIGNING_SALT)
    raw = json.dumps(payload, separators=(",", ":"), default=str)
    return signer.sign(raw)


def _unsign_payload(signed_value: str) -> dict | None:
    signer = signing.TimestampSigner(salt=SIGNING_SALT)
    try:
        raw = signer.unsign(signed_value, max_age=MAX_AGE_SECONDS)
        return json.loads(raw)
    except Exception:
        return None


def load_user_from_cookie(request) -> TTUser | TTAnonymous:
    signed_value = request.COOKIES.get(COOKIE_NAME)
    if not signed_value:
        return TTAnonymous()
    payload = _unsign_payload(signed_value)
    if not payload:
        return TTAnonymous()
    if "id" not in payload or "email" not in payload:
        return TTAnonymous()
    return TTUser(
        id=payload["id"],
        email=payload.get("email") or "",
        empresa_id=payload.get("empresa_id"),
        empleado_id=payload.get("empleado_id"),
        roles=payload.get("roles") or [],
    )


def build_cookie_for_user(user: Usuario, roles: list[str]) -> str:
    payload = {
        "id": str(user.id),
        "email": user.email,
        "empresa_id": str(user.empresa_id) if user.empresa_id else None,
        "empleado_id": str(user.empleado_id) if user.empleado_id else None,
        "roles": roles,
        "iat": timezone.now().isoformat(),
    }
    return _sign_payload(payload)


def authenticate_login(login: str, password: str) -> tuple[Usuario | None, list[str], str | None]:
    # Returns (usuario, roles, error_message)
    login_norm = (login or "").strip().lower()
    if not login_norm or not password:
        return None, [], "Ingresa usuario y contraseña."

    qs = Usuario.objects.all()
    user = qs.filter(email__iexact=login_norm).first()
    if not user:
        user = qs.filter(phone=(login or "").strip()).first()
    if not user:
        return None, [], "Usuario no encontrado."

    ok, upgraded = verify_and_upgrade_password(user.hash_password, password)
    if not ok:
        return None, [], "Contraseña incorrecta."

    if upgraded:
        user.hash_password = upgraded

    user.ultimo_acceso = timezone.now()
    user.save(update_fields=["hash_password", "ultimo_acceso"] if upgraded else ["ultimo_acceso"])

    role_names = list(
        UsuarioRol.objects.filter(usuario_id=user.id)
        .select_related("rol")
        .values_list("rol__nombre", flat=True)
    )
    return user, role_names, None
