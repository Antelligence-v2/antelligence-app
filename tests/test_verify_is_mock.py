
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chain.verify import verify_artifact
from chain.ipfs import compute_artifact_hash

def test_verify_artifact_contains_is_mock_key():
    config = {"tumor_radius": 100}
    metrics = {"kill_rate": 10.0, "deliveries": 5}
    c_hash = compute_artifact_hash(config)
    m_hash = compute_artifact_hash(metrics)
    
    # We create an artifact that is 'broken' (invalid artifact_hash) 
    # so it doesn't trigger complex logic, but we check the returned dict.
    artifact = {
        "version": "v2",
        "type": "antelligence-simulation-v2",
        "config": config,
        "metrics": metrics,
        "config_hash": c_hash,
        "metrics_hash": m_hash,
        "artifact_hash": "0"*64, 
        "is_mock": True
    }
    
    result = verify_artifact(artifact, replay=False)
    assert "is_mock" in result
    assert result["is_mock"] is True

def test_verify_artifact_is_mock_false_by_default():
    config = {"tumor_radius": 100}
    metrics = {"kill_rate": 10.0, "deliveries": 5}
    c_hash = compute_artifact_hash(config)
    m_hash = compute_artifact_hash(metrics)
    
    artifact = {
        "version": "v2",
        "type": "antelligence-simulation-v2",
        "config": config,
        "metrics": metrics,
        "config_hash": c_hash,
        "metrics_hash": m_hash,
        "artifact_hash": "0"*64,
    }
    
    result = verify_artifact(artifact, replay=False)
    assert "is_mock" in result
    assert result["is_mock"] is False
