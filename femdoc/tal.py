"""Talformatering til rapporten: dansk decimalkomma og ingen 1.23e+03-notation."""
from __future__ import annotations
import math


def tal(v, cifre: int = 3) -> str:
    """Formaterer et tal med ca. `cifre` betydende cifre og decimalkomma.

    Store tal afrundes til heltal i stedet for at blive skrevet med eksponent,
    så fx en reaktion på 1234,7 kN bliver "1235" og ikke "1.23e+03".
    """
    if v is None:
        return "–"
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return str(v)
    if math.isnan(v):
        return "–"
    if math.isinf(v):
        return "∞" if v > 0 else "−∞"
    if v == 0:
        return "0"
    a = abs(v)
    if a < 1e-4:
        s = f"{v:.{max(cifre - 1, 0)}e}"
    else:
        decimaler = min(max(cifre - 1 - math.floor(math.log10(a)), 0), 6)
        s = f"{v:.{decimaler}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        if s in ("-0", ""):
            s = "0"
    return s.replace(".", ",")
