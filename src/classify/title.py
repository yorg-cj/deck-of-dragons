"""
Title assignment within a House.
Combines spaCy NER (entity type detection) with house-specific logic
to determine whether the primary actor is individual or collective,
then selects the appropriate Title.
"""
import spacy

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


# GDELT actor type codes → individual vs collective
_COLLECTIVE_CAMEO = {"GOV", "MIL", "NGO", "IGO", "UNK", "BUS"}
_INDIVIDUAL_CAMEO = {"ELITES", "LEADER", "COP"}

# spaCy entity labels
_COLLECTIVE_LABELS = {"GPE", "ORG", "NORP", "FAC"}  # nations, orgs, groups
_INDIVIDUAL_LABELS = {"PERSON"}


def assign(text: str, house: str, cameo_actor_type: str | None = None) -> str:
    """
    Assign a Title within the given House based on the primary entity in the text.

    Args:
        text             — article text (headline + excerpt)
        house            — the House already assigned by HouseClassifier
        cameo_actor_type — optional GDELT Actor1Type1Code for higher-confidence typing

    Returns:
        Title string, e.g. 'The Warlord'
    """
    is_individual = _detect_individual(text, cameo_actor_type)
    return _title_for_house(house, is_individual, text)


def _detect_individual(text: str, cameo_actor_type: str | None) -> bool:
    """True if the primary actor in the text is an individual person."""
    # CAMEO actor type is the most reliable signal when available
    if cameo_actor_type:
        if cameo_actor_type in _INDIVIDUAL_CAMEO:
            return True
        if cameo_actor_type in _COLLECTIVE_CAMEO:
            return False

    # Fall back to spaCy NER
    nlp = _get_nlp()
    doc = nlp(text[:400])

    entity_labels = [ent.label_ for ent in doc.ents]
    has_person     = "PERSON" in entity_labels
    has_collective = any(l in entity_labels for l in _COLLECTIVE_LABELS)

    # A named person with no nation/org context → individual
    # A named person alongside nations/orgs → the person is probably representing
    # a collective, so treat as collective for title purposes
    return has_person and not has_collective


def _title_for_house(house: str, is_individual: bool, text: str) -> str:
    text_lower = text.lower()

    if house == "High House War":
        if is_individual:
            # Aggressive commander vs. covert operator
            return "The Assassin" if any(w in text_lower for w in ("assassin", "covert", "killed", "targeted")) else "The Warlord"
        return "The Army"

    if house == "High House Coin":
        if is_individual:
            return "The Merchant"
        # Nation imposing vs. institution managing
        return "The Throne" if any(w in text_lower for w in ("central bank", "federal reserve", "imf", "world bank")) else "The King"

    if house == "High House Shadow":
        if is_individual:
            return "The Assassin"
        # Weaver = narrative/influence ops; Knight = direct covert action
        return "The Weaver" if any(w in text_lower for w in ("disinformation", "propaganda", "influence", "narrative")) else "The Knight"

    if house == "High House Life":
        if is_individual:
            return "The Magi"   # scientist, doctor, expert
        return "The King"       # nation or institution driving the event

    if house == "High House Iron":
        if is_individual:
            return "The Magi"   # tech visionary, researcher
        return "The Merchant"   # corporation or industrial entity

    if house == "High House Words":
        if is_individual:
            return "The Herald"  # spokesperson, journalist, diplomat
        return "The Weaver"      # media org, state broadcaster, platform

    if house == "High House Chains":
        if is_individual:
            return "The Assassin"  # enforcer, debt collector, warden
        return "The Knight"        # occupying force, binding institution

    return "The Throne"  # fallback
