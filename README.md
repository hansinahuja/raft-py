# Distributed Key-Value Store with RAFT Consensus

## Overview
This project implements a distributed key-value store using the RAFT consensus protocol. It has a frontend service which manages client interactions, RAFT servers that handle consensus and data storage, and a comprehensive testing framework.

Key features:
- Leader election and log replication
- Fault tolerance with network partition handling
- Persistent storage with crash recovery
- Linearizable read/write operations

## Quick Start

### Prerequisites

1. **Go 1.23.4**
```bash
wget https://go.dev/dl/go1.23.4.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.23.4.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin
```

2. **Python Environment**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### Running the System

1. Start frontend:
```bash
python frontend.py
```

2. Run tests:
Test using our **modified** testing script. We made these modifications to account for constraints on Python's gRPC. More details in our project report.

```bash
cd CS380D-RaftProject/testing
go run testfrontend.go
```

## Project Structure
```
.
├── config.init       # RAFT configurations
├── frontend.py       # Client request handling and server management
├── server.py        # RAFT consensus implementation
├── test_client.py        # Client for command line requests
└── CS380D-RaftProject
    └── testing 
        └── testfrontend.go  # Our modified testing script
```