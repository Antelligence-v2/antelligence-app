"""W1 review hardening: "verified on-chain" must mean *these* values were proven, and the
backend must never sign against a chain other than the selected testnet.

Background (review of fork PR #18): TumorIntel keys records by configHash, and
submitSimulation() is permissionless and overwrote a verified record's values without
clearing `verified`. Reading isVerified(configHash) therefore vouched for whatever values a
later submission wrote. The binding that cannot be forged is the record's publicValuesHash,
set only by verifySimulation() to keccak256(abi.encode(proven values)).
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from chain import config  # noqa: E402
from chain.leaderboard import SIMULATION_SUBMITTED_TOPIC, build_leaderboard, fetch_onchain_simulations, \
    onchain_artifacts  # noqa: E402
from chain.onchain_record import proves, public_values_hash, public_values_hash_from_encoded  # noqa: E402
from chain.proof_adapter import create_proof_bundle  # noqa: E402
from chain.proof_spec import build_public_values_payload, encode_public_values_payload  # noqa: E402
from chain.submit import preflight_signing_target, submit_bundle_onchain, _web3_send_submit  # noqa: E402

CFG = "ab" * 32
CONTRACT = "0x" + "12" * 20
HONEST = (3000, 5, 66, 30)
FORGED = (9999, 5, 66, 30)


# ----------------------------------------------------------------------------- fakes


def _word(n: int) -> str:
    return f"{n:064x}"


def _log(values, submitter="cd" * 20, tx="11"):
    return {"topics": [SIMULATION_SUBMITTED_TOPIC, "0x" + CFG, "0x" + "00" * 12 + submitter],
            "data": "0x" + "".join(_word(v) for v in values), "transactionHash": "0x" + tx * 32,
            "blockNumber": 7}


class _Call:
    def __init__(self, value):
        self._value = value

    def call(self):
        return self._value


class _Functions:
    def __init__(self, records):
        self._records = records

    def simulations(self, cfg_bytes):
        rec = self._records.get(cfg_bytes.hex())
        if rec is None:
            return _Call((b"\x00" * 32, 0, 0, 0, 0, "0x" + "00" * 20, 0, 0, False, False, b"\x00" * 32))
        values, verified, pv_hash = rec
        return _Call((bytes.fromhex(CFG), *values, "0x" + "cd" * 20, 1, 2 if verified else 0, True, verified,
                      bytes.fromhex(pv_hash[2:])))


class _Eth:
    def __init__(self, logs=(), records=None, chain_id=300, code=b"\x01"):
        self._logs, self._records, self.chain_id, self._code = list(logs), records or {}, chain_id, code
        self.sent = []

    def get_logs(self, _filter):
        return self._logs

    def contract(self, address=None, abi=None):
        return type("C", (), {"functions": _Functions(self._records)})()

    def get_code(self, _address):
        return self._code


class _W3:
    def __init__(self, **kw):
        self.eth = _Eth(**kw)


def _proven(values):
    return {CFG: (values, True, public_values_hash(CFG, *values))}


# ----------------------------------------------------------------------------- the hash


def test_public_values_hash_is_keccak_of_the_canonical_encoding():
    payload = build_public_values_payload(CFG, *HONEST)
    assert public_values_hash(CFG, *HONEST) == public_values_hash_from_encoded(
        encode_public_values_payload(payload))
    assert public_values_hash(CFG, *HONEST) != public_values_hash(CFG, *FORGED)


def test_proves_requires_verified_flag_and_exact_hash():
    good = public_values_hash(CFG, *HONEST)
    assert proves({"verified": True, "public_values_hash": good}, good)
    assert not proves({"verified": False, "public_values_hash": good}, good)
    assert not proves({"verified": True, "public_values_hash": public_values_hash(CFG, *FORGED)}, good)
    assert not proves({"verified": True, "public_values_hash": "0x" + "00" * 32}, "0x" + "00" * 32)
    assert not proves(None, good)
    assert not proves({"verified": True, "public_values_hash": good}, None)


# ----------------------------------------------------------------------------- leaderboard


def test_overwritten_verified_record_does_not_promote_the_forged_submission():
    """The exact state reproduced on anvil-zksync against the PR's contract."""
    w3 = _W3(logs=[_log(HONEST, tx="11"), _log(FORGED, submitter="ef" * 20, tx="22")],
             records={CFG: (FORGED, True, public_values_hash(CFG, *HONEST))})  # values overwritten, hash intact
    events = fetch_onchain_simulations("http://rpc.test", contract=CONTRACT, from_block=0, w3=w3)
    by_rate = {e["kill_rate_bps"]: e for e in events}
    assert by_rate[3000]["verified"] is True
    assert by_rate[9999]["verified"] is False
    assert by_rate[9999]["contract_verified_flag"] is True  # what the PR used to trust
    board = build_leaderboard(onchain_artifacts(events))["leaderboard"]
    forged_row = next(r for r in board if r["kill_rate"] == 99.99)
    assert forged_row["verified_onchain"] is False and forged_row["trust_tier"] != "verified_onchain"


def test_unverified_record_promotes_nothing():
    w3 = _W3(logs=[_log(HONEST)], records={CFG: (HONEST, False, "0x" + "00" * 32)})
    (event,) = fetch_onchain_simulations("http://rpc.test", contract=CONTRACT, from_block=0, w3=w3)
    assert event["verified"] is False and event["contract_verified_flag"] is False


