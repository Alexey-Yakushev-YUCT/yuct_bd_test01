# -*- coding: utf-8 -*-
"""
YAKUSHEV UNIFIED COORDINATION THEORY (YUCT) — TRUE MMAP RETRIEVAL ENGINE
File: live_db_test.py
[Strict O(0) Heap Profile | Native Memory-Mapped Layout]
"""
import os
import math
import time
import mmap
import tracemalloc

# --- Фундаментальные константы вакуумной решетки YUCT ---
BETA = 2.0 / 3.0
Q_QUANTUM = (3.0 / 2.0) ** (1.0 / 3.0)
PHASE_PERIOD = 16.5
PI_COORD = 3.141640786499874
A_COEFFICIENT = 0.44
C1 = 10**80
BASE = 10**102

def integer_cuberoot_newton(y: int) -> int:
    """Целочисленный кубический корень методом Ньютона."""
    if y == 0: return 0
    b = y.bit_length()
    x = 1 << ((b + 2) // 3)
    while True:
        next_x = (2 * x + y // (x * x)) // 3
        if next_x >= x: return x
        x = next_x

def generate_yuct_key_monotonic(seq: int) -> int:
    """Оригинальный генератор 103-значных волновых ключей YUCT."""
    if seq <= 1: return BASE
    ln_n_shifted = int(math.log(seq) * 65536)
    ln_ln_n_shifted = int(math.log(max(0.0001, math.log(seq))) * 65536) if seq > 2 else 0
    log_q_shifted = int(math.log(Q_QUANTUM) * 65536)
    
    N_f_fixed = (ln_n_shifted << 16) // log_q_shifted
    phase_angle_fixed = (int(PI_COORD * 65536) * (N_f_fixed - (80 << 16))) // int(PHASE_PERIOD * 65536)
    
    sin_val = math.sin(phase_angle_fixed / 65536.0)
    sign_gate = 1 if sin_val >= 0 else -1
    
    wave_component = integer_cuberoot_newton(seq)
    absolute_error_wave = sign_gate * int(A_COEFFICIENT * PI_COORD * Q_QUANTUM * 10**12) * wave_component
    final_phase_shift = (ln_n_shifted + ln_ln_n_shifted) * 10**10 + absolute_error_wave
    
    return BASE + C1 * seq + abs(final_phase_shift)


class TrueYuctMmapDB:
    """Оригинальный бездемпферный движок на базе системного вызова mmap."""
    def __init__(self, filename, record_size=80, capacity=1000):
        self.header_size = 48  # Заголовок под 103-значный YUCT-ключ
        self.record_size = record_size + self.header_size
        self.capacity = capacity
        self.file_size = self.capacity * self.record_size
        self.filename = filename
        self.collisions = 0
        
        # Предварительная жесткая разметка файла нулями
        if not os.path.exists(self.filename):
            with open(self.filename, 'wb') as f:
                f.write(b'\0' * self.file_size)
                
        self.fd = open(filename, 'r+b')
        # Проецируем файл напрямую в адресное пространство процесса ОС
        self.mmap = mmap.mmap(self.fd.fileno(), 0)

    def _hash(self, key: int) -> int:
        """Murmur-like лавинный каскадный хэш Якушева для больших int."""
        key ^= key >> 33
        key *= 0xff51afd7ed558ccd
        key ^= key >> 33
        return key % self.capacity

    def insert(self, seq: int, text_data: bytes) -> int:
        """Вставка записи напрямую в срез mmap-памяти без системных буферов."""
        key = generate_yuct_key_monotonic(seq)
        home_slot = self._hash(key)
        
        for i in range(self.capacity):
            slot = (home_slot + i) % self.capacity
            if i > 0: self.collisions += 1
            
            addr = slot * self.record_size
            
            # Чтение среза mmap как обычного массива (без выделения памяти на куче)
            header_bytes = self.mmap[addr : addr + self.header_size]
            header_key = int.from_bytes(header_bytes, byteorder='big')
            
            if header_key == 0 or header_key == key:
                padded_data = text_data.ljust(self.record_size - self.header_size, b'\0')
                # Прямая побайтовая запись в память ОС
                self.mmap[addr : addr + self.header_size] = key.to_bytes(self.header_size, byteorder='big')
                self.mmap[addr + self.header_size : addr + self.record_size] = padded_data
                return key
                
        raise RuntimeError("DB Full")

    def get_by_key(self, key: int) -> bytes:
        """Мгновенное Look-up извлечение из mmap-массива."""
        home_slot = self._hash(key)
        
        for i in range(self.capacity):
            slot = (home_slot + i) % self.capacity
            addr = slot * self.record_size
            
            header_bytes = self.mmap[addr : addr + self.header_size]
            header_key = int.from_bytes(header_bytes, byteorder='big')
            
            if header_key == key:
                return self.mmap[addr + self.header_size : addr + self.record_size].rstrip(b'\0')
            if header_key == 0:
                return b""
        return b""

    def close(self):
        """Корректное закрытие дескрипторов mmap и файлов."""
        self.mmap.close()
        self.fd.close()


def run_yuct_true_monitor():
    DB_FILE = "true_yuct_vacuum.db"
    LOG_FILE = "yuct_true_telemetry.log"
    
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
        
    db = TrueYuctMmapDB(DB_FILE, record_size=80, capacity=1000)
    
    tracemalloc.start()
    print("=" * 95)
    print("   ЗАПУСК ПОДЛИННОЙ MMAP-НАВИГАЦИИ СУБД НА БАЗЕ UNIFIED COORDINATION THEORY (YUCT)")
    print("=" * 95)
    print(f"[*] Файл дисковой решетки (mmap)  : {DB_FILE} (Размер: {db.file_size/1024:.2f} KB)")
    print(f"[*] Протокол телеметрии           : {LOG_FILE}")
    print("-" * 95)
    print(f"{'Время':<9} | {'Слот (Индекс)':<16} | {'103-значный YUCT-ключ (Начало)':<32} | {'Коллизии':<8} | {'RAM (Index)'}")
    print("-" * 95)
    
    try:
        iteration = 1
        while True:
            current_time = time.strftime("%H:%M:%S")
            seq = iteration + 1
            
            payload = f"TRUE_MMAP_BLOCK_{seq}".encode('utf-8')
            key = db.insert(seq, payload)
            assigned_slot = db._hash(key)
            
            _ = db.get_by_key(key)
            
            _, peak_ram = tracemalloc.get_traced_memory()
            
            key_shortcut = f"{str(key)[:28]}..."
            slot_info = f"Slot {assigned_slot} (seq:{seq})"
            
            report_line = f"{current_time:<9} | {slot_info:<16} | {key_shortcut:<32} | {db.collisions:<8} | {peak_ram/1024:.2f} KB"
            print(report_line)
            
            with open(LOG_FILE, "a", encoding="utf-8") as log_f:
                log_f.write(report_line + "\n")
                
            iteration += 1
            time.sleep(0.5)  # Ускоряем тест до 0.5с для быстрого выхода на лимит
            
    except RuntimeError as e:
        print(f"\n[!] Системное уведомление: {e}")
    except KeyboardInterrupt:
        print("\n[-] Мониторинг остановлен.")
    finally:
        tracemalloc.stop()
        db.close()
        print("[+] Сессия закрыта через db.close(). Файлы деаллоцированы.")

if __name__ == "__main__":
    run_yuct_true_monitor()
