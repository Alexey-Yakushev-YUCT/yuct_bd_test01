import time
import math
from segmented_db import generate_yuct_key_monotonic as python_keygen
from yuct_speed_core import fast_generate_yuct_key_monotonic as cpp_keygen

N = 50000
print(f"=== ЗАПУСК СРАВНИТЕЛЬНОГО ТЕСТА ЯДРА YUCT ({N} КЛЮЧЕЙ) ===")

# 1. Тест старого Python-ядра
checksum_py = 0
t0 = time.perf_counter_ns()
for seq in range(1, N + 1):
    checksum_py += python_keygen(seq)
t1 = time.perf_counter_ns()
py_total_ms = (t1 - t0) / 1_000_000
py_avg_ns = (t1 - t0) / N
print(f"[Python] Всего времени: {py_total_ms:.2f} мс | Средняя задержка: {py_avg_ns:.0f} нс")

# 2. Тест скомпилированного С++ ядра
checksum_cpp = 0
t2 = time.perf_counter_ns()
for seq in range(1, N + 1):
    checksum_cpp += cpp_keygen(seq)
t3 = time.perf_counter_ns()
cpp_total_ms = (t3 - t2) / 1_000_000
cpp_avg_ns = (t3 - t2) / N
print(f"[C++ Core] Всего времени: {cpp_total_ms:.2f} мс | Средняя задержка: {cpp_avg_ns:.0f} нс")

# Проверка валидности
assert checksum_py == checksum_cpp, "Ошибка: Хэш-координаты не совпадают!"
acceleration = py_avg_ns / cpp_avg_ns
print("-" * 50)
print(f"УСКОРЕНИЕ ВЫЧИСЛЕНИЙ ЯДРА: В {acceleration:.1f} РАЗ(А)!")
print(f"Контрольный лок: {str(checksum_cpp)[:30]}...")
