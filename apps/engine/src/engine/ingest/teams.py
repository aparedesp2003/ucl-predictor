"""Team name normalization and resolution across sources.

Resolution order for a (source, name, country) reference:

1. exact alias: ``team_aliases`` row for (source, name);
2. normalized name: a *unique* team whose canonical name or any alias normalizes to the same
   string, and whose country agrees when both countries are known;
3. manual override from ``team_overrides.csv``.

Nothing is guessed: an ambiguous normalized match that no override settles is unresolved.
"""

import csv
import difflib
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from pathlib import Path

from engine.db.models import Source

OVERRIDES_PATH = Path(__file__).with_name("team_overrides.csv")

_DROP_TOKENS = frozenset({"fc", "cf", "ac", "sc", "sk", "afc"})
# Letters NFKD does not decompose into base + accent.
_TRANSLIT = str.maketrans({"ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "đ": "d", "Đ": "d",
                           "ł": "l", "Ł": "l", "ı": "i", "ð": "d", "þ": "th"})  # fmt: skip


def normalize(name: str) -> str:
    """casefold, strip accents and punctuation, drop club-type tokens (FC, CF, AC, SC, SK, AFC)."""
    text = unicodedata.normalize("NFKD", name.translate(_TRANSLIT))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    tokens = re.sub(r"[^\w]+", " ", text).split()
    return " ".join(t for t in tokens if t not in _DROP_TOKENS)


class How(StrEnum):
    ALIAS = "alias"
    NORMALIZED = "normalized"
    OVERRIDE = "override"


@dataclass(frozen=True)
class Resolution:
    team_id: int | None
    how: How | None = None
    ambiguous: bool = False


@dataclass(frozen=True)
class Override:
    source: Source
    alias: str
    team_name: str
    reason: str


def load_overrides(path: Path = OVERRIDES_PATH) -> list[Override]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [
            Override(Source(r["source"]), r["alias"], r["team_name"], r.get("reason", ""))
            for r in csv.DictReader(f)
        ]


@dataclass
class _Team:
    name: str
    country: str | None


class TeamResolver:
    """In-memory index of teams and aliases; the loader keeps it in sync with the DB."""

    def __init__(self, overrides: list[Override] | None = None) -> None:
        self._teams: dict[int, _Team] = {}
        self._aliases: dict[tuple[Source, str], int] = {}
        self._by_norm: dict[str, set[int]] = defaultdict(set)
        self._overrides = {(o.source, o.alias): o.team_name for o in overrides or []}

    def add_team(self, team_id: int, name: str, country: str | None) -> None:
        self._teams[team_id] = _Team(name, country)
        self._by_norm[normalize(name)].add(team_id)

    def add_alias(self, team_id: int, source: Source, alias: str) -> None:
        self._aliases[(source, alias)] = team_id
        self._by_norm[normalize(alias)].add(team_id)

    def has_alias(self, source: Source, alias: str) -> bool:
        return (source, alias) in self._aliases

    def team_by_name(self, name: str) -> int | None:
        ids = [tid for tid, t in self._teams.items() if t.name == name]
        return ids[0] if len(ids) == 1 else None

    def override_target(self, source: Source, name: str) -> str | None:
        return self._overrides.get((source, name))

    def resolve(self, source: Source, name: str, country: str | None = None) -> Resolution:
        if (tid := self._aliases.get((source, name))) is not None:
            return Resolution(tid, How.ALIAS)

        candidates = {
            tid
            for tid in self._by_norm.get(normalize(name), ())
            if country is None or self._teams[tid].country in (None, country)
        }
        if len(candidates) == 1:
            return Resolution(candidates.pop(), How.NORMALIZED)

        target = self.override_target(source, name)
        if target is not None and (tid := self.team_by_name(target)) is not None:
            return Resolution(tid, How.OVERRIDE)
        return Resolution(None, ambiguous=len(candidates) > 1)

    def possible_duplicates(self, threshold: float = 0.85) -> list[tuple[str, str, str]]:
        """Same-country team pairs whose names look alike: (country, name_a, name_b)."""
        by_country: dict[str, list[_Team]] = defaultdict(list)
        for t in self._teams.values():
            by_country[t.country or "?"].append(t)
        out = []
        for country, teams in sorted(by_country.items()):
            for a, b in combinations(sorted(teams, key=lambda t: t.name), 2):
                na, nb = normalize(a.name), normalize(b.name)
                ta, tb = set(na.split()), set(nb.split())
                if (
                    ta <= tb
                    or tb <= ta
                    or difflib.SequenceMatcher(None, na, nb).ratio() >= threshold
                ):
                    out.append((country, a.name, b.name))
        return out
