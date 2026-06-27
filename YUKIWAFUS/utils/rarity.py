# ── Central Rarity Definitions ────────────────────────────────────────────────
# Maps rarity number → (emoji, name)
# Used by /upload, /rarity, spawn, and harem display.

RARITY_MAP: dict[int, tuple[str, str]] = {
    1:  ("⚪️", "Common"),
    2:  ("🟣", "Rare"),
    3:  ("🟡", "Legendary"),
    4:  ("🟢", "Medium"),
    5:  ("💮", "Special Edition"),
    6:  ("🔮", "Limited Edition"),
    7:  ("💸", "Premium Edition"),
    8:  ("🌤",  "Summer"),
    9:  ("🎐",  "Celestial"),
    10: ("❄️", "Winter"),
    11: ("💝",  "Valentine"),
    12: ("🎃",  "Halloween"),
    13: ("🎄",  "Christmas Special"),
    14: ("🪐",  "Omniversal"),
    15: ("🎭",  "Cosplay Master"),
    16: ("🧧",  "Events"),
    17: ("🍑",  "Echhi"),
    18: ("🎗️", "AMV Edition"),
    19: ("🌟",  "Luminous"),
    20: ("🌧",  "Rainy"),
    22: ("🍭",  "Winter event"),
}

# name → emoji  (quick lookup for display)
RARITY_EMOJI: dict[str, str] = {name: emoji for _, (emoji, name) in RARITY_MAP.items()}

# all valid rarity names
VALID_RARITY_NAMES: set[str] = set(RARITY_EMOJI.keys())

# Also include the legacy API rarities so existing waifus still display correctly
_LEGACY = {
    "Common":    "⚪️",
    "Uncommon":  "🟢",
    "Rare":      "🟣",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}
for _n, _e in _LEGACY.items():
    RARITY_EMOJI.setdefault(_n, _e)


def rarity_by_number(num: int) -> tuple[str, str] | None:
    """Return (emoji, name) for a rarity number, or None if invalid."""
    return RARITY_MAP.get(num)


def rarity_emoji(name: str) -> str:
    """Return emoji for a rarity name (legacy or new), default '◈'."""
    return RARITY_EMOJI.get(name, "◈")


def rarity_display_list() -> str:
    """Build a formatted string of all rarities for /rarity command."""
    lines = []
    for num in sorted(RARITY_MAP):
        emoji, name = RARITY_MAP[num]
        lines.append(f"  <code>{num:>2}.</code> {emoji} {name}")
    return "\n".join(lines)
