import configparser
import socket
import sys
import os
import grpc
from concurrent import futures
from threading import Thread, Timer
import random
import raft_pb2
import raft_pb2_grpc
import math
import json
import time
import tempfile
import subprocess


CONFIG_FILE = "config.ini"

ADDRESS = {}
SERVER_ID = None
MIN_RANDOM_TIMEOUT = None
MAX_RANDOM_TIMEOUT = None
LEADER_TIMEOUT = None
MAX_WORKERS = None
PERSISTENT_STATE_PATH = None
BASE_SOURCE_PORT = None

class CustomSocketFactory:
    def __init__(self, source_port):
        self.source_port = source_port

    def create_socket(self, family, type, proto):
        sock = _socket.socket(family, type, proto)
        sock.bind(('localhost', self.source_port))
        return sock


class KeyValueStore(raft_pb2_grpc.KeyValueStoreServicer):
    def __init__(self):

        super().__init__()

        # Persistent state
        if (os.path.isfile(os.path.join(PERSISTENT_STATE_PATH, f'server_{SERVER_ID}.json'))):
            self.currentTerm, self.votedFor, self.log = self.read_persistent_memory()
        else:
            self.currentTerm = 0
            self.votedFor = None
            self.log = []
        self.id = SERVER_ID
         
        # Volatile state
        self.commitIndex = 0
        self.lastApplied = 0 

        # Volatile state for leader
        self.nextIndex = []
        self.matchIndex = []

        # Other members
        self.role = "follower"
        self.kv_store = {} 
        self.leaderId = None
        self.randomTimeout = random.uniform(MIN_RANDOM_TIMEOUT, MAX_RANDOM_TIMEOUT) 

        # print("Verifying port setup...")
        # self.verify_port_connections()

        self.timer = Timer(self.randomTimeout, self.declare_candidacy)
        self.timer.start()
        self.voteRequestCalls = []
        self.votes = []
        self.servers_to_clients = {}
        self.setup_client_connections(SERVER_ID)

    def setup_client_connections(self, me):
        number_of_servers = len(ADDRESS)
        start_idx = 7001 + me * number_of_servers
        
        for i in range(number_of_servers):
            if i != me:  # Skip creating connection to self
                port_number = 9001 + i
                source_port = start_idx + i
                print(f"dst port_number {port_number}")
                print(f"src port number {source_port}")
                
                try:
                    # Create socket with specific source port
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.bind(('', start_idx + i))
                    
                    # Create channel options with custom socket
                    channel_options = [
                        ('grpc.custom_primary_socket', sock.fileno())
                    ]
                    
                    # Create gRPC channel
                    channel = grpc.insecure_channel(
                        f'localhost:{port_number}',
                        options=channel_options
                    )

                    # # Store the channel
                    self.servers_to_clients[i] = channel
                    
                except Exception as e:
                    print(f"Failed to connect: {e}")

    def read_persistent_memory(self):
        with open(os.path.join(PERSISTENT_STATE_PATH, f'server_{SERVER_ID}.json'), 'r') as file:
            data = json.load(file)
        return data["currentTerm"], data["votedFor"], data["log"]
    
    def write_persistent_memory(self):
        data = {
            "currentTerm": self.currentTerm,
            "votedFor": self.votedFor,
            "log": self.log
        }
        if not os.path.exists(PERSISTENT_STATE_PATH):
            os.makedirs(PERSISTENT_STATE_PATH)
        with open(os.path.join(PERSISTENT_STATE_PATH, f'server_{SERVER_ID}.json'), 'w') as file:
            json.dump(data, file)


    def create_channel_with_source_port(self, target_id):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("source: ", BASE_SOURCE_PORT + self.id*len(ADDRESS) + target_id, "target: ", ADDRESS[target_id])
        sock.bind(('', BASE_SOURCE_PORT + self.id*len(ADDRESS) + target_id))
        channel_options = [
            ('grpc.custom_primary_socket', sock.fileno())
        ]
        channel = grpc.insecure_channel(ADDRESS[target_id], options=channel_options)
        return channel
        
    def get_group(self, id):
        # TODO(debajit): add group membership logic here
        return 0

    def start_timer(self, callback_fn):
        if self.timer.is_alive():
            self.timer.cancel()
        self.timer = Timer(self.randomTimeout, callback_fn)
        self.timer.start()


    def send_heartbeat(self, server_id):

        if self.role != 'leader':
            return
        
        if self.get_group(self.id) != self.get_group(server_id):
            return

        # channel = self.create_channel_with_source_port(server_id)
        channel = self.servers_to_clients[server_id]
        stub = raft_pb2_grpc.KeyValueStoreStub(channel)

        try:
            request = raft_pb2.AppendEntriesRequest(
                term=self.currentTerm,
                leaderId=self.id,
                prevLogIndex=self.nextIndex[server_id]-1,
                prevLogTerm=self.log[self.nextIndex[server_id]-2]['term'] if self.nextIndex[server_id] > 1 else 0,
                entries=[self.log[self.nextIndex[server_id]-1]] if len(self.log) >= self.nextIndex[server_id] else [],
                leaderCommit=self.commitIndex
            )

            response = stub.appendEntries(request)

            if response.term > self.currentTerm:
                self.votedFor = None
                self.currentTerm = response.term
                self.randomTimeout = random.uniform(MIN_RANDOM_TIMEOUT, MAX_RANDOM_TIMEOUT)
                self.role = 'follower'
                print (f'================= Term {self.currentTerm} =================')
                print(f'Term: {self.term}\t Role: {self.role}')
                self.write_persistent_memory()
                self.start_timer(self.declare_candidacy)

            elif response.success:
                if len(request.entries) != 0:
                    self.matchIndex[server_id] = self.nextIndex[server_id]
                    self.nextIndex[server_id] += 1

            else:
                self.matchIndex[server_id] = min(self.matchIndex[server_id], self.nextIndex[server_id]-2)
                self.nextIndex[server_id] -= 1

        except Exception as e:
            pass

    def update_kv_store(self):
        if self.role != "leader":
            return

        for t in self.voteRequestCalls:
            t.join(0)

        self.nextIndex[self.id] = len(self.log)+1
        self.matchIndex[self.id] = len(self.log)

        successful_commits = 0
        for i in range(len(self.matchIndex)):
            if self.matchIndex[i] - 1 >= self.commitIndex:
                successful_commits += 1

        if successful_commits > math.floor(len(self.matchIndex) / 2):
            # print("------------> Look here:")
            # print("Match index: ", self.matchIndex)
            # print("Commit index: ", self.commitIndex)
            # print("Successful commits: ", successful_commits)
            # print("Log: ", self.log)
            # print("Last applied: ", self.lastApplied)
            self.commitIndex += 1
            

        while self.lastApplied < self.commitIndex:
            self.kv_store[self.log[self.lastApplied]['key']] = self.log[self.lastApplied]['value']
            self.lastApplied += 1

        self.voteRequestCalls = []
        for server_id in ADDRESS.keys():
            if server_id != self.id:
                self.voteRequestCalls.append(Thread(target=self.send_heartbeat,
                                                    args=[server_id]))
        for t in self.voteRequestCalls:
            t.start()

        self.start_timer(self.update_kv_store)

    def count_votes(self):
        for t in self.voteRequestCalls:
            t.join(0)

        print(f"Term: {self.currentTerm}: received {sum(self.votes)} votes from {len(ADDRESS)} servers")
        min_votes = math.ceil(len(ADDRESS) / 2)
        if len(ADDRESS) % 2 == 0:
            min_votes += 1

        if sum(self.votes) < min_votes:
            print(f'Term: {self.currentTerm}\t Role: {self.role}')
            self.role = 'follower'
            self.randomTimeout = random.uniform(MIN_RANDOM_TIMEOUT, MAX_RANDOM_TIMEOUT)
            self.start_timer(self.declare_candidacy)
        else:
            self.role = 'leader'
            self.leaderId = self.id
            self.randomTimeout = LEADER_TIMEOUT
            self.matchIndex = [0 for i in range(len(ADDRESS))]
            self.nextIndex = [(len(self.log)+1) for i in range(len(ADDRESS))]
            print(f'Term: {self.currentTerm}\t Role: {self.role}')

            self.voteRequestCalls = []
            for server_id in ADDRESS.keys():
                if server_id != self.id:
                    self.voteRequestCalls.append(Thread(target=self.send_heartbeat,
                                                        args=[server_id]))
            for t in self.voteRequestCalls:
                t.start()

            self.start_timer(self.update_kv_store)


    def send_vote_request(self, server_id):

        if self.role != "candidate":
            return
        
        if self.get_group(self.id) != self.get_group(server_id):
            return

        # channel = self.create_channel_with_source_port(server_id)
        channel = self.servers_to_clients[server_id]
        stub = raft_pb2_grpc.KeyValueStoreStub(channel)
        # print('Gen stub')
        try:
            lastLogTerm = 0
            if len(self.log):
                lastLogTerm = self.log[-1]['term']
            request = raft_pb2.RequestVoteRequest(
                term=self.currentTerm,
                candidateId=self.id,
                lastLogIndex=len(self.log),
                lastLogTerm=lastLogTerm)
            
            response = stub.requestVote(request)

            print('Response from', ADDRESS[server_id], response)

            if response.voteGranted:
                self.votes[server_id] = 1

            elif response.term > self.currentTerm:
                self.votedFor = None
                self.currentTerm = response.term
                self.randomTimeout = random.uniform(MIN_RANDOM_TIMEOUT, MAX_RANDOM_TIMEOUT)
                self.role = 'follower'
                print (f'================= Term {self.currentTerm} =================')
                print(f'Term: {self.currentTerm}\t Role: {self.role}')
                self.write_persistent_memory()
                self.start_timer(self.declare_candidacy)

        except Exception as e:
            pass


    def declare_candidacy(self):
        self.role = 'candidate'
        self.currentTerm += 1
        self.votedFor = self.id
        # self.leaderId = self.id
        self.write_persistent_memory()
        print('Starting election...')
        print (f'================= Term {self.currentTerm} =================')
        print(f'currentTerm: {self.currentTerm}\t votedFor: {self.votedFor}')
        
        
        self.votes = [0]*len(ADDRESS)
        self.votes[self.id] = 1
        self.voteRequestCalls = []
        for server_id in ADDRESS.keys():
            if server_id != self.id:
                self.voteRequestCalls.append(Thread(target=self.send_vote_request,
                                                    args=[server_id]))
        for t in self.voteRequestCalls:
            t.start()

        self.start_timer(self.count_votes)


    # RPC endpoints

    def ping(self, request, context):
        if self.role != 'candidate':
            return raft_pb2.GenericResponse(success=True)
        return raft_pb2.GenericResponse(success=False)

    def GetState(self, request, context):
        return raft_pb2.State(term=self.currentTerm, isLeader=(self.role=='leader'))
    
    def has_quorum(self):
        if self.role == "leader":
            matching_servers = 1
            for i in range(len(self.matchIndex)):
                if i != self.id and self.matchIndex[i] >= len(self.log) - 1:
                    matching_servers += 1
            return matching_servers > len(ADDRESS) / 2
        elif self.role == "follower":
            return time.time() - self.last_heartbeat < self.heartbeat_timeout
        return False


    def Get(self, request, context):
        print("key ", request.arg, " | value ",self.kv_store[request.arg])
        if request.arg in self.kv_store:
            return raft_pb2.KeyValue(key=request.arg, value=self.kv_store[request.arg])
        else:
            return raft_pb2.KeyValue(key=request.arg, value='None')
        
    def Put(self, request, context):
        print(request)

        if self.role == "leader":
            self.log.append({"term": self.currentTerm,
                            "key": request.key,
                            "value": request.value})
            curr_index = len(self.log)-1
            self.write_persistent_memory()
            time.sleep(0.9)
            if self.kv_store[request.key] != request.value:
                print('PUT RETURNING FALSE')
                return raft_pb2.GenericResponse(success=False)

            print('PUT RETURNING TRUE')
            return raft_pb2.GenericResponse(success=True)
        
        elif self.role == "follower":
        # else:
            # channel = self.create_channel_with_source_port(self.leaderId)
            channel = self.servers_to_clients[self.leaderId]
            stub = raft_pb2_grpc.KeyValueStoreStub(channel)
            try:
                response = stub.Put(request)
                print('FOR PUT LEADER SAID', response)
                print("leader", self.leaderId)
                return response
            except:
                print("Leader unavailable!")
                return raft_pb2.GenericResponse(success=False)
            
        return raft_pb2.GenericResponse(success=False)
            

    def requestVote(self, request, context):

        if request.term < self.currentTerm:
            if self.role == 'follower':
                self.start_timer(self.declare_candidacy)
            return raft_pb2.RequestVoteResponse(term=self.currentTerm, voteGranted=False)

        if request.term == self.currentTerm:
            if self.votedFor is not None or request.lastlogIndex < len(self.log) or self.role != "follower" or (request.lastLogIndex == len(self.log) and self.log[request.lastLogIndex-1]['term'] != request.lastLogTerm):
                if self.role == 'follower':
                    self.start_timer(self.declare_candidacy)
                return raft_pb2.RequestVoteResponse(term=self.currentTerm, voteGranted=False)

            else:
                self.votedFor = request.candidateId
                self.leaderId = request.candidateId
                self.write_persistent_memory()
                print(f'currentTerm: {self.currentTerm}\t votedFor: {self.votedFor}')
                if self.role == 'follower':
                    self.start_timer(self.declare_candidacy)
                return raft_pb2.RequestVoteResponse(term=self.currentTerm, voteGranted=True)


        if request.term > self.currentTerm:
            print (f'================= Term {request.term} =================')
            self.leaderId = request.candidateId
            self.votedFor = request.candidateId
            self.currentTerm = request.term
            self.role = 'follower'
            print(f'Term: {self.currentTerm}\t VotedFor: {request.candidateId}')
            print(f'Term: {self.currentTerm}\t Role: {self.role}')
            self.write_persistent_memory()
            self.start_timer(self.declare_candidacy)
            return raft_pb2.RequestVoteResponse(term=self.currentTerm, voteGranted=True)

    def appendEntries(self, request, context):
        # print("received from ", context.peer())
        if request.term < self.currentTerm:
            return raft_pb2.AppendEntriesResponse(term=self.currentTerm, success=False) 
        
        if request.term >= self.currentTerm:
            self.last_heartbeat = time.time()

        if request.term > self.currentTerm:
            print (f'================= Term {request.term} =================')
            self.currentTerm = request.term
            self.leaderId = request.leaderId
            self.votedFor = None
            self.role = 'follower'
            print(f'Term: {self.currentTerm}\t Role: {self.role}')
            self.write_persistent_memory()
            self.start_timer(self.declare_candidacy)

        if request.prevLogIndex > len(self.log):
            if self.role == 'follower':
                self.start_timer(self.declare_candidacy)
            return raft_pb2.AppendEntriesResponse(term=self.currentTerm, success=False)

        self.log = self.log[:request.prevLogIndex]
        if request.entries:
            self.log.append({"term": request.entries[0].term,
                            "key": request.entries[0].key,
                            "value": request.entries[0].value})
        self.write_persistent_memory()


        if self.commitIndex < request.leaderCommit:
            self.commitIndex = min(request.leaderCommit, len(self.log))
            while self.lastApplied < self.commitIndex:
                self.kv_store[self.log[self.lastApplied]['key']] = self.log[self.lastApplied]['value']
                self.lastApplied += 1
        
        

        self.start_timer(self.declare_candidacy)
        return raft_pb2.AppendEntriesResponse(term=self.currentTerm, success=True)



