"""Tests for verifier admin helpers."""

from unittest.mock import patch
import pytest

from backend.chain.verifier_admin import set_verifier_address, submit_proof_verification


class TestVerifierAdmin:
    @patch("backend.chain.verifier_admin.subprocess.run")
    def test_set_verifier_address_rejects_malformed_address_before_cast(self, mock_run):
        with pytest.raises(ValueError, match="must be a 20-byte hex address"):
            set_verifier_address("0x1234")

        mock_run.assert_not_called()

    @patch("backend.chain.verifier_admin.subprocess.run")
    def test_set_verifier_address(self, mock_run):
        mock_run.return_value.stdout = '{"transactionHash":"0xabc"}'
        result = set_verifier_address("0x1111111111111111111111111111111111111111")
        assert result["ok"] is True
        assert result["verifier"] == "0x1111111111111111111111111111111111111111"

    @patch("backend.chain.verifier_admin.subprocess.run")
    def test_submit_proof_verification(self, mock_run):
        mock_run.return_value.stdout = '{"transactionHash":"0xdef"}'
        result = submit_proof_verification("0x1234", "0xabcd")
        assert result["ok"] is True
        assert result["proof_lifecycle"]["stage"] == "verified_onchain"
        assert result["verification_status"]["onchain_ok"] is True

    @patch("backend.chain.verifier_admin.get_tumor_intel_address")
    @patch("backend.chain.verifier_admin.get_private_key")
    @patch("backend.chain.verifier_admin.get_base_sepolia_rpc_url")
    @patch("backend.chain.verifier_admin.subprocess.run")
    def test_set_verifier_address_invalid_config(self, mock_run, mock_rpc, mock_pk, mock_intel):
        mock_intel.return_value = "0x1234567890123456789012345678901234567890"
        mock_pk.return_value = "0xabc"
        mock_rpc.return_value = "http://localhost:8545"
        # Ensure the mock_run returns a valid stdout string to prevent TypeError in json.loads
        mock_run.return_value.stdout = '{"transactionHash":"0xabc"}'
        
        with pytest.raises(ValueError, match="verifier_address is not configured"):
            set_verifier_address("")

