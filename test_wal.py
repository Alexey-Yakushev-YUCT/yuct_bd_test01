# -*- coding: utf-8 -*-
import os
from segmented_db import YuctSegment, generate_yuct_key_monotonic

def test_wal():
    # Удаляем старые файлы
    for f in ['test_wal.db', 'test_wal.db.wal']:
        if os.path.exists(f):
            os.remove(f)

    print("=== Создаём сегмент с WAL (auto_recover=False) ===")
    seg = YuctSegment('test_wal.db', capacity=100, record_size=80,
                      use_wal=True, auto_recover=False)

    print("Вставляем 5 записей...")
    for seq in range(1, 6):
        ok = seg.insert(seq, f"Data_{seq}".encode('utf-8'))
        print(f"  insert seq={seq}, result={ok}")

    print("Проверка чтения после вставки:")
    for seq in range(1, 6):
        key = generate_yuct_key_monotonic(seq)
        data = seg.get(key)
        print(f"  seq={seq}, data={data}")

    wal_size = os.path.getsize('test_wal.db.wal') if os.path.exists('test_wal.db.wal') else 0
    print(f"Размер WAL-файла после вставки: {wal_size} байт")

    print("Закрываем сегмент (имитация сбоя)...")
    seg.close()

    print("\n=== Создаём новый сегмент с авто-восстановлением ===")
    seg2 = YuctSegment('test_wal.db', capacity=100, record_size=80,
                       use_wal=True, auto_recover=True)

    print("Чтение после восстановления:")
    for seq in range(1, 6):
        key = generate_yuct_key_monotonic(seq)
        data = seg2.get(key)
        print(f"  seq={seq}, data={data}")

    seg2.close()

if __name__ == "__main__":
    test_wal()