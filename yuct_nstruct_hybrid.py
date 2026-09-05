# -*- coding: utf-8 -*-
"""
yuct_nstruct_hybrid.py — гибридное хранилище (inline + blob) для неструктурированных данных
Версия: исправленная (гарантированный возврат ключа)
"""
import os
import mmap
import struct
import hashlib
from typing import Optional

# Импорт генератора ключей (предполагается, что он определён в yuct_core.py)
try:
    from yuct_core import generate_yuct_key_monotonic
except ImportError:
    from segmented_db import generate_yuct_key_monotonic

def data_to_seq(data: bytes) -> int:
    h = hashlib.blake2b(data, digest_size=16).digest()
    return int.from_bytes(h, 'big')

class YuctNStructDB:
    INLINE_THRESHOLD = 128
    HEADER_SIZE = 1 + 16 + 8 + 8   # occupied + hash_digest + data_len + blob_offset
    SLOT_SIZE = HEADER_SIZE + INLINE_THRESHOLD

    def __init__(self, main_file: str, blob_file: str, capacity: int):
        self.capacity = capacity
        self.main_file = main_file
        self.blob_file = blob_file

        if not os.path.exists(main_file):
            with open(main_file, 'wb') as f:
                f.truncate(capacity * self.SLOT_SIZE)
        self.fd = open(main_file, 'r+b')
        self.mmap = mmap.mmap(self.fd.fileno(), 0)

        self.blob_fd = open(blob_file, 'a+b')
        self.blob_fd.seek(0, os.SEEK_END)
        self.blob_end = self.blob_fd.tell()

    def _hash_key(self, key: int) -> int:
        key ^= key >> 33
        key *= 0xff51afd7ed558ccd
        key ^= key >> 33
        return key % self.capacity

    def _slot_addr(self, idx: int) -> int:
        return idx * self.SLOT_SIZE

    def _read_slot(self, addr: int):
        occupied = self.mmap[addr]
        digest = bytes(self.mmap[addr+1:addr+17])
        data_len = struct.unpack_from('>Q', self.mmap, addr+17)[0]
        blob_offset = struct.unpack_from('>Q', self.mmap, addr+25)[0]
        inline_start = addr + self.HEADER_SIZE
        inline_data = bytes(self.mmap[inline_start:inline_start+self.INLINE_THRESHOLD])
        return occupied, digest, data_len, blob_offset, inline_data

    def _write_slot_header(self, addr: int, occupied: int, digest: bytes, data_len: int, blob_offset: int):
        self.mmap[addr] = occupied
        self.mmap[addr+1:addr+17] = digest
        struct.pack_into('>Q', self.mmap, addr+17, data_len)
        struct.pack_into('>Q', self.mmap, addr+25, blob_offset)

    def _append_to_blob(self, data: bytes) -> int:
        offset = self.blob_end
        self.blob_fd.seek(offset)
        self.blob_fd.write(data)
        self.blob_end += len(data)
        return offset

    def _read_from_blob(self, offset: int, length: int) -> bytes:
        self.blob_fd.seek(offset)
        return self.blob_fd.read(length)

    def insert_data(self, data: bytes, cmd_code: int = 0) -> Optional[int]:
        """
        Вставка произвольных данных. Возвращает 103-значный ключ при успехе.
        Исправленная версия: гарантированный return key во всех ветках.
        """
        seq = data_to_seq(data)
        key = generate_yuct_key_monotonic(seq, cmd_code)
        idx = self._hash_key(key)

        digest = data_to_seq(data).to_bytes(16, 'big')
        data_len = len(data)

        for _ in range(self.capacity):
            addr = self._slot_addr(idx)
            occupied, stored_digest, _, _, _ = self._read_slot(addr)

            if not occupied:
                if data_len <= self.INLINE_THRESHOLD:
                    # ВЕТКА 1: Inline (малые данные)
                    self._write_slot_header(addr, 1, digest, data_len, 0)
                    inline_start = addr + self.HEADER_SIZE
                    self.mmap[inline_start:inline_start+data_len] = data
                    return key   # <-- ИСПРАВЛЕНО: ключ возвращается всегда
                else:
                    # ВЕТКА 2: Blob (большие данные)
                    blob_offset = self._append_to_blob(data)
                    self._write_slot_header(addr, 1, digest, data_len, blob_offset)
                    return key
            else:
                if stored_digest == digest:
                    return key
                idx = (idx + 1) % self.capacity

        return None   # Таблица переполнена

    def retrieve_data(self, data_or_key, is_key=False):
        """
        Поиск данных по содержимому или по ключу.
        Если is_key=True, data_or_key интерпретируется как 103-значный ключ.
        Иначе вычисляется хеш и выполняется поиск.
        """
        if is_key:
            key = int(data_or_key)
            digest = None
        else:
            digest_bytes = data_to_seq(data_or_key).to_bytes(16, 'big')
            key = generate_yuct_key_monotonic(int.from_bytes(digest_bytes, 'big'), 0)
            digest = digest_bytes

        idx = self._hash_key(key)
        for _ in range(self.capacity):
            addr = self._slot_addr(idx)
            occupied, stored_digest, data_len, blob_offset, inline_data = self._read_slot(addr)

            if not occupied:
                return None

            if digest is not None and stored_digest == digest:
                if data_len <= self.INLINE_THRESHOLD:
                    return inline_data[:data_len]
                else:
                    return self._read_from_blob(blob_offset, data_len)
            elif digest is None and occupied:
                # Поиск по ключу: возвращаем данные, даже если ключ найден
                if data_len <= self.INLINE_THRESHOLD:
                    return inline_data[:data_len]
                else:
                    return self._read_from_blob(blob_offset, data_len)

            idx = (idx + 1) % self.capacity

        return None

    def close(self):
        self.mmap.close()
        self.fd.close()
        self.blob_fd.close()