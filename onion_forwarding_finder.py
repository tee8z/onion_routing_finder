#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import argparse
from typing import List, Dict, Any, Optional

def load_env_file(file_path='.env'):
    """Load environment variables from a .env file."""
    if not os.path.exists(file_path):
        return
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                if value and (value[0] == value[-1] == '"' or value[0] == value[-1] == "'"):
                    value = value[1:-1]
                    
                if key not in os.environ:
                    os.environ[key] = value

load_env_file()

MACAROON_PATH = os.getenv('LND_MACAROON_PATH', os.path.expanduser('~/.lnd/data/chain/bitcoin/mainnet/admin.macaroon'))
TLS_PATH = os.getenv('LND_TLS_PATH', os.path.expanduser('~/.lnd/tls.cert'))
RPC_SERVER = os.getenv('LND_RPC_SERVER', 'localhost:10009')

# Feature bits for onion message support (38/39)
FEATURE_BIT_ONION_MESSAGES_OPTIONAL = 39  # Odd bit (optional support)
FEATURE_BIT_ONION_MESSAGES_REQUIRED = 38  # Even bit (required support)

# Debug mode from environment or arguments
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't', 'yes')

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Find nodes supporting BOLT12 via onion message routing')
    
    # Load default values from environment variables
    default_public_ip_only = os.getenv('PUBLIC_IP_ONLY', 'False').lower() in ('true', '1', 't', 'yes')
    default_debug = DEBUG  # Use the value from environment
    default_limit = int(os.getenv('LIMIT', '20'))
    default_sort_by = os.getenv('SORT_BY', 'channels')
    default_onion_only = os.getenv('ONION_ONLY', 'False').lower() in ('true', '1', 't', 'yes')
    default_output = os.getenv('OUTPUT_FILE', 'bolt12_capable_nodes.json')
    
    parser.add_argument('--public-ip-only', action='store_true', default=default_public_ip_only,
                        help=f'Filter for nodes with public IPs only (default: {default_public_ip_only})')
    parser.add_argument('--debug', action='store_true', default=default_debug,
                        help=f'Enable debug output (default: {default_debug})')
    parser.add_argument('--limit', type=int, default=default_limit,
                        help=f'Limit the number of results displayed (default: {default_limit})')
    parser.add_argument('--sort-by', choices=['channels', 'update'], default=default_sort_by,
                        help=f'Sort results by number of channels or last update time (default: {default_sort_by})')
    parser.add_argument('--onion-only', action='store_true', default=default_onion_only,
                        help=f'Include onion addresses (default: {default_onion_only})')
    parser.add_argument('--output', type=str, default=default_output,
                        help=f'Output file for node results (default: {default_output})')
    
    return parser.parse_args()

