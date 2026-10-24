"""Which categories are in the hat right now. Used by the home screen summary and (Session 5)
the draw itself, so both always agree.

Rules:
  • Normal mode: exactly the chosen categories.
  • Random mode: every category except the excluded ones.
  • Spicy is never chosen through the hat. It's in only when BOTH people have their
    own Spicy switch on, in either mode.
"""

from .models import CATEGORIES

HAT = tuple(c for c in CATEGORIES if c != "spicy")  # what can be picked or excluded


def categories_in_play(settings: dict, spicy_both: bool) -> list[str]:
    if settings.get("random"):
        excluded = set(settings.get("excluded", []))
        ids = [c for c in HAT if c not in excluded]
    else:
        chosen = set(settings.get("categories", []))
        ids = [c for c in HAT if c in chosen]
    if spicy_both:
        ids.append("spicy")
    return ids
