import os
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account
import json

# Load environment variables from .env file
load_dotenv()

# Helper function to load contract ABI
def load_contract_abi(contract_name):
    """Load ABI from compiled Hardhat artifacts"""
    try:
        artifact_path = os.path.join(
            os.path.dirname(__file__),
            'artifacts', 'contracts', f'{contract_name}.sol', f'{contract_name}.json'
        )
        with open(artifact_path, 'r') as f:
            artifact = json.load(f)
            return artifact['abi']
    except Exception as e:
        print(f"Warning: Could not load ABI for {contract_name}: {e}")
        return None

# Get RPC URL and Private Key from environment variables
# Prioritize local chain RPC if available, otherwise fall back to Base Sepolia
_CHAIN_RPC = os.getenv("CHAIN_RPC")
_BASE_SEPOLIA_RPC_URL = os.getenv("BASE_SEPOLIA_RPC_URL")

# Choose which RPC URL to use
RPC_URL = None
if _CHAIN_RPC and _CHAIN_RPC != "http://127.0.0.1:8545": # Check if local RPC is set and not just default placeholder
    RPC_URL = _CHAIN_RPC
    print(f"Using local RPC: {RPC_URL}")
elif _BASE_SEPOLIA_RPC_URL:
    RPC_URL = _BASE_SEPOLIA_RPC_URL
    print(f"Using Base Sepolia RPC: {RPC_URL}")
else:
    raise ValueError("Neither CHAIN_RPC nor BASE_SEPOLIA_RPC_URL is set in .env. Please configure at least one.")


_PRIV_KEY = os.getenv("PRIVATE_KEY")

# Check if private key is loaded and not empty
if not _PRIV_KEY:
    raise ValueError("PRIVATE_KEY environment variable not set or is empty. Please set it in your .env file with a valid testnet private key.")

# Initialize Web3 provider
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Check connection
if not w3.is_connected():
    raise ConnectionError(f"Failed to connect to Ethereum node at {RPC_URL}. Please check your RPC URL and network connection.")
else:
    print(f"Successfully connected to Ethereum node at {RPC_URL}")
    print(f"Current Chain ID: {w3.eth.chain_id}")

# Load account from private key
try:
    acct = Account.from_key(_PRIV_KEY)
    print(f"Account loaded: {acct.address}")
    # Verify that the account has some balance (optional but good for debugging)
    balance_wei = w3.eth.get_balance(acct.address)
    balance_eth = w3.from_wei(balance_wei, 'ether')
    print(f"Account balance: {balance_eth:.4f} ETH")
    if balance_eth == 0:
        print("WARNING: Account has 0 ETH. Transactions will likely fail. Please fund it via a faucet.")
except Exception as e:
    raise ValueError(f"Failed to load account from private key: {e}. Ensure PRIVATE_KEY is a valid hex string (e.g., '0x...' or without '0x' prefix if it's just the hex string).")

# Load contract addresses from environment variables
FOOD_CONTRACT_ADDRESS = os.getenv("FOOD_ADDR")
MEMORY_CONTRACT_ADDRESS = os.getenv("MEMORY_ADDR")
TUMOR_INTEL_CONTRACT_ADDRESS = os.getenv("TUMOR_INTEL_ADDR")

if not FOOD_CONTRACT_ADDRESS:
    print("WARNING: FOOD_ADDR not set in .env. Food contract interactions may fail.")
if not MEMORY_CONTRACT_ADDRESS:
    print("WARNING: MEMORY_ADDR not set in .env. Memory contract interactions may fail.")
if not TUMOR_INTEL_CONTRACT_ADDRESS:
    print("WARNING: TUMOR_INTEL_ADDR not set in .env. TumorIntel contract interactions may fail.")

# Load contract ABIs
MEMORY_ABI = load_contract_abi('ColonyMemory')
FOOD_ABI = load_contract_abi('FoodToken')
TUMOR_INTEL_ABI = load_contract_abi('TumorIntel')

# Create contract instances if addresses are available
memory_contract = None
food_contract = None
tumor_intel_contract = None

if MEMORY_CONTRACT_ADDRESS and MEMORY_ABI and w3.is_connected():
    try:
        memory_contract = w3.eth.contract(
            address=Web3.to_checksum_address(MEMORY_CONTRACT_ADDRESS),
            abi=MEMORY_ABI
        )
        print(f"✅ ColonyMemory contract loaded at {MEMORY_CONTRACT_ADDRESS}")
    except Exception as e:
        print(f"⚠️ Failed to load ColonyMemory contract: {e}")

if FOOD_CONTRACT_ADDRESS and FOOD_ABI and w3.is_connected():
    try:
        food_contract = w3.eth.contract(
            address=Web3.to_checksum_address(FOOD_CONTRACT_ADDRESS),
            abi=FOOD_ABI
        )
        print(f"✅ FoodToken contract loaded at {FOOD_CONTRACT_ADDRESS}")
    except Exception as e:
        print(f"⚠️ Failed to load FoodToken contract: {e}")

if TUMOR_INTEL_CONTRACT_ADDRESS and TUMOR_INTEL_ABI and w3.is_connected():
    try:
        tumor_intel_contract = w3.eth.contract(
            address=Web3.to_checksum_address(TUMOR_INTEL_CONTRACT_ADDRESS),
            abi=TUMOR_INTEL_ABI
        )
        print(f"✅ TumorIntel contract loaded at {TUMOR_INTEL_CONTRACT_ADDRESS}")
    except Exception as e:
        print(f"⚠️ Failed to load TumorIntel contract: {e}")

# The `w3`, `acct`, and contract objects are now ready to be imported and used
