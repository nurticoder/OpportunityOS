"""Hard filters evaluated before ranking, using verified profile facts."""
import re

ALIASES = {"kyrgyz": "kyrgyzstan", "kyrgyz republic": "kyrgyzstan", "hong kong sar": "hong kong",
           "hk": "hong kong", "bachelor": "undergraduate", "bachelors": "undergraduate",
           "bachelor's": "undergraduate", "bs": "undergraduate", "beng": "undergraduate",
           "masters": "master", "master's": "master", "ms": "master", "doctoral": "phd"}


def canonical(value):
    value = value.casefold().strip().rstrip(".")
    return ALIASES.get(value, value)


def hard_filter(item, facts):
    reasons, unknown = [], []
    criteria = item.get("eligibility_requirements", {})
    for criterion, key in (("nationality", "citizenship"), ("country_of_study", "location"),
                           ("level", "academic_level")):
        allowed = criteria.get(criterion)
        fact = facts.get(key, {})
        if not allowed:
            unknown.append(criterion)
            continue
        if any(canonical(v) in {"all", "any", "worldwide", "all nationalities"} for v in allowed):
            continue
        if not fact.get("verified") or not fact.get("value"):
            unknown.append("Verify profile " + key)
            continue
        values = {canonical(v) for v in allowed}
        # Broad or prose requirements need manual interpretation rather than false rejection.
        known = {"kyrgyzstan", "hong kong", "india", "china", "united states", "uk", "kenya",
                 "ethiopia", "undergraduate", "master", "phd", "graduate", "yemen"}
        if not values <= known:
            unknown.append("Interpret " + criterion)
            continue
        actual = {canonical(v) for v in re.split(r"[,;/]", fact["value"])}
        if criterion == "level" and "graduate" in values:
            values |= {"master", "phd"}
        if not actual & values:
            reasons.append(f"{criterion} requires {', '.join(allowed)}")
    return reasons, unknown
