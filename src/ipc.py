"""
K-Trader Master - IPC(Inter-Process Communication) 모듈
UI(서버)와 엔진(클라이언트) 간의 고속 소켓 통신을 담당합니다.
"""
import socket
import json
import time
import logging
from PyQt5.QtCore import QThread, pyqtSignal

logger = logging.getLogger("ktrader")


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

    # [Fix #6] 버퍼 최대 크기 상수: 포트폴리오 JSON이 64KB를 초과하더라도
    #          버퍼가 무한히 커지지 않도록 10MB를 상한으로 설정.
    _MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10 MB

    def _handle_client(self, conn):
        buffer = ""
        while self.running:
            try:
                data = conn.recv(65536).decode('utf-8')
                if not data:
                    break  # 연결 종료
                buffer += data

                # [Fix #6] 버퍼가 상한을 넘으면 개행 기준으로 잘라낼 수 없는 부분을 버림
                if len(buffer) > self._MAX_BUFFER_SIZE:
                    last_newline = buffer.rfind('\n')
                    if last_newline != -1:
                        buffer = buffer[last_newline + 1:]
                    else:
                        buffer = ""  # 개행 없이 10MB 초과 → 전체 버림
                    logger.warning("⚠️ [IPC] 수신 버퍼가 상한을 초과하여 일부를 폐기했습니다.")

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

                    # [Fix #6] 클라이언트 수신 버퍼도 상한 적용 (명령은 짧으므로 1MB로 충분)
                    if len(buffer) > 1024 * 1024:
                        last_newline = buffer.rfind('\n')
                        buffer = buffer[last_newline + 1:] if last_newline != -1 else ""

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