"""Core fare-splitting algorithm.

The trip is processed segment by segment.  For every segment the passengers
on board share that segment's integer-cent cost equally.  When the cost is
not divisible, each leftover cent goes to the rider with the largest
*deficit* — the difference between a passenger's cumulative theoretical
(exact fractional) share and the amount already allocated to them.  The
passenger id is used only as a deterministic tie-breaker.

This guarantees:

* conservation — the allocated amounts always sum to the total cost;
* order independence — permuting the passenger input never changes the
  result, because deficits are exact fractions and ties fall back to ids.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction


@dataclass(frozen=True)
class Ride:
    """One passenger's presence on the trip: boards at ``board``, alights at
    ``alight`` (station indices; passenger occupies segments board..alight-1)."""

    passenger_id: str
    board: int
    alight: int


@dataclass(frozen=True)
class SegmentSplit:
    """Allocation detail for a single segment."""

    index: int
    cost_cents: int
    passengers: tuple[str, ...]  # riders on this segment, sorted by id
    shares: dict[str, int] = field(default_factory=dict)  # id -> cents


def split_fares(
    costs: list[int], rides: list[Ride]
) -> tuple[dict[str, int], list[SegmentSplit]]:
    """Split ordered segment ``costs`` (integer cents) among ``rides``.

    Returns ``(totals, details)``: per-passenger total cents and per-segment
    allocation details.  Callers must validate inputs beforehand (see
    ``app.models``); a charged segment without riders is rejected there.
    """
    n_segments = len(costs)

    on_board: list[list[str]] = [[] for _ in range(n_segments)]
    for ride in rides:
        for seg in range(ride.board, ride.alight):
            on_board[seg].append(ride.passenger_id)

    theoretical: dict[str, Fraction] = {r.passenger_id: Fraction(0) for r in rides}
    allocated: dict[str, int] = {r.passenger_id: 0 for r in rides}
    details: list[SegmentSplit] = []

    for index, cost in enumerate(costs):
        riders = sorted(on_board[index])
        if not riders:
            # Only reachable for free (cost 0) segments; charged empty
            # segments are rejected during request validation.
            details.append(SegmentSplit(index=index, cost_cents=cost, passengers=()))
            continue

        base, remainder = divmod(cost, len(riders))
        shares = {pid: base for pid in riders}
        for pid in riders:
            theoretical[pid] += Fraction(cost, len(riders))
            allocated[pid] += base

        if remainder:
            # Deficit = theoretical - allocated.  Sorting by
            # (allocated - theoretical, id) ascending puts the largest
            # deficit first and breaks ties deterministically by id.
            by_deficit = sorted(
                riders, key=lambda pid: (allocated[pid] - theoretical[pid], pid)
            )
            for pid in by_deficit[:remainder]:
                shares[pid] += 1
                allocated[pid] += 1

        details.append(
            SegmentSplit(
                index=index, cost_cents=cost, passengers=tuple(riders), shares=shares
            )
        )

    return allocated, details
