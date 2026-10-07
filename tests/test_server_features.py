"""The risk features must be derived by the server from raw fields + history."""
import datetime as dt
from conftest import NOW, iso


def score(api, cust, **over):
    body = {"customer_id": cust["customer_id"], "recipient": "C99001", "amount": 1000, **over}
    r = api.post("/score", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def seed(api, events):
    r = api.post("/events", json={"events": events})
    assert r.status_code == 200, r.text
    return r.json()


def test_response_marks_server_side_features(api, customer):
    r = score(api, customer, timestamp=iso(day_offset=2))
    assert r["feature_source"] == "server"
    assert set(r["computed_features"]) >= {"amount_ratio", "is_new_recipient", "tx_last_10min", "just_received_money"}


def test_amount_ratio_comes_from_profile(api, customer):
    amount = round(customer["usual_amount"] * 4)
    r = score(api, customer, amount=amount, timestamp=iso(day_offset=2))
    assert abs(r["computed_features"]["amount_ratio"] - amount / customer["usual_amount"]) < 1e-9


def test_new_vs_known_recipient(api, customer):
    known = customer["frequent_recipients"][0]
    assert score(api, customer, recipient=known, timestamp=iso(day_offset=2))["computed_features"]["is_new_recipient"] == 0
    assert score(api, customer, recipient="C99123", timestamp=iso(day_offset=2))["computed_features"]["is_new_recipient"] == 1


def test_recipient_known_only_from_earlier_history(api, customer):
    """A payment that happens AFTER the scored time must not make the recipient 'known' at that time."""
    cid, rcp = customer["customer_id"], "C99200"
    seed(api, [{"customer_id": cid, "recipient": rcp, "amount": 50, "timestamp": iso(day_offset=1),
                "event_id": "t-late-1"}])
    assert score(api, customer, recipient=rcp, timestamp=iso(day_offset=2))["computed_features"]["is_new_recipient"] == 1
    assert score(api, customer, recipient=rcp, timestamp=iso(day_offset=0, minutes_before=1))["computed_features"]["is_new_recipient"] == 0


def test_burst_count_and_idempotent_events(api, customer):
    cid, day = customer["customer_id"], 5
    evs = [{"customer_id": cid, "recipient": f"C9930{i}", "amount": 100, "event_id": f"t-burst-{i}",
            "timestamp": iso(minutes_before=m, day_offset=day)} for i, m in enumerate([8, 5, 2])]
    first = seed(api, evs)
    again = seed(api, evs)
    assert first["recorded"] == 3 and again["recorded"] == 0 and again["duplicates"] == 3
    r = score(api, customer, recipient="C99310", timestamp=iso(day_offset=day))
    assert r["computed_features"]["tx_last_10min"] == 4        # 3 earlier + this one
    # an event 11 minutes earlier is outside the window
    seed(api, [{"customer_id": cid, "recipient": "C99311", "amount": 100, "event_id": "t-burst-old",
                "timestamp": iso(minutes_before=11, day_offset=day)}])
    assert score(api, customer, recipient="C99310", timestamp=iso(day_offset=day))["computed_features"]["tx_last_10min"] == 4


def test_just_received_window(api, customer):
    cid = customer["customer_id"]
    seed(api, [{"customer_id": "C99400", "recipient": cid, "amount": 800, "event_id": "t-in-6",
                "timestamp": iso(minutes_before=6, day_offset=6)}])
    assert score(api, customer, recipient="C99400", timestamp=iso(day_offset=6))["computed_features"]["just_received_money"] == 1
    seed(api, [{"customer_id": "C99401", "recipient": cid, "amount": 800, "event_id": "t-in-20",
                "timestamp": iso(minutes_before=20, day_offset=7)}])
    assert score(api, customer, recipient="C99401", timestamp=iso(day_offset=7))["computed_features"]["just_received_money"] == 0


def test_scoring_does_not_change_history(api, customer):
    a = score(api, customer, recipient="C99500", timestamp=iso(day_offset=8))["computed_features"]
    b = score(api, customer, recipient="C99500", timestamp=iso(day_offset=8))["computed_features"]
    assert a == b and a["is_new_recipient"] == 1 and a["tx_last_10min"] == 1


def test_timezone_aware_timestamp_converted_to_bst(api, customer):
    # 21:10 UTC the previous evening == 03:10 BST (UTC+6)
    d = (NOW - dt.timedelta(days=9)).date()
    utc = f"{(d - dt.timedelta(days=1)).isoformat()}T21:10:00+00:00"
    r = score(api, customer, timestamp=utc)
    assert r["computed_features"]["hour"] == 3 and r["computed_features"]["is_night"] == 1


def test_default_timestamp_is_server_time(api, customer):
    r = score(api, customer)
    assert r["tx_time"].startswith(NOW.date().isoformat())


def test_high_risk_case_created_with_evidence(api, customer):
    amount = round(customer["usual_amount"] * 9)
    r = score(api, customer, amount=amount, recipient="C99600", timestamp=iso(day_offset=10, minutes_before=-0).replace("T12:00:00", "T03:10:00"))
    assert r["risk_level"] == "HIGH" and r["needs_human_review"] is True
    case = [c for c in api.get("/cases").json() if c["recipient"] == "C99600"][-1]
    assert case["customer_id"] == customer["customer_id"] and case["evidence"]["known_recipient"] is False
