import grpc
import raft_pb2
import raft_pb2_grpc

FRONTEND_PORT = 8001
client_id = 1
request_id = 0

def get_frontend_stub():
    channel = grpc.insecure_channel(f'localhost:{FRONTEND_PORT}')
    return raft_pb2_grpc.FrontEndStub(channel)

def get_next_request_id():
    global request_id
    request_id += 1
    return request_id

def get_state():
    # not sure of this
    stub = get_frontend_stub()
    try:
        response = stub.Get(raft_pb2.GetKey(
            key="state",
            ClientId=client_id,
            RequestId=get_next_request_id()
        ))
        print(f'Status: {"Success" if not response.wrongLeader else "Failed"}')
    except Exception as e:
        print(f"Error: {e}")

def set_val(key, value):
    stub = get_frontend_stub()
    try:
        response = stub.Put(raft_pb2.KeyValue(
            key=key,
            value=value,
            ClientId=client_id,
            RequestId=get_next_request_id()
        ))
        print(response)
        if response.wrongLeader:
            print("Put failed: No leader available")
        else:
            print("Put successful")
    except Exception as e:
        print(f"Error: {e}")

def get_val(key):
    stub = get_frontend_stub()
    try:
        response = stub.Get(raft_pb2.GetKey(
            key=key,
            ClientId=client_id,
            RequestId=get_next_request_id()
        ))
        if response.wrongLeader:
            print("Get failed: No leader available")
        else:
            print(f'{key} = {response.value}')
    except Exception as e:
        print(f"Error: {e}")

def start_server(server_id):
    stub = get_frontend_stub()
    try:
        response = stub.StartServer(raft_pb2.IntegerArg(arg=server_id))
        # print(response, "()")
        if response.wrongLeader:
            print(f"Failed to start server: {response.error}")
        else:
            print(f"Started {server_id} successfully")
    except Exception as e:
        print(f"Error: {e}")

def start_servers(num_servers):
    stub = get_frontend_stub()
    try:
        response = stub.StartRaft(raft_pb2.IntegerArg(arg=num_servers))
        # print(response, "()")
        if response.wrongLeader:
            print(f"Failed to start servers: {response.error}")
        else:
            print(f"Started {num_servers} servers successfully")
    except Exception as e:
        print(f"Error: {e}")

def run_client():
    print("RAFT Client")
    print("Commands: start <num>, startserver <num>, put <key> <value>, get <key>, getstate, quit")
    
    while True:
        try:
            command = input("cmd> ").strip().split()
            print(command)
            if not command:
                continue

            if command[0] == "start":
                start_servers(int(command[1]))
            elif command[0] == "startserver":
                start_server(int(command[1]))
            elif command[0] == "getstate":
                get_state()
            elif command[0] == "put":
                set_val(command[1], command[2])
            elif command[0] == "get":
                get_val(command[1])
            elif command[0] == "quit":
                break
            else:
                print("Invalid command")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_client()