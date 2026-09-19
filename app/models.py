"""Request/response schemas.  Invalid input is rejected with HTTP 422."""

from __future__ import annotations

from pydantic import BaseModel, Field, NonNegativeInt, model_validator


class Passenger(BaseModel):
    id: str = Field(min_length=1, description="Unique passenger identifier")
    board: NonNegativeInt = Field(description="Boarding station index (0-based)")
    alight: NonNegativeInt = Field(description="Alighting station index (0-based)")

    @model_validator(mode="after")
    def _check_interval(self) -> "Passenger":
        if self.alight <= self.board:
            raise ValueError(
                f"passenger {self.id!r}: alight station {self.alight} must be "
                f"greater than board station {self.board}"
            )
        return self


class SplitRequest(BaseModel):
    segments: list[NonNegativeInt] = Field(
        min_length=1,
        description="Ordered per-segment costs in integer cents; segment i "
        "connects station i and station i+1",
    )
    passengers: list[Passenger] = Field(
        default_factory=list, description="Passengers with board/alight stations"
    )

    @model_validator(mode="after")
    def _check_trip(self) -> "SplitRequest":
        n_segments = len(self.segments)
        last_station = n_segments  # stations are 0..n_segments

        seen: set[str] = set()
        for p in self.passengers:
            if p.id in seen:
                raise ValueError(f"duplicate passenger id: {p.id!r}")
            seen.add(p.id)
            if p.alight > last_station:
                raise ValueError(
                    f"passenger {p.id!r}: alight station {p.alight} out of range; "
                    f"trip has {n_segments} segment(s), stations 0..{last_station}"
                )

        for idx, cost in enumerate(self.segments):
            if cost > 0 and not any(
                p.board <= idx < p.alight for p in self.passengers
            ):
                raise ValueError(
                    f"segment {idx} costs {cost} cent(s) but has no passengers "
                    "on board"
                )
        return self


class SegmentDetail(BaseModel):
    index: int
    cost_cents: int
    passengers: list[str]
    shares: dict[str, int]


class SplitResponse(BaseModel):
    total_cents: int
    passenger_totals: dict[str, int]
    segments: list[SegmentDetail]
