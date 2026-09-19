"""Tests for the /split endpoint and the splitting algorithm."""

from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def post(payload: dict):
    return client.post("/split", json=payload)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_even_split_single_segment():
    resp = post(
        {
            "segments": [100],
            "passengers": [
                {"id": "alice", "board": 0, "alight": 1},
                {"id": "bob", "board": 0, "alight": 1},
            ],
        }
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_cents"] == 100
    assert body["passenger_totals"] == {"alice": 50, "bob": 50}
    assert body["segments"] == [
        {
            "index": 0,
            "cost_cents": 100,
            "passengers": ["alice", "bob"],
            "shares": {"alice": 50, "bob": 50},
        }
    ]


def test_partial_overlap_worked_example():
    resp = post(
        {
            "segments": [100, 101, 100],
            "passengers": [
                {"id": "alice", "board": 0, "alight": 3},
                {"id": "bob", "board": 0, "alight": 2},
                {"id": "carol", "board": 2, "alight": 3},
            ],
        }
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_cents"] == 301
    # Segment 1 (101 cents) leaves a 1-cent remainder; alice and bob have
    # equal deficits, so the id tie-break gives it to alice.
    assert body["passenger_totals"] == {"alice": 151, "bob": 100, "carol": 50}
    assert sum(body["passenger_totals"].values()) == body["total_cents"]
    for seg in body["segments"]:
        assert sum(seg["shares"].values()) == seg["cost_cents"]


def test_remainder_follows_deficit_not_id():
    # Two 1-cent segments.  alice rides both; bob only the first, carol only
    # the second.  On segment 1 alice is first by id but carol carries the
    # larger deficit, so carol receives the leftover cent.
    resp = post(
        {
            "segments": [1, 1],
            "passengers": [
                {"id": "alice", "board": 0, "alight": 2},
                {"id": "bob", "board": 0, "alight": 1},
                {"id": "carol", "board": 1, "alight": 2},
            ],
        }
    )
    assert resp.status_code == 200
    assert resp.json()["passenger_totals"] == {"alice": 1, "bob": 0, "carol": 1}


def test_remainder_alternates_over_segments():
    # Two riders, three 1-cent segments: the extra cent must alternate so
    # the split stays as fair as possible (2 vs 1, not 3 vs 0).
    resp = post(
        {
            "segments": [1, 1, 1],
            "passengers": [
                {"id": "a", "board": 0, "alight": 3},
                {"id": "b", "board": 0, "alight": 3},
            ],
        }
    )
    assert resp.status_code == 200
    assert resp.json()["passenger_totals"] == {"a": 2, "b": 1}


def test_tie_broken_by_passenger_id():
    resp = post(
        {
            "segments": [1],
            "passengers": [
                {"id": "zoe", "board": 0, "alight": 1},
                {"id": "amy", "board": 0, "alight": 1},
            ],
        }
    )
    assert resp.status_code == 200
    assert resp.json()["passenger_totals"] == {"amy": 1, "zoe": 0}


def test_free_empty_segment_is_allowed():
    resp = post(
        {
            "segments": [0, 100],
            "passengers": [{"id": "alice", "board": 1, "alight": 2}],
        }
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["passenger_totals"] == {"alice": 100}
    assert body["segments"][0] == {
        "index": 0,
        "cost_cents": 0,
        "passengers": [],
        "shares": {},
    }


def test_passenger_input_order_does_not_change_result():
    passengers = [
        {"id": "alice", "board": 0, "alight": 4},
        {"id": "bob", "board": 1, "alight": 3},
        {"id": "carol", "board": 0, "alight": 2},
        {"id": "dan", "board": 2, "alight": 4},
        {"id": "erin", "board": 3, "alight": 4},
    ]
    segments = [101, 203, 307, 409]
    responses = []
    for perm in itertools.permutations(passengers):
        resp = post({"segments": segments, "passengers": list(perm)})
        assert resp.status_code == 200
        responses.append(resp.json())
    first = responses[0]
    for other in responses[1:]:
        assert other == first
    assert sum(first["passenger_totals"].values()) == sum(segments)


def test_conservation_on_larger_trip():
    segments = [999, 1, 0, 12345, 77, 2]
    passengers = [
        {"id": f"p{i}", "board": i % 3, "alight": 4 + (i % 3)}
        for i in range(7)
    ]
    resp = post({"segments": segments, "passengers": passengers})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_cents"] == sum(segments)
    assert sum(body["passenger_totals"].values()) == sum(segments)
    for seg in body["segments"]:
        assert sum(seg["shares"].values()) == seg["cost_cents"]


# ---------------------------------------------------------------------------
# Validation -> 422
# ---------------------------------------------------------------------------

def test_charged_segment_without_riders_is_422():
    resp = post(
        {
            "segments": [100, 50],
            "passengers": [{"id": "alice", "board": 0, "alight": 1}],
        }
    )
    assert resp.status_code == 422
    assert "no passengers on board" in resp.text


def test_alight_not_after_board_is_422():
    resp = post(
        {
            "segments": [100, 100],
            "passengers": [{"id": "alice", "board": 1, "alight": 1}],
        }
    )
    assert resp.status_code == 422
    assert "must be greater than board station" in resp.text


def test_station_out_of_range_is_422():
    resp = post(
        {
            "segments": [100, 100],
            "passengers": [{"id": "alice", "board": 0, "alight": 3}],
        }
    )
    assert resp.status_code == 422
    assert "out of range" in resp.text


def test_duplicate_passenger_id_is_422():
    resp = post(
        {
            "segments": [100],
            "passengers": [
                {"id": "alice", "board": 0, "alight": 1},
                {"id": "alice", "board": 0, "alight": 1},
            ],
        }
    )
    assert resp.status_code == 422
    assert "duplicate passenger id" in resp.text


def test_negative_cost_is_422():
    resp = post(
        {
            "segments": [-5],
            "passengers": [{"id": "alice", "board": 0, "alight": 1}],
        }
    )
    assert resp.status_code == 422


def test_empty_segments_is_422():
    resp = post({"segments": [], "passengers": []})
    assert resp.status_code == 422


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
