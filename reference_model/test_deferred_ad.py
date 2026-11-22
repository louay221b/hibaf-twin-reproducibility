"""One independent regression check: AES-GCM with deferred associated data.

Run alongside the archived 35-check suite:
    python3 reference_model/test_hibaf_v2.py
    python3 reference_model/test_deferred_ad.py

The two scripts total 36 checks. No timing or ns-3 simulation is executed here.
"""
import random
import hibaf_v2_ref as h
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


def test_deferred_ad():
    rng = random.Random(20261028)
    ttp = h.TTP(rng)
    st = h.Station("ST", ttp, rng)
    be = h.BackEnd("BE", ttp, rng, theta=1.0)
    col = h.Collector("B0", ttp, rng)
    sensor = h.Sensor("S0", ttp, rng)
    m1 = sensor.enrol_start(be.id)
    m2 = be.enrol(m1)
    assert m2 is not None
    m3 = sensor.enrol_finish(m2, be.P)
    assert be.enrol_confirm(m3)
    sensor.link_key(col.id, col.Y)
    col.add_sensor(sensor)
    rl = ttp.rl_object(1)
    beacon, rho = st.beacon(1, rl)
    assert sensor.accept_beacon(beacon, st.P, ttp.P)
    col.new_window(1, rho, rl)

    message = b"DO=7.1"
    report = sensor.report(message, 1, 10)
    ident, w, ts, tau, nonce, ciphertext_tag, U, s = report[:8]
    key = h.PRF(sensor.nvm["K"], "enc", sensor.id, sensor.be_id, w, rho, tau, n=16)
    first_ad = h.H("AD", sensor.id, w, rho, tau, ts, nonce)
    first_call = AESGCM(key).encrypt(nonce, message, first_ad)
    preliminary_tag = first_call[-16:]
    wire = b"".join(x if isinstance(x, (bytes, bytearray)) else str(x).encode() for x in report)

    assert len(nonce) == 12
    assert len(ciphertext_tag) - len(message) == 16
    assert ciphertext_tag[:-16] == first_call[:-16]
    assert ciphertext_tag[-16:] != preliminary_tag
    assert preliminary_tag not in wire
    assert AESGCM(key).decrypt(nonce, ciphertext_tag,
                               h.ad_full(ident, w, rho, tau, ts, nonce, U, s)) == message
    try:
        AESGCM(key).decrypt(nonce, ciphertext_tag, first_ad)
    except InvalidTag:
        pass
    else:
        raise AssertionError("final tag accepted with preliminary associated data")

    sign = h.sign
    def injected_failure(*args, **kwargs):
        raise RuntimeError("injected failure between the two GCM calls")
    previous_counter = sensor.c
    h.sign = injected_failure
    try:
        try:
            sensor.report(b"DO=7.2", 1, 11)
        except RuntimeError:
            pass
        else:
            raise AssertionError("fault injection did not interrupt signing")
    finally:
        h.sign = sign
    failed_nonce = sensor.r.to_bytes(8, "big") + (previous_counter + 1).to_bytes(4, "big")
    next_report = sensor.report(b"DO=7.3", 1, 12)
    assert sensor.c == previous_counter + 2
    assert next_report[4] != failed_nonce


if __name__ == "__main__":
    test_deferred_ad()
    print("1/1 deferred-associated-data regression check passed")
