"""Carpool fare-splitting API."""

from __future__ import annotations

from fastapi import FastAPI

from .models import SegmentDetail, SplitRequest, SplitResponse
from .splitter import Ride, split_fares

app = FastAPI(
    title="Carpool Fare Splitter",
    version="1.0.0",
    summary="Split ordered trip segment costs fairly among passengers.",
)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": "carpool-fare-splitter", "docs": "/docs"}


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/split", response_model=SplitResponse)
def split(request: SplitRequest) -> SplitResponse:
    rides = [Ride(p.id, p.board, p.alight) for p in request.passengers]
    totals, details = split_fares(request.segments, rides)
    return SplitResponse(
        total_cents=sum(request.segments),
        # Sorted by id so the response is byte-identical regardless of the
        # passenger input order.
        passenger_totals=dict(sorted(totals.items())),
        segments=[
            SegmentDetail(
                index=d.index,
                cost_cents=d.cost_cents,
                passengers=list(d.passengers),
                shares=d.shares,
            )
            for d in details
        ],
    )
