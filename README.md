# Onion Forwarding Finder

A tool to find Lightning Network nodes supporting onion message forwarding required for BOLT12 offer routing by examining feature bits [(38/39)](https://github.com/lightning/bolts/blob/011bf84d74d130c2972becca97c87f297b9d4a92/09-features.md?plain=1#L49) in the network graph.

## Overview

This script scans the Lightning Network to identify nodes that support onion message forwarding, which are required for BOLT12 Offers. It connects to your LND node to retrieve the network graph, then processes each node to check whether it has the necessary feature bits enabled.

## Features

- Finds nodes with onion message forwarding support (feature bits 38/39)
- Filters for nodes with public IPs only (optional)
- Includes Tor onion addresses (optional)
- Sorts results by number of channels or last update time
- Configurable via environment variables or command-line arguments
- Detailed progress reporting with time estimates
- Saves results to JSON for further analysis

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/onion_forwarding_finder.git
   cd onion_forwarding_finder
   ```

2. Copy the `.env.example` into `.env` file and update with your LND connection settings:
   ```bash
   LND_MACAROON_PATH=/path/to/your/admin.macaroon
   LND_TLS_PATH=/path/to/your/tls.cert
   LND_RPC_SERVER=your-lnd-node:10009
   
   # Default script settings (optional)
   DEBUG=False
   PUBLIC_IP_ONLY=False
   LIMIT=20
   SORT_BY=channels
   ONION_ONLY=False
   OUTPUT_FILE=bolt12_capable_nodes.json
   ```

## Usage

Run the script with default settings (from `.env` file):

```bash
python3 onion_forwarding_finder.py
```

### Command-line Options

All of these override the settings in your `.env` file:

```
--public-ip-only     Filter for nodes with public IPs only
--debug              Enable debug output
--limit NUMBER       Limit the number of results displayed (default: 20)
--sort-by OPTION     Sort results by 'channels' or 'update' (default: channels)
--onion-only         Include onion addresses
--output FILENAME    Output file for node results (default: bolt12_capable_nodes.json)
```

### Examples

Find all BOLT12-capable nodes (including those without public IPs):
```bash
python3 onion_forwarding_finder.py
```

Find only nodes with public IPs and show detailed debug information:
```bash
python3 onion_forwarding_finder.py --public-ip-only --debug
```

Include Tor onion addresses and limit results to top 50 nodes:
```bash
python3 onion_forwarding_finder.py --onion-only --limit 50
```

Sort results by most recently updated nodes:
```bash
python3 onion_forwarding_finder.py --sort-by update
```

## Requirements

- Python 3.6+
- Active LND node with RPC access
- Installed lncli that is accessible from where the pythons script runs

## How It Works

1. The script connects to your LND node via lncli and retrieves the entire network graph
2. It examines each node for feature bits 38 (required) and 39 (optional) for onion message forwarding support
3. For nodes that support onion message forwarding, it retrieves additional details like channel count
4. Results are sorted and displayed, with the option to save to a JSON file for further analysis

## Notes

- The script requires an LND node with proper authentication (macaroon & TLS cert)
- Scanning large networks can take several minutes
- The progress bar provides progress towards completion
- Not all nodes with onion message forwarding support will be available for connections (check for public addresses)


Example of output when used against a mutinynet lnd node
```bash
➜  onion_forwarding_finder git:(master) ✗ python3 onion_forwarding_finder.py
=== BOLT12 Onion Message Routing Node Finder ===
Fetching network graph, this might take a while...

Checking all 481 nodes in the graph for onion message support...
Checked 50/481 nodes... Found 5 with BOLT12 support
Checked 100/481 nodes... Found 11 with BOLT12 support
Checked 150/481 nodes... Found 12 with BOLT12 support
Checked 200/481 nodes... Found 15 with BOLT12 support
Checked 250/481 nodes... Found 17 with BOLT12 support
Checked 300/481 nodes... Found 19 with BOLT12 support
Checked 350/481 nodes... Found 29 with BOLT12 support
Checked 400/481 nodes... Found 32 with BOLT12 support
Checked 450/481 nodes... Found 33 with BOLT12 support

Found 37 nodes with onion message routing support for BOLT12

=== Top BOLT12 Capable Nodes (sorted by channels (descending)) ===
Alias                     PubKey               Channels   Public/Onion Address          
-------------------------------------------------------------------------------------
Faucet LND                02465ed5be53d04fd... 918        104.26.11.226:9735
HOPPINGTOTE               036d478eb1ae5e236... 9          45.33.17.66:39735
lsps mutinynet            0371d6fd7d75de2d0... 8          44.219.111.31:39735
z                         03fa8ad0100ad4c6d... 8          129.159.126.190:39735
cumulo-mutinynet          026b14431ccd5c953... 7          3.148.132.73:9735
PEEVEDTOTE-v24.05         02c1745d21aab2823... 6          45.33.17.66:39735
GREENFELONY               0366abc8eb4da61e3... 6          45.33.17.66:39735
GREENCHIPMUNK             03f26f1d14221a6b7... 4          Unknown
                          02386ee4cfc9b5f1b... 3          0.0.0.0:9735
                          02764a0e09f2e8ec6... 3          192.243.215.101:27110
                          02bee11173aeb017f... 3          127.0.0.1:26030
shadowysupernode          02523f295cff1a319... 2          3szgdy7tbeiftowerisbwqe6berwbd
LATENTTRAWL               0258df7807680d0ec... 2          zbrdujcolszbhfp7tk3c2wc3clq3mb
JUNIORWALK                02f4b654026b3913e... 2          5.75.146.5:39735
LQwD-Mutinynet            03466abad0e5162c0... 2          192.243.215.98:25030
                          03dcf4a8bcd27c418... 2          0.0.0.0:9735
                          020911655d588cbc0... 1          0.0.0.0:9735
                          020ca7ab563c72c1c... 1          0.0.0.0:25320
                          0226ad53b7b055c2d... 1          0.0.0.0:9735
IRATENIGHT                02360dfd86f3ceef8... 1          Unknown

Saved detailed results to bolt12_capable_nodes.json

=== Example Connection Commands ===
To connect to the top node using lncli:
lncli connect 02465ed5be53d04fde66c9418ff14a5f2267723810176c9212b722e542dc1afb1b@104.26.11.226:9735

For other implementations:
Core Lightning: lightning-cli connect 02465ed5be53d04fde66c9418ff14a5f2267723810176c9212b722e542dc1afb1b@104.26.11.226:9735
Eclair: eclair-cli connect --uri=02465ed5be53d04fde66c9418ff14a5f2267723810176c9212b722e542dc1afb1b@104.26.11.226:9735
```