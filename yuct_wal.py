# -*- coding: utf-8 -*-
import os
import struct

class YuctWAL:
    """
    Упрощённый журнал предзаписи: хранит seq, data, контрольную сумму.
    Ключ вычисляется из seq при восстановлении.
    """
    MAGIC = b'YUCTWAL'
    VERSION = 1

    def __init__(self, wal_filename: str, segment):
        self.wal_filename = wal_filename
        self.segment = segment
        self.fd = None
        self._open()

    def _open(self):
        self.fd = open(self.wal_filename, 'a+b')
        if os.path.getsize(self.wal_filename) == 0:
            self.fd.write(self.MAGIC)
            self.fd.write(struct.pack('>I', self.VERSION))
            self.fd.flush()

    def append(self, seq: int, data: bytes) -> bool:
        """Записывает seq и data в WAL."""
        try:
            data_len = len(data)
            checksum = self._calc_checksum(seq, data)
            self.fd.write(struct.pack('>Q', seq))
            self.fd.write(struct.pack('>I', data_len))
            self.fd.write(data)
            self.fd.write(struct.pack('>Q', checksum))
            self.fd.flush()
            return True
        except Exception:
            return False

    def _calc_checksum(self, seq: int, data: bytes) -> int:
        checksum = seq
        for b in data:
            checksum ^= b
        return checksum

    def replay(self) -> int:
        """Восстанавливает записи из WAL в сегмент."""
        self.fd.seek(0)
        magic = self.fd.read(8)
        if magic != self.MAGIC:
            return 0
        ver_bytes = self.fd.read(4)
        if len(ver_bytes) < 4:
            return 0
        version = struct.unpack('>I', ver_bytes)[0]
        if version != self.VERSION:
            return 0

        recovered = 0
        while True:
            header = self.fd.read(8 + 4)  # seq + data_len
            if len(header) < 8 + 4:
                break
            seq = struct.unpack('>Q', header[0:8])[0]
            data_len = struct.unpack('>I', header[8:12])[0]
            data = self.fd.read(data_len)
            if len(data) < data_len:
                break
            checksum_bytes = self.fd.read(8)
            if len(checksum_bytes) < 8:
                break
            stored_checksum = struct.unpack('>Q', checksum_bytes)[0]
            calc_checksum = self._calc_checksum(seq, data)

            if calc_checksum != stored_checksum:
                continue

            # Проверяем, есть ли уже такая запись (по seq)
            key = self.segment._generate_key(seq)
            existing = self.segment.get(key)
            if existing is None:
                self.segment._insert_direct(seq, data)
                recovered += 1
        return recovered

    def truncate(self):
        self.fd.close()
        open(self.wal_filename, 'wb').close()
        self._open()

    def close(self):
        if self.fd:
            self.fd.close()