def update_config(id, remove=False):
    global ADDRESS
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    if remove:
        active_servers = config.get('Servers', 'active').split(',')
        active_servers = [s for s in active_servers if s != str(id)]
        config.set('Servers', 'active', ','.join(active_servers))
        with open(CONFIG_FILE, "w+") as configfile:
            config.write(configfile)
        return

    base_address = config.get('Global', 'base_address')
    base_port = int(config.get('Servers', 'base_port'))
    active_servers = config.get('Servers', 'active').split(',')
    for server_id in active_servers:
        server_id = int(server_id)
        if server_id == -1:
            continue
        if (id == server_id):
            pass
            # print('Server ID already taken! Please use a different ID.')
            # sys.exit()
        server_address = f'{base_address}:{str(base_port + server_id)}'
        ADDRESS[server_id] = server_address

    # ADDRESS[id] = f'{base_address}:{str(base_port + id)}'
    # config.set('Servers', 'active', f'{config.get("Servers", "active")},{id}')
    # with open(CONFIG_FILE, "w+") as configfile:
    #     config.write(configfile)
    
    
def initialise_globals(id):
    global SERVER_ID, MIN_RANDOM_TIMEOUT, MAX_RANDOM_TIMEOUT, LEADER_TIMEOUT, MAX_WORKERS, PERSISTENT_STATE_PATH, BASE_SOURCE_PORT
    SERVER_ID = id
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    MIN_RANDOM_TIMEOUT = float(config.get('Servers', 'min_random_timeout'))
    MAX_RANDOM_TIMEOUT = float(config.get('Servers', 'max_random_timeout'))
    LEADER_TIMEOUT = float(config.get('Servers', 'leader_timeout'))
    MAX_WORKERS = int(config.get('Servers', 'max_workers'))
    PERSISTENT_STATE_PATH = str(config.get('Servers', 'persistent_state_path'))
    BASE_SOURCE_PORT = int(config.get('Servers', 'base_source_port'))

def run_server(id):
    update_config(id)
    initialise_globals(id)
    print(f'Starting server {id} at port {ADDRESS[id]}...')
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=MAX_WORKERS))
    raft_pb2_grpc.add_KeyValueStoreServicer_to_server(KeyValueStore(), server)
    server.add_insecure_port(ADDRESS[id])
    try:
        server.start()

        while True:
            server.wait_for_termination()
    except:
        print("Unexpected Error!")
        # update_config(id, remove=True)
        sys.exit()

if __name__ == "__main__":
    if sys.argv[1].isdigit() == False:
        print('Invalid server ID!')
        sys.exit()
    print("started")
    run_server(int(sys.argv[1]))