def test_proven_submission_is_verified():
    w3 = _W3(logs=[_log(HONEST)], records=_proven(HONEST))
    (event,) = fetch_onchain_simulations("http://rpc.test", contract=CONTRACT, from_block=0, w3=w3)
    assert event["verified"] is True


# ----------------------------------------------------------------------------- RPC + signing guards


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for name in ("ANTELLIGENCE_CHAIN", "ANTELLIGENCE_RPC_URL", "CHAIN_RPC", "ZKSYNC_SEPOLIA_RPC_URL",
                 "BASE_SEPOLIA_RPC_URL", "ANTELLIGENCE_TUMOR_INTEL_ADDR", "TUMOR_INTEL_ADDR", "FOOD_ADDR",
                 "ANTELLIGENCE_FOOD_ADDR"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "zksync-era-sepolia.json").write_text(json.dumps({
        "network": "zksync-era-sepolia", "chain_id": 300,
        "contracts": [{"name": "TumorIntel", "address": CONTRACT}, {"name": "FoodToken", "address": "0x" + "34" * 20}]}))
    monkeypatch.setenv("ANTELLIGENCE_DEPLOYMENTS_DIR", str(tmp_path))
    return tmp_path


def test_legacy_local_hardhat_chain_rpc_does_not_hijack_zksync(clean_env, monkeypatch):
    monkeypatch.setenv("CHAIN_RPC", "http://127.0.0.1:8545")  # env.example / docker-compose-ecr default
    monkeypatch.setenv("ANTELLIGENCE_CHAIN", "zksync-era-sepolia")
    assert config.get_rpc_url() == "https://sepolia.era.zksync.dev"


def test_network_specific_rpc_beats_legacy_chain_rpc(clean_env, monkeypatch):
    monkeypatch.setenv("CHAIN_RPC", "https://some-other-rpc.example")
    monkeypatch.setenv("ZKSYNC_SEPOLIA_RPC_URL", "https://zk.example")
    assert config.get_rpc_url() == "https://zk.example"
    monkeypatch.setenv("ANTELLIGENCE_RPC_URL", "https://explicit.example")
    assert config.get_rpc_url() == "https://explicit.example"


def test_non_default_legacy_chain_rpc_is_still_honoured(clean_env, monkeypatch):
    monkeypatch.setenv("CHAIN_RPC", "http://10.0.0.5:8011")
    assert config.get_rpc_url() == "http://10.0.0.5:8011"


def test_rpc_on_a_different_chain_is_refused(clean_env):
    assert config.assert_rpc_matches_network(_W3(chain_id=300)) == 300
    for wrong in (1, 324, 8453, 84532, 31337):  # mainnet, Era mainnet, Base mainnet, Base Sepolia, hardhat
        with pytest.raises(config.ChainConfigError, match="refusing"):
            config.assert_rpc_matches_network(_W3(chain_id=wrong))


def test_signing_is_refused_before_any_key_use_on_the_wrong_chain(clean_env):
    w3 = _W3(chain_id=1)
    with pytest.raises(config.ChainConfigError):
        _web3_send_submit(rpc_url="http://rpc.test", private_key="0x" + "11" * 32, contract=CONTRACT,
                          args=["0x" + CFG, "3000", "5", "66", "30"], w3=w3)


def test_signing_is_refused_when_the_contract_has_no_code(clean_env):
    with pytest.raises(config.ChainConfigError, match="no contract code"):
        preflight_signing_target(_W3(chain_id=300, code=b""), CONTRACT)
    assert preflight_signing_target(_W3(chain_id=300), CONTRACT) == 300


def test_submit_bundle_path_still_uses_injected_sender(clean_env):
    bundle = create_proof_bundle({"nanobot_count": 5, "tumor_radius": 66, "steps": 30}, {"kill_rate": 30.0},
                                 run_id="w1")
    sent = []

    def sender(**kw):
        sent.append(kw)
        return {"status": "0x1", "transactionHash": "0x" + "22" * 32, "blockNumber": 9, "from": "0x" + "cd" * 20}

    out = submit_bundle_onchain(bundle, rpc_url="http://rpc.test", private_key="0x" + "11" * 32, sender=sender)
    assert sent and out["onchain"]["chain_id"] == 300


# ----------------------------------------------------------------------------- legacy address overrides


def test_stale_legacy_address_env_is_ignored_on_zksync(clean_env, monkeypatch):
    monkeypatch.setenv("TUMOR_INTEL_ADDR", "0x925b455175eF932a9a0239090a94E593224CD8AB")  # old Base Sepolia
    assert config.get_tumor_intel_address() == CONTRACT


def test_prefixed_override_still_wins_everywhere(clean_env, monkeypatch):
    monkeypatch.setenv("ANTELLIGENCE_TUMOR_INTEL_ADDR", "0x" + "99" * 20)
    assert config.get_tumor_intel_address() == "0x" + "99" * 20


def test_legacy_address_env_still_works_on_base_sepolia(clean_env, monkeypatch):
    monkeypatch.setenv("ANTELLIGENCE_CHAIN", "base-sepolia")
    monkeypatch.setenv("TUMOR_INTEL_ADDR", "0x925b455175eF932a9a0239090a94E593224CD8AB")
    assert config.get_tumor_intel_address() == "0x925b455175eF932a9a0239090a94E593224CD8AB"
