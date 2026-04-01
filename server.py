"""
Real-Time Multi-Client Chat Server
TCP Socket Programming - Computer Networks Lab Mini-Project
"""

import socket
import threading
import os
import json
import datetime
import struct

# ─────────────────────────────────────────────
#  CONFIGURATION  (edit as needed)
# ─────────────────────────────────────────────
HOST = "0.0.0.0"          # Listen on all interfaces
PORT = 9999               # Change port here if needed

# ─────────────────────────────────────────────
#  PRE-DEFINED ROOMS  (only server creates rooms)
# ─────────────────────────────────────────────
ROOMS = {
    "General Chat": {
        "type": "public",
        "password": None,
        "connected_clients": []   # list of usernames
    },
    "Project Team": {
        "type": "private",
        "password": "team123",
        "connected_clients": []
    },
    "Faculty Room": {
        "type": "private",
        "password": "faculty@456",
        "connected_clients": []
    },
    "Study Hall": {
        "type": "public",
        "password": None,
        "connected_clients": []
    },
}

# ─────────────────────────────────────────────
#  RUNTIME STATE
# ─────────────────────────────────────────────
# username -> {"socket": sock, "room": room_name}
clients = {}
clients_lock = threading.Lock()

# Create required directories
for room in ROOMS:
    safe = room.replace(" ", "_")
    os.makedirs(f"shared_files/{safe}", exist_ok=True)
os.makedirs("chat_history", exist_ok=True)
os.makedirs("downloads", exist_ok=True)   # just in case server is also client


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def timestamp():
    return datetime.datetime.now().strftime("%H:%M:%S")


def log_to_history(room_name, text):
    safe = room_name.replace(" ", "_")
    path = f"chat_history/{safe}.txt"
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def get_chat_history(room_name):
    safe = room_name.replace(" ", "_")
    path = f"chat_history/{safe}.txt"
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()[-100:]   # send last 100 messages
    
def send_msg(sock, msg_dict):
    """Send a JSON message prefixed with 4-byte length."""
    try:
        data = json.dumps(msg_dict).encode("utf-8")
        sock.sendall(struct.pack(">I", len(data)) + data)
        return True
    except Exception:
        return False


def recv_msg(sock):
    """Receive a length-prefixed JSON message. Returns dict or None."""
    try:
        raw_len = _recv_exact(sock, 4)
        if raw_len is None:
            return None
        length = struct.unpack(">I", raw_len)[0]
        raw_data = _recv_exact(sock, length)
        if raw_data is None:
            return None
        return json.loads(raw_data.decode("utf-8"))
    except Exception:
        return None


def _recv_exact(sock, n):
    """Read exactly n bytes from socket."""
    buf = b""
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        except Exception:
            return None
    return buf


def broadcast_to_room(room_name, msg_dict, exclude=None):
    """Send a message to all clients in a room."""
    with clients_lock:
        targets = [
            (uname, info["socket"])
            for uname, info in clients.items()
            if info["room"] == room_name and uname != exclude
        ]
    for uname, sock in targets:
        send_msg(sock, msg_dict)


def get_room_file_list(room_name):
    safe = room_name.replace(" ", "_")
    folder = f"shared_files/{safe}"
    try:
        return os.listdir(folder)
    except Exception:
        return []


def rooms_info_payload():
    """Build a list of room descriptors for clients."""
    info = []
    for rname, rdata in ROOMS.items():
        info.append({
            "name": rname,
            "type": rdata["type"],
            "members": len(rdata["connected_clients"])
        })
    return info


# ─────────────────────────────────────────────
#  CLIENT HANDLER
# ─────────────────────────────────────────────

