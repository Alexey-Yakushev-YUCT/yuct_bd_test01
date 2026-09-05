# -*- coding: utf-8 -*-
import time
import multiprocessing
import os
from segmented_db import YuctSegmentedDB

def worker(proc_id, records_per_thread, segment_capacity, num_segments):
    """
    Функция, выполняемая в отдельном процессе.
    Каждый процесс создаёт свою базу данных с уникальным префиксом файлов.
    """
    prefix = f"seg_test_p{proc_id}"
    # Удаляем старые файлы этого процесса (если есть)
    for i in range(num_segments):
        fname = f"{prefix}_seg{i}.db"
        if os.path.exists(fname):
            os.remove(fname)
    
    db = YuctSegmentedDB(prefix, segment_capacity, num_segments, record_size=80)
    
    start_seq = proc_id * records_per_thread
    payload = f"DATA_FROM_PROC_{proc_id}".encode('utf-8')
    for i in range(records_per_thread):
        seq = start_seq + i
        db.insert(seq, payload)
    
    db.close()

def run_test(num_processes, records_per_process, segment_capacity=5000, num_segments=None):
    if num_segments is None:
        num_segments = num_processes  # по одному сегменту на процесс
    
    processes = []
    start_time = time.perf_counter()
    for p in range(num_processes):
        proc = multiprocessing.Process(
            target=worker,
            args=(p, records_per_process, segment_capacity, num_segments)
        )
        processes.append(proc)
        proc.start()
    
    for proc in processes:
        proc.join()
    end_time = time.perf_counter()
    
    total_records = num_processes * records_per_process
    elapsed = end_time - start_time
    throughput = total_records / elapsed
    
    print(f"Процессов: {num_processes}, записей на процесс: {records_per_process}, всего: {total_records}")
    print(f"Время: {elapsed:.2f} сек, пропускная способность: {throughput:.0f} записей/сек")
    
    # Удаляем временные файлы (опционально)
    # for p in range(num_processes):
    #     prefix = f"seg_test_p{p}"
    #     for i in range(num_segments):
    #         fname = f"{prefix}_seg{i}.db"
    #         if os.path.exists(fname):
    #             os.remove(fname)
    return throughput

if __name__ == "__main__":
    # Тестируем 1, 2, 4, 8 процессов
    for procs in [1, 2, 4, 8]:
        run_test(procs, 5000, segment_capacity=5000, num_segments=procs)