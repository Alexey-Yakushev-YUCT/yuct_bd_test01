# -*- coding: utf-8 -*-
"""
YAKUSHEV UNIFIED COORDINATION THEORY (YUCT) — UNIVERSAL API GATEWAY
File: yuct_universal_gateway.py
Version: 2.2 (Fixed set_by_hash with modulo)
[Verified by YUCT Coordination Framework] | DOI: 10.5281/zenodo.18444598
"""
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import os
import sys
import hashlib

try:
    from segmented_db import YuctSegmentedDB, generate_yuct_key_monotonic
except ImportError:
    sys.path.append('.')
    from segmented_db import YuctSegmentedDB, generate_yuct_key_monotonic

# =============================================================================
# Глобальная конфигурация
# =============================================================================
DATA_DIR = "yuct_data"
RECORD_SIZE = 256
SEGMENT_CAPACITY = 100000
NUM_SEGMENTS = 8
USE_WAL = True

os.makedirs(DATA_DIR, exist_ok=True)

base_filename = os.path.join(DATA_DIR, "yuct_seg")
db = YuctSegmentedDB(
    base_filename=base_filename,
    segment_capacity=SEGMENT_CAPACITY,
    num_segments=NUM_SEGMENTS,
    record_size=RECORD_SIZE,
    use_wal=USE_WAL,
    auto_recover=True
)

# Общее количество слотов для маппинга хеша
TOTAL_SLOTS = SEGMENT_CAPACITY * NUM_SEGMENTS

def seq_to_key(seq: int) -> int:
    return generate_yuct_key_monotonic(seq)

def data_to_seq(data: bytes) -> int:
    """Преобразует данные в seq через хеш, ограничивая диапазон TOTAL_SLOTS."""
    h = hashlib.blake2b(data, digest_size=16).digest()
    hash_int = int.from_bytes(h, 'big')
    return hash_int % TOTAL_SLOTS

# =============================================================================
# HTTP-обработчик (остаётся без изменений)
# =============================================================================

class YuctUniversalHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/health":
            self.send_json({"status": "ok", "storage": "segmented", "use_wal": USE_WAL, "total_slots": TOTAL_SLOTS})

        elif path == "/get":
            if "seq" not in query:
                self.send_json({"status": "error", "message": "Missing 'seq' parameter"}, 400)
                return
            try:
                seq = int(query["seq"][0])
                t0 = time.perf_counter_ns()
                key = seq_to_key(seq)
                data = db.get_by_key(key)
                t1 = time.perf_counter_ns()
                latency = (t1 - t0) / 1000.0
                if data is None:
                    self.send_json({"status": "not_found", "seq": seq, "latency_mks": latency}, 404)
                else:
                    try:
                        decoded = data.decode('utf-8')
                    except UnicodeDecodeError:
                        decoded = data.hex()
                    self.send_json({
                        "status": "ok",
                        "seq": seq,
                        "key": str(key),
                        "data": decoded,
                        "latency_mks": latency
                    })
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)

        elif path == "/get_by_key":
            if "key" not in query:
                self.send_json({"status": "error", "message": "Missing 'key' parameter"}, 400)
                return
            try:
                key = int(query["key"][0])
                t0 = time.perf_counter_ns()
                data = db.get_by_key(key)
                t1 = time.perf_counter_ns()
                latency = (t1 - t0) / 1000.0
                if data is None:
                    self.send_json({"status": "not_found", "key": str(key), "latency_mks": latency}, 404)
                else:
                    try:
                        decoded = data.decode('utf-8')
                    except UnicodeDecodeError:
                        decoded = data.hex()
                    self.send_json({
                        "status": "ok",
                        "key": str(key),
                        "data": decoded,
                        "latency_mks": latency
                    })
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)

        else:
            self.send_json({"status": "error", "message": "Endpoint not found. Use /get, /get_by_key, /set, /set_by_hash, /health"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json({"status": "error", "message": "Invalid JSON"}, 400)
            return

        if path == "/set":
            if "seq" not in payload or "data" not in payload:
                self.send_json({"status": "error", "message": "Missing 'seq' or 'data' in JSON"}, 400)
                return
            try:
                seq = int(payload["seq"])
                data = payload["data"].encode('utf-8')
                key = seq_to_key(seq)
                t0 = time.perf_counter_ns()
                success = db.insert(seq, data)
                t1 = time.perf_counter_ns()
                latency = (t1 - t0) / 1000.0
                if success:
                    self.send_json({"status": "ok", "seq": seq, "key": str(key), "latency_mks": latency})
                else:
                    self.send_json({"status": "error", "message": "Insert failed (maybe storage full)", "latency_mks": latency}, 500)
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)

        elif path == "/set_by_hash":
            if "data" not in payload:
                self.send_json({"status": "error", "message": "Missing 'data' in JSON"}, 400)
                return
            try:
                raw = payload["data"].encode('utf-8')
                seq = data_to_seq(raw)
                key = seq_to_key(seq)
                t0 = time.perf_counter_ns()
                success = db.insert(seq, raw)
                t1 = time.perf_counter_ns()
                latency = (t1 - t0) / 1000.0
                if success:
                    self.send_json({"status": "ok", "seq": seq, "key": str(key), "latency_mks": latency})
                else:
                    self.send_json({"status": "error", "message": "Insert failed (storage full)", "latency_mks": latency}, 500)
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)

        else:
            self.send_json({"status": "error", "message": "Endpoint not found. Use /set or /set_by_hash"}, 404)

def run_server(port=8080):
    server_address = ("", port)
    httpd = HTTPServer(server_address, YuctUniversalHandler)
    print("=" * 85)
    print(f" [ONLINE] YUCT UNIVERSAL API GATEWAY ЗАПУЩЕН НА ПОРТУ {port}")
    print(f" Хранилище: сегментированное, WAL: {USE_WAL}, сегментов: {NUM_SEGMENTS}, слотов: {TOTAL_SLOTS}")
    print(" Доступные эндпоинты:")
    print("   GET  /get?seq=<int>")
    print("   GET  /get_by_key?key=<int>")
    print("   POST /set (JSON: {'seq': int, 'data': '...'})")
    print("   POST /set_by_hash (JSON: {'data': '...'})")
    print("   GET  /health")
    print(" Ожидание запросов... (Ctrl+C для остановки)")
    print("=" * 85)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Шлюз остановлен.")
        httpd.server_close()
        db.close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)