def handle_client(sock, addr):
    username = None
    current_room = None

    try:
        # ── Step 1: receive username ──────────────────
        msg = recv_msg(sock)
        if not msg or msg.get("type") != "login":
            sock.close()
            return

        username = msg.get("username", "").strip()
        if not username:
            send_msg(sock, {"type": "error", "text": "Invalid username."})
            sock.close()
            return

        with clients_lock:
            if username in clients:
                send_msg(sock, {"type": "error", "text": "Username already taken."})
                sock.close()
                return
            clients[username] = {"socket": sock, "room": None}

        print(f"[+] {username} connected from {addr}")

        # ── Step 2: send room list ────────────────────
        send_msg(sock, {"type": "room_list", "rooms": rooms_info_payload()})

        # ── Step 3: room join loop ────────────────────
        while True:
            msg = recv_msg(sock)
            if not msg:
                break

            if msg.get("type") == "join_room":
                room_name = msg.get("room")
                password = msg.get("password", "")

                if room_name not in ROOMS:
                    send_msg(sock, {"type": "error", "text": "Room does not exist."})
                    continue

                room = ROOMS[room_name]

                # Username unique per room
                if username in room["connected_clients"]:
                    send_msg(sock, {"type": "error", "text": "Username taken in this room."})
                    continue

                # Password check
                if room["type"] == "private":
                    if password != room["password"]:
                        send_msg(sock, {"type": "error", "text": "Wrong password."})
                        continue

                # Leave old room if any
                if current_room and current_room in ROOMS:
                    if username in ROOMS[current_room]["connected_clients"]:
                        ROOMS[current_room]["connected_clients"].remove(username)
                    leave_msg = {
                        "type": "system",
                        "text": f"[{timestamp()}] {username} left the room."
                    }
                    broadcast_to_room(current_room, leave_msg)
                    log_to_history(current_room, leave_msg["text"])

                # Join new room
                room["connected_clients"].append(username)
                current_room = room_name
                with clients_lock:
                    clients[username]["room"] = room_name

                send_msg(sock, {
                    "type": "join_ok",
                    "room": room_name,
                    "files": get_room_file_list(room_name),
                    "history": get_chat_history(room_name),
                    "users": ROOMS[room_name]["connected_clients"]
                })

                join_text = f"[{timestamp()}] {username} joined the room."
                broadcast_to_room(room_name, {
                    "type": "user_update",
                    "users": ROOMS[room_name]["connected_clients"]
                })
                log_to_history(room_name, join_text)
                print(f"  {username} joined '{room_name}'")

            elif msg.get("type") == "chat":
                if not current_room:
                    continue
                text = msg.get("text", "").strip()
                if not text:
                    continue

                # Private message /msg <user> <message>
                if text.startswith("/msg "):
                    parts = text[5:].split(" ", 1)
                    if len(parts) < 2:
                        send_msg(sock, {"type": "system", "text": "Usage: /msg <username> <message>"})
                        continue
                    target_user, pm_text = parts
                    with clients_lock:
                        target_info = clients.get(target_user)

                    if target_user == username:
                        send_msg(sock, {"type": "system", "text": "You cannot message yourself."})
                        continue

                    if not target_info or target_info["room"] != current_room:
                        send_msg(sock, {"type": "system", "text": f"User '{target_user}' not found in this room."})
                        continue
                    pm = {
                        "type": "private",
                        "from": username,
                        "text": pm_text,
                        "timestamp": timestamp()
                    }
                    send_msg(target_info["socket"], pm)
                    send_msg(sock, {**pm, "self": True})
                    continue

                chat_msg = {
                    "type": "chat",
                    "from": username,
                    "text": text,
                    "timestamp": timestamp()
                }
                broadcast_to_room(current_room, chat_msg)
                log_entry = f"[{timestamp()}] {username}: {text}"
                log_to_history(current_room, log_entry)

            elif msg.get("type") == "file_upload":
                if not current_room:
                    continue
                filename = os.path.basename(msg.get("filename", "unknown"))
                filesize = msg.get("filesize", 0)

                safe_room = current_room.replace(" ", "_")
                save_path = f"shared_files/{safe_room}/{filename}"

                # Receive raw bytes
                received = 0
                file_data = b""
                while received < filesize:
                    chunk = _recv_exact(sock, min(4096, filesize - received))
                    if chunk is None:
                        break
                    file_data += chunk
                    received += len(chunk)

                if received == filesize:
                    with open(save_path, "wb") as f:
                        f.write(file_data)
                    send_msg(sock, {"type": "system", "text": f"File '{filename}' uploaded successfully."})
                    notify = {
                        "type": "file_notify",
                        "filename": filename,
                        "uploader": username,
                        "timestamp": timestamp(),
                        "files": get_room_file_list(current_room)
                    }
                    broadcast_to_room(current_room, notify)
                    log_to_history(current_room, f"[{timestamp()}] {username} uploaded file: {filename}")
                    print(f"  File '{filename}' saved to {save_path}")
                else:
                    send_msg(sock, {"type": "error", "text": "File transfer incomplete."})

            elif msg.get("type") == "file_download":
                if not current_room:
                    continue
                filename = os.path.basename(msg.get("filename", ""))
                safe_room = current_room.replace(" ", "_")
                fpath = f"shared_files/{safe_room}/{filename}"

                if not os.path.exists(fpath):
                    send_msg(sock, {"type": "error", "text": f"File '{filename}' not found."})
                    continue

                with open(fpath, "rb") as f:
                    file_data = f.read()

                send_msg(sock, {
                    "type": "file_data",
                    "filename": filename,
                    "filesize": len(file_data)
                })
                sock.sendall(file_data)

            elif msg.get("type") == "get_files":
                if current_room:
                    send_msg(sock, {
                        "type": "file_list",
                        "files": get_room_file_list(current_room)
                    })

    except Exception as e:
        print(f"[!] Error with {username or addr}: {e}")

    finally:
        # Cleanup
        if username:
            with clients_lock:
                clients.pop(username, None)
            if current_room and current_room in ROOMS:
                room_clients = ROOMS[current_room]["connected_clients"]
                if username in room_clients:
                    room_clients.remove(username)
                leave_text = f"[{timestamp()}] {username} disconnected."
                broadcast_to_room(current_room, {"type": "system", "text": leave_text})
                log_to_history(current_room, leave_text)
            print(f"[-] {username} disconnected.")
        try:
            sock.close()
        except Exception:
            pass


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(50)

    print("=" * 55)
    print("  CN Chat Server  —  TCP Multi-Client")
    print("=" * 55)
    print(f"  Listening on  {HOST}:{PORT}")
    print(f"  Rooms available: {', '.join(ROOMS.keys())}")
    print("  Press Ctrl+C to stop.\n")

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
    finally:
        server.close()


if __name__ == "__main__":
    main()