"""
Real-Time Multi-Client Chat Client
TCP Socket Programming - Computer Networks Lab Mini-Project

FIX: Download no longer freezes chat.
Architecture: recv_loop owns ALL socket reads. File bytes are drained
inside recv_loop itself, then written to disk — no second thread ever
touches the socket.
"""

import socket
import threading
import os
import json
import struct
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import datetime

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
DEFAULT_SERVER_IP = "192.168.1.34"   # ← Change to server's LAN IP
PORT = 9999

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

EMOJIS = ["😀","😂","😍","🔥","👍","❤️","😎","🎉","😢","🤔",
          "👋","💯","🙏","😡","🥳","😴","👀","🤣","😱","💪"]


# ─────────────────────────────────────────────
#  NETWORK HELPERS
# ─────────────────────────────────────────────

def send_msg(sock, msg_dict):
    try:
        data = json.dumps(msg_dict).encode("utf-8")
        sock.sendall(struct.pack(">I", len(data)) + data)
        return True
    except Exception:
        return False


def recv_msg(sock):
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
    """Read exactly n bytes from socket. Returns None on failure."""
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


# ─────────────────────────────────────────────
#  COLOUR PALETTE
# ─────────────────────────────────────────────
BG        = "#0d1117"
BG2       = "#161b22"
BG3       = "#21262d"
ACCENT    = "#58a6ff"
ACCENT2   = "#3fb950"
TXT       = "#c9d1d9"
TXT_DIM   = "#8b949e"
PRIVATE   = "#f78166"
SYS_CLR   = "#d2a8ff"
BORDER    = "#30363d"
ENTRY_BG  = "#0d1117"
BTN_BG    = "#21262d"
BTN_HOVER = "#30363d"
SEND_BG   = "#238636"
SEND_HOV  = "#2ea043"


# ─────────────────────────────────────────────
#  APPLICATION
# ─────────────────────────────────────────────