def run_lncli_command(command: List[str]) -> Dict[str, Any]:
    """Run an lncli command and return the JSON response."""
    base_command = [
        "lncli",
        f"--macaroonpath={MACAROON_PATH}",
        f"--rpcserver={RPC_SERVER}",
        f"--tlscertpath={TLS_PATH}",
    ]

    full_command = base_command + command

    try:
        result = subprocess.run(
            full_command,
            check=True,
            capture_output=True,
            text=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error decoding JSON response")
        sys.exit(1)

def check_feature_bit_set(features_hex: str, bit_position: int) -> bool:
    """Check if a specific feature bit is set in the hex-encoded feature string."""
    if not features_hex:
        return False

    # Convert hex to binary
    try:
        # Strip '0x' prefix if present
        if features_hex.startswith('0x'):
            features_hex = features_hex[2:]

        # Convert to binary representation
        features_binary = bin(int(features_hex, 16))[2:]  # [2:] to remove '0b' prefix

        # Pad the binary representation to ensure it's long enough for our bit position
        padded_binary = features_binary.zfill(bit_position + 1)

        # Check if the bit position is within the binary representation
        # Remember: features are counted from the right (LSB)
        # The bit at position N is the Nth bit from the right (LSB)
        return padded_binary[-bit_position-1] == '1'
    except (ValueError, TypeError) as e:
        if DEBUG:
            print(f"Error parsing feature bits: {e}, format: {features_hex}")
        return False

def has_onion_message_support(node_info: Dict[str, Any]) -> bool:
    """Check if a node supports onion messages by inspecting its feature bits."""
    features = parse_lnd_features(node_info)

    return features["onion_messages_optional"] or features["onion_messages_required"]

def get_lnd_feature_format_example() -> None:
    """Print an example of the feature format from LND to help with debugging."""
    if not DEBUG:
        return

    try:
        graph_info = run_lncli_command(["describegraph"])
        if "nodes" in graph_info and len(graph_info["nodes"]) > 0:
            sample_node = graph_info["nodes"][0]
            print("\n=== Sample Node Feature Format ===")
            print(f"Node: {sample_node.get('alias', 'Unknown')} ({sample_node['pub_key']})")

            if "features" in sample_node:
                print("Features format in graph response:")
                print(json.dumps(sample_node["features"], indent=2))

            node_details = get_node_details(sample_node["pub_key"])
            if node_details and "features" in node_details:
                print("\nFeatures format in node details:")
                print(json.dumps(node_details["features"], indent=2))

            print("===================================")
    except Exception as e:
        print(f"Error getting feature format example: {e}")

def filter_for_public_ip_nodes(nodes: List[Dict[str, Any]], include_onion: bool = False) -> List[Dict[str, Any]]:
    """Filter nodes to include only those with public IP addresses."""
    public_ip_nodes = []

    for node in nodes:
        # Check if node has addresses
        if "addresses" in node:
            has_public_ip = False
            public_addr = ""

            for addr in node["addresses"]:
                # Skip .onion addresses if not explicitly included
                if ".onion" in addr["addr"] and not include_onion:
                    continue

                # If we include onion and find one, use it
                if ".onion" in addr["addr"] and include_onion:
                    has_public_ip = True
                    public_addr = addr["addr"]
                    break

                # Skip local addresses (192.168.*, 10.*, 172.16-31.*, 127.*)
                ip = addr["addr"].split(":")[0]
                if ip.startswith(("192.168.", "10.", "127.")):
                    continue
                if ip.startswith("172."):
                    second_octet = int(ip.split(".")[1])
                    if 16 <= second_octet <= 31:
                        continue

                # This is a public IP
                has_public_ip = True
                public_addr = addr["addr"]
                break

            if has_public_ip:
                node_copy = node.copy()
                node_copy["public_address"] = public_addr
                public_ip_nodes.append(node_copy)

    return public_ip_nodes

def get_node_details(pub_key: str) -> Optional[Dict[str, Any]]:
    """Get detailed information about a node."""
    try:
        node_info = run_lncli_command(["getnodeinfo", pub_key])

        # Debugging output for feature bits
        if DEBUG:
            examine_features(node_info)

        return node_info
    except Exception as e:
        if DEBUG:
            print(f"Error getting node details for {pub_key}: {e}")
        return None

def parse_lnd_features(node_info: Dict[str, Any]) -> Dict[str, bool]:
    """Parse LND feature bits into a more usable format."""
    result = {
        "onion_messages_optional": False,
        "onion_messages_required": False
    }

    # LND represents features as a dictionary where keys are bit positions
    # The format is typically: {"bit_position": {"name": "feature_name", "is_required": bool, ...}}
    for field in ['features', 'node_features']:
        if field not in node_info:
            continue

        features = node_info[field]

        # Format 1: Dictionary of bit_position -> feature_info
        if isinstance(features, dict):
            # Convert string keys to integers for comparison
            for bit_str, feature_info in features.items():
                try:
                    bit_position = int(bit_str)

                    # Check for onion message bits
                    if bit_position == FEATURE_BIT_ONION_MESSAGES_OPTIONAL:
                        result["onion_messages_optional"] = True
                    elif bit_position == FEATURE_BIT_ONION_MESSAGES_REQUIRED:
                        result["onion_messages_required"] = True

                    # Debug output
                    if DEBUG and (bit_position == 38 or bit_position == 39):
                        print(f"Found feature bit {bit_position}: {feature_info}")

                except (ValueError, TypeError):
                    # Skip keys that aren't integers
                    continue

        # Format 2: Hex string (less common but possible)
        elif isinstance(features, str):
            result["onion_messages_optional"] = check_feature_bit_set(features, FEATURE_BIT_ONION_MESSAGES_OPTIONAL)
            result["onion_messages_required"] = check_feature_bit_set(features, FEATURE_BIT_ONION_MESSAGES_REQUIRED)

    return result

def find_bolt12_capable_nodes(public_ip_only: bool = False, include_onion: bool = False) -> List[Dict[str, Any]]:
    """Find nodes that support onion message routing for BOLT12, optionally filtering for public IP."""
    # Get the entire network graph
    print("Fetching network graph, this might take a while...")
    graph_info = run_lncli_command(["describegraph"])

    # First, print a sample of the feature format if in debug mode
    if DEBUG:
        get_lnd_feature_format_example()

    all_nodes = graph_info["nodes"]
    total_nodes = len(all_nodes)

    nodes_to_check = filter_for_public_ip_nodes(all_nodes, include_onion) if public_ip_only else all_nodes

    if public_ip_only:
        print(f"\nChecking {len(nodes_to_check)}/{total_nodes} nodes with public/onion addresses for onion message support...")
    else:
        print(f"\nChecking all {total_nodes} nodes in the graph for onion message support...")

    bolt12_capable_nodes = []

    for i, node in enumerate(nodes_to_check):
        if i % 50 == 0 and i > 0:
            print(f"Checked {i}/{len(nodes_to_check)} nodes... Found {len(bolt12_capable_nodes)} with BOLT12 support")

        # Check if node has feature bits for onion messages in the graph data
        has_onion_support_in_graph = False

        # First try to check the graph data before making an API call
        if "features" in node or "node_features" in node:
            features = parse_lnd_features(node)
            has_onion_support_in_graph = features["onion_messages_optional"] or features["onion_messages_required"]

        # If we can't determine from graph data, get detailed info
        if not has_onion_support_in_graph:
            # Get detailed node information to check feature bits
            node_details = get_node_details(node["pub_key"])
            if not node_details:
                continue

            # Check if the detailed node info shows onion message support
            supports_onion_messages = has_onion_message_support(node_details)
        else:
            supports_onion_messages = True

        if supports_onion_messages:
            # Create a copy of the node to avoid modifying the original
            node_copy = node.copy()

            node_copy["has_onion_message_support"] = True

            # Add channel count
            node_info = get_node_details(node["pub_key"])
            if node_info:
                node_copy["num_channels"] = node_info.get("num_channels", 0)
                # Add a default public address if not already present
                if "public_address" not in node_copy and "addresses" in node and len(node["addresses"]) > 0:
                    node_copy["public_address"] = node["addresses"][0]["addr"]
            else:
                node_copy["num_channels"] = 0
                if "public_address" not in node_copy:
                    node_copy["public_address"] = "Unknown"

            bolt12_capable_nodes.append(node_copy)

    return bolt12_capable_nodes

def examine_features(node_info):
    """Debug function to examine feature bits format"""
    print("\n--- Feature Bit Debug Info ---")
    for field in ['features', 'node_features']:
        if field in node_info:
            print(f"{field}: {node_info[field]}")
            if isinstance(node_info[field], str):
                try:
                    features_hex = node_info[field]
                    if features_hex.startswith('0x'):
                        features_hex = features_hex[2:]
                    features_binary = bin(int(features_hex, 16))[2:]
                    print(f"  Binary: {features_binary}")
                    print(f"  Bit 38 set: {check_feature_bit_set(node_info[field], 38)}")
                    print(f"  Bit 39 set: {check_feature_bit_set(node_info[field], 39)}")
                except Exception as e:
                    print(f"  Error parsing: {e}")
    print("----------------------------")

def main():
    args = parse_arguments()

    # Set debug mode - command line args override env variable
    global DEBUG
    DEBUG = args.debug

    print("=== BOLT12 Onion Message Routing Node Finder ===")

    try:
        # Find nodes with onion message routing support for BOLT12
        bolt12_nodes = find_bolt12_capable_nodes(
            public_ip_only=args.public_ip_only,
            include_onion=args.onion_only
        )

        if not bolt12_nodes:
            print("No nodes found that support onion message routing for BOLT12.")
            return

        print(f"\nFound {len(bolt12_nodes)} nodes with onion message routing support for BOLT12")

        # Sort by either number of channels or last update time
        if args.sort_by == 'channels':
            bolt12_nodes.sort(key=lambda x: x.get("num_channels", 0), reverse=True)
            sort_description = "channels (descending)"
        else:  # sort by update time
            bolt12_nodes.sort(key=lambda x: x.get("last_update", 0), reverse=True)
            sort_description = "last update time (newest first)"

        # Display the top nodes
        print(f"\n=== Top BOLT12 Capable Nodes (sorted by {sort_description}) ===")
        print(f"{'Alias':<25} {'PubKey':<20} {'Channels':<10} {'Public/Onion Address':<30}")
        print("-" * 85)

        display_limit = min(args.limit, len(bolt12_nodes))
        for node in bolt12_nodes[:display_limit]:
            alias = node.get("alias", "Unknown")
            alias = alias[:23] + ".." if len(alias) > 23 else alias.ljust(23)
            pubkey = node["pub_key"][:17] + "..."
            channels = node.get("num_channels", "Unknown")
            address = node.get("public_address", "Unknown")

            print(f"{alias:<25} {pubkey:<20} {channels:<10} {address[:30]}")

        with open(args.output, "w") as f:
            json.dump(bolt12_nodes, f, indent=2)

        print(f"\nSaved detailed results to {args.output}")

        # Provide connection command examples
        print("\n=== Example Connection Commands ===")
        if bolt12_nodes:
            example_node = bolt12_nodes[0]
            address = example_node.get("public_address", "Unknown")
            if address != "Unknown":
                print(f"To connect to the top node using lncli:")
                print(f"lncli connect {example_node['pub_key']}@{address}")

                print("\nFor other implementations:")
                print(f"Core Lightning: lightning-cli connect {example_node['pub_key']}@{address}")
                print(f"Eclair: eclair-cli connect --uri={example_node['pub_key']}@{address}")
            else:
                print("No address available for the top node to provide connection examples.")

    except Exception as e:
        print(f"An error occurred: {e}")
        if DEBUG:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()