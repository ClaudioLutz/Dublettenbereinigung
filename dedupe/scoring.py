from __future__ import annotations

from dataclasses import dataclass
from rapidfuzz import fuzz


@dataclass(frozen=True)
class MatchResult:
    i: int
    j: int
    score: float
    name_score: float
    addr_score: float
    reason: str


def score_pair(i: int, j: int, cols: dict[str, object]) -> MatchResult | None:
    yi = int(cols["year"][i])
    yj = int(cols["year"][j])
    if yi != -1 and yj != -1 and yi != yj:
        return None

    ni = cols["full_name"].iloc[i]
    nj = cols["full_name"].iloc[j]
    name_score = float(fuzz.WRatio(ni, nj))

    plz_i = cols["plz"].iloc[i]
    plz_j = cols["plz"].iloc[j]
    house_i = cols["house"].iloc[i]
    house_j = cols["house"].iloc[j]
    street_i = cols["street"].iloc[i]
    street_j = cols["street"].iloc[j]

    plz_score = 100.0 if (plz_i != "" and plz_i == plz_j) else 0.0
    house_score = 100.0 if (house_i != "" and house_i == house_j) else 0.0
    street_score = float(fuzz.WRatio(street_i, street_j)) if street_i and street_j else 0.0

    addr_score = 0.5 * plz_score + 0.25 * house_score + 0.25 * street_score

    final = 0.7 * name_score + 0.3 * addr_score

    if plz_i and plz_j and plz_i != plz_j and final < 95:
        return None

    return MatchResult(i=i, j=j, score=final, name_score=name_score, addr_score=addr_score, reason="weighted_name_addr")
