# -*- coding: utf-8 -*-
"""
segmented_db.py — сегментированное хранилище с поддержкой WAL
Версия: полная (интеграция с yuct_wal)
"""
import os
import mmap
import struct
import threading
from typing import Optional
from yuct_wal import YuctWAL

# --- Целочисленный монотонный генератор YUCT-ключа ---
def integer_cuberoot_newton(y: int) -> int:
    if y == 0:
        return 0
    b = y.bit_length()
    x = 1 << ((b + 2) // 3)
    while True:
        x2 = x * x
        x_next = (2 * x + y // x2) // 3
        if x_next >= x:
            if x_next * x_next * x_next <= y:
                return x_next
            else:
                return x
        x = x_next

def generate_yuct_key_monotonic(seq: int) -> int:
    BASE = 10**102
    if seq <= 1:
        return BASE
    C1 = 10**80
    C2 = int(0.4 * 10**70)
    C3 = int(1.5 * 10**60)
    n_pow_2_3 = integer_cuberoot_newton(seq) ** 2
    ln_approx = (seq.bit_length() - 1) * 45426 >> 16
    return BASE + C1 * seq + (C2 * n_pow_2_3) // 10**10 + (C3 * ln_approx) // 10**5

# --- Одиночный сегмент с поддержкой WAL ---
class YuctSegment:
    HEADER_SIZE = 48  # для хранения 103-значного ключа

    def __init__(self, filename: str, capacity: int,
                 record_size: int = 80, use_wal: bool = True,
                 auto_recover: bool = True):
        self.capacity = capacity
        self.record_size = record_size + self.HEADER_SIZE
        self.file_size = self.capacity * self.record_size
        self.lock = threading.Lock()
        self.use_wal = use_wal

        # Создаём файл, если его нет
        if not os.path.exists(filename):
            with open(filename, 'wb') as f:
                f.truncate(self.file_size)
        self.fd = open(filename, 'r+b')
        self.mmap = mmap.mmap(self.fd.fileno(), 0)

        # Инициализация WAL
        self.wal = None
        if self.use_wal:
            wal_filename = filename + '.wal'
            self.wal = YuctWAL(wal_filename, self)
            if auto_recover and os.path.getsize(wal_filename) > 8:
                recovered = self.wal.replay()
                if recovered > 0:
                    self.wal.truncate()

    def _hash(self, key: int) -> int:
        key ^= key >> 33
        key *= 0xff51afd7ed558ccd
        key ^= key >> 33
        return key % self.capacity

    def _generate_key(self, seq: int) -> int:
        return generate_yuct_key_monotonic(seq)

    def insert(self, seq: int, data: bytes) -> bool:
        key = self._generate_key(seq)

        # Шаг 1: запись в WAL (если включён)
        if self.use_wal and self.wal:
            if not self.wal.append(seq, data):
                return False

        # Шаг 2: запись в mmap (с блокировкой)
        with self.lock:
            home = self._hash(key)
            for i in range(self.capacity):
                slot = (home + i) % self.capacity
                addr = slot * self.record_size
                header = self.mmap[addr:addr + self.HEADER_SIZE]
                header_key = int.from_bytes(header, byteorder='big')
                if header_key == 0 or header_key == key:
                    self.mmap[addr:addr + self.HEADER_SIZE] = key.to_bytes(self.HEADER_SIZE, byteorder='big')
                    padded = data.ljust(self.record_size - self.HEADER_SIZE, b'\0')
                    self.mmap[addr + self.HEADER_SIZE:addr + self.record_size] = padded
                    return True
            return False

    def _insert_direct(self, seq: int, data: bytes) -> bool:
        """Прямая вставка в mmap без WAL (используется только для восстановления)."""
        key = self._generate_key(seq)
        with self.lock:
            home = self._hash(key)
            for i in range(self.capacity):
                slot = (home + i) % self.capacity
                addr = slot * self.record_size
                header = self.mmap[addr:addr + self.HEADER_SIZE]
                header_key = int.from_bytes(header, byteorder='big')
                if header_key == 0 or header_key == key:
                    self.mmap[addr:addr + self.HEADER_SIZE] = key.to_bytes(self.HEADER_SIZE, byteorder='big')
                    padded = data.ljust(self.record_size - self.HEADER_SIZE, b'\0')
                    self.mmap[addr + self.HEADER_SIZE:addr + self.record_size] = padded
                    return True
            return False

    def get(self, key: int) -> Optional[bytes]:
        home = self._hash(key)
        for i in range(self.capacity):
            slot = (home + i) % self.capacity
            addr = slot * self.record_size
            header = self.mmap[addr:addr + self.HEADER_SIZE]
            header_key = int.from_bytes(header, byteorder='big')
            if header_key == key:
                return self.mmap[addr + self.HEADER_SIZE:addr + self.record_size].rstrip(b'\0')
            if header_key == 0:
                return None
        return None

    def close(self):
        if self.wal:
            self.wal.close()
        self.mmap.close()
        self.fd.close()

# --- Сегментированное хранилище (несколько сегментов) ---
class YuctSegmentedDB:
    def __init__(self, base_filename: str, segment_capacity: int,
                 num_segments: int, record_size: int = 80,
                 use_wal: bool = True, auto_recover: bool = True):
        self.segment_capacity = segment_capacity
        self.num_segments = num_segments
        self.segments = []
        for i in range(num_segments):
            fname = f"{base_filename}_seg{i}.db"
            seg = YuctSegment(fname, segment_capacity, record_size,
                              use_wal=use_wal, auto_recover=auto_recover)
            self.segments.append(seg)

    def _get_segment(self, seq: int) -> int:
        return seq // self.segment_capacity

    def insert(self, seq: int, data: bytes) -> bool:
        seg_idx = self._get_segment(seq)
        if seg_idx >= self.num_segments:
            return False
        return self.segments[seg_idx].insert(seq, data)

    def get_by_key(self, key: int) -> Optional[bytes]:
        for seg in self.segments:
            result = seg.get(key)
            if result is not None:
                return result
        return None

    def close(self):
        for seg in self.segments:
            seg.close()