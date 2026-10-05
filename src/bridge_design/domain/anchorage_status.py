"""Shared straight/hooked development classification by available length."""

RECTO_Y_GANCHO = "RECTO Y CON GANCHO"
SOLO_GANCHO = "SOLO GANCHO"
NO_CUMPLE = "NO CUMPLE"
PENDIENTE = "PENDIENTE DETALLE"


def anchorage_status(available_cm, straight_cm, hooked_cm):
    """Classify lengths with hooked <= straight; hook fit is a separate detail."""
    if hooked_cm > straight_cm + 1e-8:
        raise ValueError(
            "Revisar longitudes de anclaje: ld con gancho supera ld recto; "
            "no se puede aplicar la clasificacion de tres estados."
        )
    if available_cm is None:
        return PENDIENTE
    straight = available_cm+1e-8 >= straight_cm
    hooked = available_cm+1e-8 >= hooked_cm
    if straight and hooked:
        return RECTO_Y_GANCHO
    if hooked:
        return SOLO_GANCHO
    return NO_CUMPLE


def anchorage_passes(status):
    return status in (RECTO_Y_GANCHO, SOLO_GANCHO)
