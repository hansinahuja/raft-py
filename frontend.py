import grpc, os, signal
import raft_pb2
import raft_pb2_grpc
from concurrent import futures
import configparser
import subprocess
import time
import sys
from typing import Dict, List, Optional, Tuple
import shutil
from concurrent.futures import ThreadPoolExecutor
import platform
import psutil
from threading import Thread

CONFIG_FILE = "config.ini"
FRONTEND_PORT = 8001
BASE_SERVER_PORT = 9001

class FrontEndService(raft_pb2_grpc.FrontEndServicer):
    def __init__(self):
        self.address_map = {} 
        self.raft_processes = []
        self.duplicate_request_cache = {} 
        self.current_leader = None
        self.base_address = '127.0.0.1'
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    def delete_directory(self, directory_path):
        if os.path.exists(directory_path):
            shutil.rmtree(directory_path)
            print(f"Directory '{directory_path}' and its contents have been deleted.")
        else:
            print(f"Directory '{directory_path}' does not exist.")

    def get_stub(self):
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        base_address = config.get('Global', 'base_address')
        base_port = int(config.get('Servers', 'base_port'))
        active_servers = config.get('Servers', 'active').split(',')

        for i in range(len(active_servers)-1, -1, -1):
            server_id = int(active_servers[i])
            if server_id == -1:
                continue
            server_address = f'{base_address}:{str(base_port + server_id)}'
            channel = grpc.insecure_channel(server_address)
            stub = raft_pb2_grpc.KeyValueStoreStub(channel)
            try:
                res = stub.ping(raft_pb2.Empty())
                print('res', res)
                if res.success:
                    print("Connecting to server ", server_id)
                    return stub
                else:
                    print("Failed to connect to ", server_id)
                    continue
            except Exception as e:
                print(e)
                print("Failed to connect to ", server_id, " : ", server_address)
                pass

        print("No available servers!")

    def Put(self, request, context):
        return self.executor.submit(self.put_task, request, context).result()

    def put_task(self, request, context):
        leader_stub = self.get_stub()
        if not leader_stub:
            return raft_pb2.Reply(wrongLeader=True, error="No leader available")
        # print("check")
        try:
            server_request = raft_pb2.KeyValue(
                key=request.key,
                value=request.value
            )
            # print("check2")
            pre_put = time.time()
            response = leader_stub.Put(server_request)
            # print("put ", request)
            # time.sleep(0.4)
            after_put = time.time()
            print("Time taken for server Put: ", (after_put - pre_put) * 1000)
            reply = raft_pb2.Reply(
                wrongLeader=not response.success,
                error="" if response.success else "Put failed"
            )
            # print('returning from put:', reply)
            # print('Response:', response)
            if response.success == False:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Did not reach consensus")
            return reply

        except Exception as e:
            self.current_leader = None
            return raft_pb2.Reply(wrongLeader=True, error=str(e))

    def Get(self, request, context):
        return self.executor.submit(self.get_task, request).result()

    def get_task(self, request):
        max_retries = 1
        retry_delay = 0.2  # 100ms

        time.sleep(0.9)

        for retry in range(max_retries):
            leader_stub = self.get_stub()
            if not leader_stub:
                return raft_pb2.Reply(wrongLeader=True, error="No servers available")

            try:
                server_request = raft_pb2.StringArg(arg=request.key)
                # print("get ", request)
                response = leader_stub.Get(server_request)
                # print("get response: ", response)
                if response.value != 'None': 
                    return raft_pb2.Reply(
                        wrongLeader=False,
                        value=response.value
                    )
            
                if retry < max_retries - 1:
                    time.sleep(retry_delay)
                    continue

            except Exception as e:
                self.current_leader = None
                if retry < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return raft_pb2.Reply(wrongLeader=True, error=str(e))

    def Replace(self, request, context):
        return self.Put(request, context)

    def StartRaft(self, request, context):
        try:
            startime = time.time()
            num_servers = request.arg
            self.delete_directory("memory")
            if num_servers <= 0:
                return raft_pb2.Reply(wrongLeader=True, error="Number of servers must be positive")
            
            self.current_leader = None
            self.address_map.clear()

            # Update config
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
            config.set('Servers', 'active', ",".join(map(str, range(num_servers))))
            with open(CONFIG_FILE, "w+") as configfile:
                config.write(configfile)

            # Setup address map
            for i in range(num_servers):
                server_id = i
                server_port = BASE_SERVER_PORT + server_id
                self.address_map[server_id] = f"{self.base_address}:{server_port}"

            print(f"Starting RAFT cluster with {num_servers} servers")
            print(f"Address map: {self.address_map}")

            current_dir = os.path.dirname(os.path.abspath(__file__))
            server_script = os.path.join(current_dir, "server.py")

            for server_id in range(num_servers):
                try:
                    # Create log file for server
                    log_file = open(f"server_{server_id}.log", "w", buffering=1)
                    log_file.write(f"=== Starting server {server_id} at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                    log_file.flush()

                    # Start the server process directly
                    python_cmd = (
                        'import os, sys, signal; '
                        'signal.signal(signal.SIGTERM, signal.SIG_DFL); '
                        f'import server; server.run_server({server_id})'
                    )

                    cmd = [
                        'bash',
                        '-c',
                        f'cd {current_dir} && exec -a raftserver{server_id+1} python3 -c \'{python_cmd}\''
                    ]
                    
                    process = subprocess.Popen(
                        cmd,
                        stdout=log_file,
                        stderr=log_file,
                        # preexec_fn=os.setsid
                    )
                    
                    self.raft_processes.append((process, log_file))
                    print(f"Started server {server_id} with PID {process.pid}")

                except Exception as e:
                    print(f"Error starting server {server_id}: {str(e)}")
                    return raft_pb2.Reply(wrongLeader=True, error=f"Failed to start server {server_id}")

            time.sleep(0.5)
            endtime = time.time()
            print("Time taken for StartRaft: ", endtime - startime)
            return raft_pb2.Reply(wrongLeader=False)

        except Exception as e:
            print(f"Error in StartRaft: {str(e)}")
            return raft_pb2.Reply(wrongLeader=True, error=str(e))


    def StartServer(self, request, context):
        try:
            startime = time.time()
            server_id = request.arg
            
            # Setup address
            server_port = BASE_SERVER_PORT + server_id
            self.address_server = f"{self.base_address}:{server_port}"

            print(f"Starting server {server_id}")
            print(f"Address map: {self.address_server}")

            current_dir = os.path.dirname(os.path.abspath(__file__))

            try:
                # Create log file for server
                log_file = open(f"server_{server_id}.log", "w", buffering=1)

                # Write initial log entry with timestamp
                log_file.write(f"=== Starting server {server_id} at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                log_file.flush()

                # Start the server process directly
                python_cmd = (
                    'import os, sys, signal; '
                    'signal.signal(signal.SIGTERM, signal.SIG_DFL); '
                    f'import server; server.run_server({server_id})'
                )

                cmd = [
                    'bash',
                    '-c',
                    f'cd {current_dir} && exec -a raftserver{server_id+1} python3 -c \'{python_cmd}\''
                ]
                
                process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=log_file,
                    # preexec_fn=os.setsid
                )
                
                self.raft_processes.append((process, log_file))
                print(f"Started server {server_id} with PID {process.pid}")

            except Exception as e:
                print(f"Error starting server {server_id}: {str(e)}")
                # self.cleanup_raft_processes()
                return raft_pb2.Reply(wrongLeader=True, error=f"Failed to start server {server_id}")

            time.sleep(0.5)
            endtime = time.time()
            print("Time taken for Starting server: ", endtime - startime)
            return raft_pb2.Reply(wrongLeader=False)

        except Exception as e:
            print(f"Error in StartServer: {str(e)}")
            # self.cleanup_raft_processes()
            return raft_pb2.Reply(wrongLeader=True, error=str(e))


    def cleanup_raft_processes(self):
        """Clean up running RAFT processes."""
                
        for process, log_file, pgid in self.raft_processes:
            try:
                # Check if process is still running
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=1)  # Wait for graceful termination
                    
                # Force kill if still running
                if process.poll() is None:
                    process.kill()
                
                # Close log file
                if log_file:
                    log_file.close()
                    
            except Exception as e:
                print(f"Error cleaning up process {process.pid}: {str(e)}")

        # Clear process list
        self.raft_processes.clear()

        # Clean up all remaining processes
        cleanup_commands = [
            "pkill -9 -f raftserver",
            "pkill -9 -f 'start_proc_.*\.py'",
            "pkill -9 -f 'server\.py'"
        ]
        
        for cmd in cleanup_commands:
            try:
                subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL)
            except:
                pass

        # Additional cleanup for any orphaned processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'server.py' in ' '.join(proc.info['cmdline'] or []):
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    frontend = FrontEndService()
    raft_pb2_grpc.add_FrontEndServicer_to_server(frontend, server)
    server.add_insecure_port(f'[::]:{FRONTEND_PORT}')
    
    try:
        server.start()
        print(f"Frontend server started on port {FRONTEND_PORT}")
        server.wait_for_termination()
    finally:
        pass
        # frontend.cleanup_raft_processes()

if __name__ == '__main__':
    serve()