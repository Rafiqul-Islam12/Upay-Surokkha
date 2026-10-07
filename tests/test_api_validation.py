"""Input validation on the raw-field API. Every case here must be rejected BEFORE scoring."""
import pytest
from conftest import iso

BASE = dict(recipient="C99001", amount=1000)


def post(api, cust, **over):
    body = {"customer_id": cust["customer_id"], **BASE, **over}
    body = {k: v for k, v in body.items() if v is not None}
    return api.post("/score", json=body)


@pytest.mark.parametrize("field,value", [
    ("amount_ratio", 9.0), ("is_new_recipient", 0), ("tx_last_10min", 1),
    ("just_received_money", 0), ("hour", 14), ("is_night", 0)])
def test_client_cannot_send_derived_features(api, customer, field, value):
    r = post(api, customer, **{field: value})
    assert r.status_code == 422
    assert "computed by the server" in r.text


@pytest.mark.parametrize("amount", [0, -1, -0.01, 10_000_000.01, 1e30, "abc", None, [], {}])
def test_bad_amounts_rejected(api, customer, amount):
    body = {"customer_id": customer["customer_id"], "recipient": "C99001", "amount": amount}
    if amount is None:
        body.pop("amount")
    assert api.post("/score", json=body).status_code == 422


def test_nan_and_infinity_rejected(api, customer):
    for raw in ("NaN", "Infinity", "-Infinity"):
        body = f'{{"customer_id": "{customer["customer_id"]}", "recipient": "C99001", "amount": {raw}}}'
        r = api.post("/score", content=body, headers={"Content-Type": "application/json"})
        assert r.status_code == 422, raw


@pytest.mark.parametrize("bad", ["", " ", "C0001; DROP TABLE", "a/b", "a\\b", "x'y", 'x"y', "a" * 33,
                                 "ক১২৩", "C 1", "C1\n", "<script>"])
def test_bad_ids_rejected(api, customer, bad):
    assert post(api, customer, recipient=bad).status_code == 422
    assert api.post("/score", json={"customer_id": bad, "recipient": "C99001", "amount": 10}).status_code == 422


def test_self_transfer_rejected(api, customer):
    assert post(api, customer, recipient=customer["customer_id"]).status_code == 422


def test_unknown_field_rejected(api, customer):
    assert post(api, customer, foo="bar").status_code == 422


def test_bad_tx_type_rejected(api, customer):
    assert post(api, customer, tx_type="refund").status_code == 422


@pytest.mark.parametrize("missing", ["customer_id", "recipient", "amount"])
def test_missing_required_field(api, customer, missing):
    body = {"customer_id": customer["customer_id"], "recipient": "C99001", "amount": 100}
    body.pop(missing)
    assert api.post("/score", json=body).status_code == 422


def test_future_timestamp_rejected_but_small_skew_allowed(api, customer):
    assert post(api, customer, timestamp=iso(minutes_before=-60)).status_code == 422     # +1h
    assert post(api, customer, timestamp=iso(minutes_before=-3)).status_code == 200      # +3 min skew ok


def test_too_old_timestamp_rejected(api, customer):
    assert post(api, customer, timestamp=iso(day_offset=400)).status_code == 422


def test_garbage_timestamp_rejected(api, customer):
    assert post(api, customer, timestamp="yesterday-ish").status_code == 422


def test_unknown_customer_is_404_not_500(api):
    r = api.post("/score", json={"customer_id": "NOPE", "recipient": "C99001", "amount": 100})
    assert r.status_code == 404 and r.json()["detail"]["code"] == "unknown_customer"


def test_context_endpoint_validates_id(api):
    assert api.get("/customer/bad id!/context").status_code in (404, 422)
    assert api.get("/customer/NOPE/context").json() == {"found": False}


def test_event_batch_limits(api, customer):
    ev = {"customer_id": customer["customer_id"], "recipient": "C99777", "amount": 10, "timestamp": iso(day_offset=3)}
    assert api.post("/events", json={"events": []}).status_code == 422
    assert api.post("/events", json={"events": [ev] * 201}).status_code == 422
    assert api.post("/events", json={"events": [{**ev, "timestamp": None}]}).status_code == 422


def test_event_rejects_derived_features(api, customer):
    ev = {"customer_id": customer["customer_id"], "recipient": "C99778", "amount": 10,
          "timestamp": iso(day_offset=3), "tx_last_10min": 9}
    assert api.post("/events", json={"events": [ev]}).status_code == 422