class ChatApp:
    def __init__(self):
        self.sock = None
        self.username = ""
        self.current_room = ""
        self.running = False

        # Guards concurrent writes to self.sock.
        # The Tkinter main thread sends chat/control messages; a dedicated
        # upload thread sends raw file bytes. Both paths acquire this lock
        # before touching the socket, so their byte streams never interleave.
        # (Reads are still owned exclusively by _recv_loop — no lock needed there.)
        self._send_lock = threading.Lock()

        # Prevents starting a second upload while one is already in progress.
        # Checked and set on the main thread; cleared by the upload thread
        # via root.after(), so no extra synchronisation is needed.
        self._uploading = False

        # ── Root window ──────────────────────────────
        self.root = tk.Tk()
        self.root.title("CN Chat — Connect")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self._center(self.root, 440, 340)

        self._build_login_screen()
        self.root.mainloop()

    # ─────────────────────────────────────────
    #  UTILITIES
    # ─────────────────────────────────────────

    def _center(self, win, w, h):
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _styled_button(self, parent, text, cmd, bg=BTN_BG, fg=TXT, font=None, **kw):
        f = font or ("Consolas", 10)
        btn = tk.Button(parent, text=text, command=cmd,
                        bg=bg, fg=fg, font=f,
                        relief="flat", cursor="hand2",
                        activebackground=BTN_HOVER, activeforeground=TXT,
                        bd=0, padx=10, pady=6, **kw)
        btn.bind("<Enter>", lambda e: btn.config(bg=BTN_HOVER if bg != SEND_BG else SEND_HOV))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn

    def _label(self, parent, text, size=11, color=TXT, bold=False):
        weight = "bold" if bold else "normal"
        return tk.Label(parent, text=text, bg=BG, fg=color,
                        font=("Consolas", size, weight))

    def _entry(self, parent, show=None, width=28):
        e = tk.Entry(parent, bg=ENTRY_BG, fg=TXT, insertbackground=ACCENT,
                     font=("Consolas", 11), relief="flat",
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT, show=show, width=width)
        return e

    # ─────────────────────────────────────────
    #  LOGIN SCREEN
    # ─────────────────────────────────────────

    def _build_login_screen(self):
        self.root.title("CN Chat — Login")

        for w in self.root.winfo_children():
            w.destroy()

        frame = tk.Frame(self.root, bg=BG)
        frame.pack(expand=True, fill="both", padx=40, pady=30)

        self._label(frame, "CN Chat", 22, ACCENT, bold=True).pack(pady=(0, 4))
        self._label(frame, "Computer Networks Lab Project", 9, TXT_DIM).pack(pady=(0, 24))

        self._label(frame, "Username").pack(anchor="w")
        self.entry_user = self._entry(frame)
        self.entry_user.pack(fill="x", pady=(2, 12))

        self._label(frame, "Server IP Address").pack(anchor="w")
        self.entry_ip = self._entry(frame)
        self.entry_ip.insert(0, DEFAULT_SERVER_IP)
        self.entry_ip.pack(fill="x", pady=(2, 20))

        self.login_status = tk.Label(frame, text="", bg=BG, fg=PRIVATE,
                                     font=("Consolas", 9))
        self.login_status.pack()

        btn = self._styled_button(frame, "  CONNECT  ", self._do_connect,
                                  bg=SEND_BG, fg="white", font=("Consolas", 11, "bold"))
        btn.pack(pady=(8, 0))
        self.entry_user.focus()
        self.root.bind("<Return>", lambda e: self._do_connect())

    def _do_connect(self):
        self.root.unbind("<Return>")
        username = self.entry_user.get().strip()
        ip = self.entry_ip.get().strip()

        if not username:
            self.login_status.config(text="⚠ Please enter a username.")
            return
        if not ip:
            self.login_status.config(text="⚠ Please enter server IP.")
            return

        self.login_status.config(text="Connecting...", fg=TXT_DIM)
        self.root.update()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, PORT))
            sock.settimeout(None)
        except ConnectionRefusedError:
            self.login_status.config(text="✖ Connection refused. Is server running?", fg=PRIVATE)
            return
        except OSError as e:
            self.login_status.config(text=f"✖ {e}", fg=PRIVATE)
            return

        send_msg(sock, {"type": "login", "username": username})
        resp = recv_msg(sock)

        if resp is None:
            self.login_status.config(text="✖ No response from server.", fg=PRIVATE)
            sock.close()
            return
        if resp.get("type") == "error":
            self.login_status.config(text=f"✖ {resp['text']}", fg=PRIVATE)
            sock.close()
            return

        if resp.get("type") == "room_list":
            self.sock = sock
            self.username = username
            self._build_room_screen(resp["rooms"])

    # ─────────────────────────────────────────
    #  ROOM SELECTION SCREEN
    # ─────────────────────────────────────────

    def _build_room_screen(self, rooms):
        self.root.title("CN Chat — Select Room")
        self._center(self.root, 460, 420)

        for w in self.root.winfo_children():
            w.destroy()

        self.rooms_data = rooms

        frame = tk.Frame(self.root, bg=BG)
        frame.pack(expand=True, fill="both", padx=30, pady=20)

        self._label(frame, f"Welcome, {self.username}", 14, ACCENT, bold=True).pack(pady=(0, 4))
        self._label(frame, "Select a room to join:", 10, TXT_DIM).pack(pady=(0, 12))

        list_frame = tk.Frame(frame, bg=BG3, highlightbackground=BORDER, highlightthickness=1)
        list_frame.pack(fill="both", expand=True, pady=(0, 12))

        scrollbar = tk.Scrollbar(list_frame, bg=BG3)
        scrollbar.pack(side="right", fill="y")

        self.room_listbox = tk.Listbox(
            list_frame,
            bg=BG3, fg=TXT, selectbackground=ACCENT, selectforeground=BG,
            font=("Consolas", 11), relief="flat", bd=0,
            yscrollcommand=scrollbar.set, activestyle="none",
            highlightthickness=0
        )
        self.room_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        scrollbar.config(command=self.room_listbox.yview)

        for r in rooms:
            lock = "🔒" if r["type"] == "private" else "🌐"
            label = f"  {lock}  {r['name']}   ({r['members']} online)"
            self.room_listbox.insert(tk.END, label)

        self.room_status = tk.Label(frame, text="", bg=BG, fg=PRIVATE,
                                    font=("Consolas", 9))
        self.room_status.pack()

        btn = self._styled_button(frame, "  JOIN ROOM  ", self._do_join_room,
                                  bg=SEND_BG, fg="white", font=("Consolas", 11, "bold"))
        btn.pack(pady=(6, 0))
        self.room_listbox.bind("<Double-Button-1>", lambda e: self._do_join_room())

    def _do_join_room(self):
        sel = self.room_listbox.curselection()
        if not sel:
            self.room_status.config(text="⚠ Please select a room.")
            return

        idx = sel[0]
        room = self.rooms_data[idx]
        room_name = room["name"]
        password = ""

        if room["type"] == "private":
            password = simpledialog.askstring(
                "Private Room",
                f"Enter password for '{room_name}':",
                show="*", parent=self.root
            )
            if password is None:
                return

        send_msg(self.sock, {"type": "join_room", "room": room_name, "password": password})
        resp = recv_msg(self.sock)

        if resp is None:
            self.room_status.config(text="✖ Server disconnected.")
            return
        if resp.get("type") == "error":
            self.room_status.config(text=f"✖ {resp['text']}")
            return

        if resp.get("type") == "join_ok":
            self.current_room = room_name
            files = resp.get("files", [])
            history = resp.get("history", [])
            users = resp.get("users", [])
            self._build_chat_screen(files, history, users)

    def _update_user_list(self, users):
        self.user_listbox.delete(0, tk.END)
        for u in users:
            label = f"🟢 {u}" if u != self.username else f"⭐ {u} (You)"
            self.user_listbox.insert(tk.END, label)

    # ─────────────────────────────────────────
    #  CHAT SCREEN
    # ─────────────────────────────────────────

    def _build_chat_screen(self, initial_files, history, users):
        self.root.title(f"CN Chat — {self.current_room}  [{self.username}]")
        self._center(self.root, 900, 640)
        self.root.resizable(True, True)
        self.root.minsize(700, 480)

        for w in self.root.winfo_children():
            w.destroy()

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True)

        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        hdr = tk.Frame(left, bg=BG2, pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f" 💬  {self.current_room}", bg=BG2, fg=ACCENT,
                 font=("Consolas", 13, "bold")).pack(side="left", padx=12)
        tk.Label(hdr, text=f"  @{self.username}", bg=BG2, fg=TXT_DIM,
                 font=("Consolas", 10)).pack(side="right", padx=12)

        self.chat_area = scrolledtext.ScrolledText(
            left, bg=BG, fg=TXT, font=("Consolas", 10),
            relief="flat", state="disabled", wrap="word",
            padx=12, pady=8
        )
        self.chat_area.pack(fill="both", expand=True)

        self.chat_area.tag_config("system",  foreground=SYS_CLR, font=("Consolas", 9, "italic"))
        self.chat_area.tag_config("private", foreground=PRIVATE, font=("Consolas", 10, "bold"))
        self.chat_area.tag_config("self",    foreground=ACCENT2)
        self.chat_area.tag_config("other",   foreground=ACCENT)
        self.chat_area.tag_config("ts",      foreground=TXT_DIM, font=("Consolas", 8))
        self.chat_area.tag_config("text",    foreground=TXT)
        self.chat_area.tag_config("progress",foreground="#e3b341", font=("Consolas", 9))

        inp_frame = tk.Frame(left, bg=BG2, pady=8, padx=10)
        inp_frame.pack(fill="x")

        self.msg_entry = tk.Text(
            inp_frame, height=2,
            bg=ENTRY_BG, fg=TXT, insertbackground=ACCENT,
            font=("Consolas", 11), relief="flat",
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, wrap="word"
        )
        self.msg_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.msg_entry.bind("<Return>", self._on_return)
        self.msg_entry.bind("<Shift-Return>", lambda e: None)

        btn_frame = tk.Frame(inp_frame, bg=BG2)
        btn_frame.pack(side="right")
        self._styled_button(btn_frame, "😊", self._show_emoji_picker,
                            font=("Segoe UI Emoji", 14)).pack(pady=(0, 4))
        self._styled_button(btn_frame, "SEND", self._send_message,
                            bg=SEND_BG, fg="white",
                            font=("Consolas", 10, "bold")).pack()

        right = tk.Frame(main, bg=BG2, width=200)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="👥 Online Users", bg=BG2, fg=ACCENT,
                 font=("Consolas", 11, "bold")).pack(pady=(10, 4), padx=10, anchor="w")

        self.user_listbox = tk.Listbox(
            right, bg=BG3, fg=TXT,
            selectbackground=ACCENT,
            font=("Consolas", 9),
            relief="flat", bd=0,
            highlightthickness=0
        )
        self.user_listbox.pack(fill="x", padx=8, pady=(0, 6))

        tk.Label(right, text="📁 Shared Files", bg=BG2, fg=ACCENT,
                 font=("Consolas", 11, "bold")).pack(pady=(12, 4), padx=10, anchor="w")

        sep = tk.Frame(right, bg=BORDER, height=1)
        sep.pack(fill="x", padx=10, pady=(0, 6))

        self.file_listbox = tk.Listbox(
            right, bg=BG3, fg=TXT, selectbackground=ACCENT, selectforeground=BG,
            font=("Consolas", 9), relief="flat", bd=0,
            highlightthickness=0, activestyle="none"
        )
        self.file_listbox.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        self._styled_button(right, "⬆  Upload File", self._upload_file,
                            font=("Consolas", 9)).pack(fill="x", padx=8, pady=2)
        self._styled_button(right, "⬇  Download", self._download_file,
                            bg=SEND_BG, fg="white",
                            font=("Consolas", 9)).pack(fill="x", padx=8, pady=(2, 4))

        sep2 = tk.Frame(right, bg=BORDER, height=1)
        sep2.pack(fill="x", padx=10, pady=4)

        self._styled_button(right, "🚪  Switch Room", self._switch_room,
                            font=("Consolas", 9)).pack(fill="x", padx=8, pady=2)

        tk.Label(right, text="Tip: /msg user text\nfor private message",
                 bg=BG2, fg=TXT_DIM, font=("Consolas", 8),
                 justify="left").pack(padx=10, pady=8, anchor="w")

        self._update_file_list(initial_files)
        self._update_user_list(users)
        for line in history:
            self._append_system(line.strip())

        # ── Start the single receiver thread ─────────────────────────────────
        # This thread is the SOLE reader of self.sock for the entire session.
        # It handles both JSON control messages AND raw file byte streams.
        # No other thread or method ever calls sock.recv() after this point.
        self.running = True
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()

        self._append_system(f"Joined '{self.current_room}'. Say hello! 👋")

    # ─────────────────────────────────────────
    #  CHAT HELPERS
    # ─────────────────────────────────────────

    def _append_system(self, text):
        self.chat_area.config(state="normal")
        self.chat_area.insert(tk.END, f"  {text}\n", "system")
        self.chat_area.config(state="disabled")
        self.chat_area.see(tk.END)

    def _append_chat(self, sender, text, ts, is_self=False, is_private=False):
        self.chat_area.config(state="normal")
        tag = "self" if is_self else "other"
        if is_private:
            self.chat_area.insert(tk.END, f"  [{ts}] ", "ts")
            dm_label = f"[DM] {sender}: " if not is_self else f"[DM → {sender}]: "
            self.chat_area.insert(tk.END, dm_label, "private")
            self.chat_area.insert(tk.END, f"{text}\n", "private")
        else:
            self.chat_area.insert(tk.END, f"  [{ts}] ", "ts")
            self.chat_area.insert(tk.END, f"{sender}: ", tag)
            self.chat_area.insert(tk.END, f"{text}\n", "text")
        self.chat_area.config(state="disabled")
        self.chat_area.see(tk.END)

    def _update_file_list(self, files):
        self.file_listbox.delete(0, tk.END)
        for f in files:
            self.file_listbox.insert(tk.END, f"  📄 {f}")

    def _on_return(self, event):
        if not event.state & 0x1:
            self._send_message()
            return "break"

    # ─────────────────────────────────────────
    #  ACTIONS
    # ─────────────────────────────────────────

    def _send_message(self):
        text = self.msg_entry.get("1.0", tk.END).strip()
        if not text:
            return
        self.msg_entry.delete("1.0", tk.END)
        # Acquire _send_lock so a concurrent upload thread can't interleave
        # its raw bytes with this JSON frame on the wire.
        with self._send_lock:
            if not send_msg(self.sock, {"type": "chat", "text": text}):
                self._append_system("Failed to send message.")

    def _upload_file(self):
        # Guard: only one upload at a time, checked on the main thread.
        if self._uploading:
            self._append_system("⚠ An upload is already in progress. Please wait.")
            return

        path = filedialog.askopenfilename(title="Select file to upload")
        if not path:
            return
        filename = os.path.basename(path)

        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Cannot read file:\n{e}")
            return

        # Send the JSON header from the main thread before handing off.
        # The upload thread will immediately follow with raw bytes, so both
        # must be wrapped in _send_lock to stay atomic on the wire.
        with self._send_lock:
            ok = send_msg(self.sock, {
                "type": "file_upload",
                "filename": filename,
                "filesize": len(data)
            })
        if not ok:
            self._append_system("✖ Failed to send upload header.")
            return

        self._uploading = True
        self._append_system(f"⬆ Uploading '{filename}' ({len(data):,} bytes)…")

        # Spin up a dedicated thread so sock.sendall() chunks never block
        # the Tkinter event loop. The main thread stays fully responsive:
        # the user can still type, read messages, and see progress ticks.
        t = threading.Thread(
            target=self._upload_worker,
            args=(data, filename),
            daemon=True
        )
        t.start()

    def _upload_worker(self, data, filename):
        """
        Runs on a background thread. Sends raw file bytes in chunks and
        reports progress back to the UI via root.after().

        WHY A LOCK HERE
        ───────────────
        Writes to a TCP socket are not atomic: if two threads call
        sock.sendall() at the same moment their byte sequences get
        interleaved on the wire and the server's parser breaks.
        _send_lock serialises every write — the upload chunks, chat
        messages, and download requests — so bytes from different
        callers never mix.

        WHY NOT sendall(data) IN ONE CALL
        ──────────────────────────────────
        sendall() on a large buffer (e.g. 200 MB) can block the calling
        thread for seconds while the kernel drains its TCP send buffer.
        By sending in CHUNK_SIZE pieces we yield the lock frequently,
        giving _send_message() a chance to slip a tiny JSON frame through
        between chunks. This keeps chat latency low during big uploads.
        """
        CHUNK_SIZE = 65536   # 64 KB — large enough for throughput, small
                             # enough to release the lock often
        total = len(data)
        sent = 0
        last_pct = -1

        try:
            while sent < total:
                chunk = data[sent : sent + CHUNK_SIZE]
                with self._send_lock:
                    self.sock.sendall(chunk)
                sent += len(chunk)

                pct = int(sent / total * 100)
                if pct // 10 != last_pct // 10:
                    last_pct = pct
                    self.root.after(
                        0, self._append_system,
                        f"  ↳ {filename}: {pct}%  ({sent:,}/{total:,} bytes)"
                    )

            self.root.after(0, self._append_system,
                            f"✅ Upload complete: '{filename}'")

        except Exception as e:
            self.root.after(0, self._append_system,
                            f"✖ Upload failed: {e}")

        finally:
            # Always clear the flag on the main thread to avoid a race
            # where the main thread reads _uploading before this write lands.
            self.root.after(0, self._clear_uploading)

    def _clear_uploading(self):
        """Called on the main thread by root.after() when upload finishes."""
        self._uploading = False

    def _download_file(self):
        sel = self.file_listbox.curselection()
        if not sel:
            messagebox.showinfo("Download", "Please select a file to download.")
            return
        raw = self.file_listbox.get(sel[0]).strip()
        filename = raw.replace("📄 ", "").strip()

        # Just send the request. The actual bytes arrive in _recv_loop
        # via a "file_data" JSON header, then raw bytes.
        # _recv_loop drains all of it — no second thread touches the socket.
        with self._send_lock:
            send_msg(self.sock, {"type": "file_download", "filename": filename})

    def _show_emoji_picker(self):
        popup = tk.Toplevel(self.root)
        popup.title("Emoji")
        popup.configure(bg=BG2)
        popup.resizable(False, False)

        cols = 5
        for i, em in enumerate(EMOJIS):
            r, c = divmod(i, cols)
            btn = tk.Button(
                popup, text=em, font=("Segoe UI Emoji", 16),
                bg=BG2, fg=TXT, relief="flat", cursor="hand2",
                activebackground=BG3, bd=0, padx=4, pady=4,
                command=lambda e=em: (self.msg_entry.insert(tk.INSERT, e), popup.destroy())
            )
            btn.grid(row=r, column=c, padx=2, pady=2)

    def _switch_room(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass
        self._reconnect_and_room()

    def _reconnect_and_room(self):
        ip = DEFAULT_SERVER_IP
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, PORT))
            sock.settimeout(None)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot reconnect:\n{e}")
            self._build_login_screen()
            return

        send_msg(sock, {"type": "login", "username": self.username})
        resp = recv_msg(sock)
        if resp and resp.get("type") == "room_list":
            self.sock = sock
            self._build_room_screen(resp["rooms"])
        else:
            messagebox.showerror("Error", "Could not fetch room list.")
            sock.close()
            self._build_login_screen()

    # ─────────────────────────────────────────
    #  RECEIVER LOOP  ← THE CORE FIX
    # ─────────────────────────────────────────

    def _recv_loop(self):
        """
        Single thread that owns ALL reads from self.sock.

        WHY THIS FIXES THE FREEZE
        ─────────────────────────
        The old code spawned _download_file_worker in a separate thread,
        which called sock.recv() concurrently with this loop. Two threads
        reading the same socket races: bytes destined for the JSON parser
        get eaten by the download thread and vice versa, causing both to
        stall indefinitely waiting for data that already arrived in the
        wrong reader.

        THE FIX
        ───────
        When we receive a "file_data" JSON header, we do NOT hand off socket
        reading to another thread. Instead, we drain all the raw file bytes
        right here, in this loop, before reading the next JSON message.
        The UI stays responsive because all Tkinter updates go through
        root.after(), which schedules them on the main thread — this
        background thread never touches any widget directly.

        THREAD SAFETY SUMMARY
        ─────────────────────
        • Only this thread reads from self.sock          → no lock needed for reads
        • send_msg() / sock.sendall() are called from
          the main (Tkinter) thread only                 → writes are serialised by GIL
          (If you ever need concurrent writes, wrap them with a threading.Lock)
        • All widget mutations go via root.after()       → Tkinter remains single-threaded
        """
        while self.running:
            msg = recv_msg(self.sock)   # blocks until next JSON header arrives
            if msg is None:
                # Socket closed or broken
                if self.running:
                    self.root.after(0, self._on_disconnect)
                break

            mtype = msg.get("type")

            if mtype == "file_data":
                # ── Inline file drain ─────────────────────────────────────
                # We stay here, in _recv_loop, reading raw bytes.
                # While we're doing this no JSON messages can arrive anyway —
                # the server is busy streaming bytes, not sending new JSON.
                # So blocking here is correct and safe.
                self._drain_file_inline(msg["filename"], msg["filesize"])
                # After _drain_file_inline returns, the socket stream is back
                # to the normal JSON-message protocol and the loop continues.
            else:
                # Dispatch all other message types to the Tkinter main thread.
                # root.after(0, fn, arg) queues fn(arg) to run on the next
                # Tkinter event-loop iteration — safe and non-blocking.
                self.root.after(0, self._handle_server_msg, msg)

    def _drain_file_inline(self, filename, filesize):
        """
        Read exactly `filesize` raw bytes from the socket and write to disk.
        Called from _recv_loop, so we are already on the receiver thread —
        no additional thread is needed, and no other thread touches the socket.

        Progress updates are sent to the UI via root.after(), which is safe
        to call from any thread.
        """
        save_path = os.path.join(DOWNLOAD_DIR, filename)
        received = 0
        last_pct = -1

        self.root.after(0, self._append_system,
                        f"⬇ Downloading '{filename}' ({filesize:,} bytes)…")

        try:
            with open(save_path, "wb") as f:
                while received < filesize:
                    # Read at most 65 536 bytes at a time (larger chunks =
                    # fewer iterations = less overhead without starving anything,
                    # since no other recv is competing here).
                    want = min(65536, filesize - received)
                    chunk = _recv_exact(self.sock, want)
                    if chunk is None:
                        raise ConnectionError("Connection lost during download.")
                    f.write(chunk)
                    received += len(chunk)

                    # Report progress every 10 percentage points.
                    # root.after is thread-safe; it queues the call for the
                    # Tkinter main thread and returns immediately.
                    pct = int(received / filesize * 100)
                    if pct // 10 != last_pct // 10:
                        last_pct = pct
                        self.root.after(
                            0, self._append_system,
                            f"  ↳ {filename}: {pct}%  ({received:,}/{filesize:,} bytes)"
                        )

            self.root.after(0, self._append_system,
                            f"✅ Download complete → {save_path}")

        except Exception as e:
            self.root.after(0, self._append_system,
                            f"✖ Download failed: {e}")

    # ─────────────────────────────────────────
    #  MESSAGE DISPATCHER
    # ─────────────────────────────────────────

    def _handle_server_msg(self, msg):
        """Runs on the Tkinter main thread via root.after(). Safe to touch widgets."""
        mtype = msg.get("type")

        if mtype == "chat":
            self._append_chat(msg["from"], msg["text"], msg["timestamp"])

        elif mtype == "private":
            is_self = msg.get("self", False)
            self._append_chat(msg["from"], msg["text"], msg["timestamp"],
                              is_self=is_self, is_private=True)

        elif mtype == "system":
            self._append_system(msg["text"])

        elif mtype == "user_update":
            self._update_user_list(msg["users"])

        elif mtype == "error":
            self._append_system(f"⚠ {msg['text']}")

        elif mtype == "file_notify":
            self._update_file_list(msg.get("files", []))
            self._append_system(
                f"📤 {msg['uploader']} uploaded '{msg['filename']}' [{msg['timestamp']}]"
            )

        elif mtype == "file_list":
            self._update_file_list(msg.get("files", []))

        # NOTE: "file_data" is intentionally absent here.
        # It is handled directly in _recv_loop before reaching this dispatcher,
        # because it requires socket reads that must stay on the receiver thread.

    def _on_disconnect(self):
        self.running = False
        messagebox.showerror("Disconnected", "Connection to server lost.")
        self._build_login_screen()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    ChatApp()