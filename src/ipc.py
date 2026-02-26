"""
K-Trader Master - IPC(Inter-Process Communication) 모듈
UI(서버)와 엔진(클라이언트) 간의 고속 소켓 통신을 담당합니다.
"""
import socket
import json
import time
from PyQt5.QtCore import QThread, pyqtSignal


class UI_IPCServer(QThread):
    """UI 대시보드에서 구동되는 TCP 서버. 엔진의 상태를 수신합니다."""
    state_received = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 0을 주면 OS가 남는 포트를 자동 할당합니다.
        self.server_socket.bind(('127.0.0.1', 0))
        self.port = self.server_socket.getsockname()[1]
        self.server_socket.listen(1)
        self.client_conn = None
        self.running = True

    def run(self):
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                conn, addr = self.server_socket.accept()
                self.client_conn = conn
                self._handle_client(conn)
            except socket.timeout:
                continue
            except Exception as e:
                break

    def _handle_client(self, conn):
        buffer = ""
        while self.running:
            try:
                data = conn.recv(65536).decode('utf-8')
                if not data:
                    break  # 연결 종료
                buffer += data
                # NDJSON (Newline Delimited JSON) 파싱
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            self.state_received.emit(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            except Exception:
                break
        self.client_conn = None

    def send_command(self, cmd: str, args: str = ""):
        """UI에서 엔진으로 명령 하달"""
        if self.client_conn:
            msg = json.dumps({"cmd": cmd, "args": args}) + "\n"
            try:
                self.client_conn.sendall(msg.encode('utf-8'))
            except Exception:
                pass

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()


class Engine_IPCClient(QThread):
    """매매 엔진에서 구동되는 TCP 클라이언트. UI로 상태를 전송합니다."""
    command_received = pyqtSignal(str, str)
    
    def __init__(self, port):
        super().__init__()
        self.port = port
        self.sock = None
        self.running = True
        self.last_heartbeat = time.time()

    def run(self):
        while self.running:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect(('127.0.0.1', self.port))
                self.last_heartbeat = time.time()
                
                buffer = ""
                while self.running:
                    data = self.sock.recv(65536).decode('utf-8')
                    if not data:
                        break # 연결 끊김
                    buffer += data
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line.strip():
                            msg = json.loads(line)
                            self.last_heartbeat = time.time()
                            self.command_received.emit(msg.get("cmd", ""), msg.get("args", ""))
            except Exception:
                # 연결 실패 또는 끊김 시 1초 대기 후 재연결 시도
                time.sleep(1)

    def send_state(self, state_dict: dict):
        """엔진에서 UI로 현재 상태(포트폴리오 등) 보고"""
        if self.sock:
            msg = json.dumps(state_dict) + "\n"
            try:
                self.sock.sendall(msg.encode('utf-8'))
            except Exception:
                pass

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()