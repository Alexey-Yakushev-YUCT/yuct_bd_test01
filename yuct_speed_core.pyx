# distutils: language=c++
# cython: language_level=3

def fast_integer_cuberoot_newton(n):
    if n <= 0: return 0
    b = n.bit_length()
    x = 1 << ((b + 2) // 3)
    while True:
        x2 = x * x
        x_next = (2 * x + n // x2) // 3
        if abs(x_next - x) <= 1: 
            if x_next * x_next * x_next <= n:
                return x_next
            else:
                return x_next - 1
        x = x_next

def fast_generate_yuct_key_monotonic(seq):
    BASE = 10**102
    if seq <= 1: return BASE
    C1 = 10**80
    C2 = int(0.4 * 10**70)
    C3 = int(1.5 * 10**60)
    n_pow_2_3 = fast_integer_cuberoot_newton(seq) ** 2
    ln_approx = (seq.bit_length() - 1) * 45426 >> 16
    return BASE + C1 * seq + (C2 * n_pow_2_3) // 10**10 + (C3 * ln_approx) // 10**5
