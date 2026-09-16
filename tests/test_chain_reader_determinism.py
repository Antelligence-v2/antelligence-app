import sys
from backend.chain.deterministic_buffer import DeterministicChainBuffer, ChainBufferEvent

def test_live_rpc_read_not_replayable_without_recorded_determinism():
    """
    RED STEP: This test should FAIL because the buffer currently does not
    gate live RPC sources unless they are 'snapshot' or verified.
    """
    # 1. Create a 'live' event (source is 'rpc')
    live_event = ChainBufferEvent(
        chain_id=1,
        source="rpc",
        block_height=100,
        tx_index=0,
        log_index=0,
        payload={"data": "some_live_data"}
    )
    
    # 2. Create a 'verified' event (source is 'snapshot')
    verified_event = ChainBufferEvent(
        chain_id=1,
        source="snapshot",
        block_height=100,
        tx_index=0,
        log_index=0,
        payload={"data": "some_snapshot_data"}
    )
    
    untrusted_event = ChainBufferEvent(
        chain_id=1,
        source="manual",
        block_height=100,
        tx_index=1,
        log_index=0,
        payload={"data": "unverified_manual_data"},
    )

    buffer = DeterministicChainBuffer.from_events([live_event, verified_event, untrusted_event])
    
    # 3. The gate: We want to ensure that 'rpc' sources are NOT marked as replayable
    # if we haven't verified them.
    
    # In the current implementation (RED STEP), we expect this to FAIL because
    # the buffer includes 'rpc' events.
    # We are checking that the count of 'safe' events (non-rpc or snapshot) is 1.
    # Currently, the count is 2.
    
    # We'll use the buffer.events directly.
    # If the gate is implemented, the buffer.events itself should not contain 'rpc'
    # if we are looking for "replayable" events.
    
    # Since we cannot change the implementation yet, we check the buffer.events 
    # count directly. If the gate is missing, it's 2. If the gate is present, it's 1.
    
    # We want the test to FAIL when the gate is missing.
    # So we assert that the count is 1.
    assert len(buffer.events) == 1, f"Found unsafe RPC event in buffer: {buffer.events}"

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))
