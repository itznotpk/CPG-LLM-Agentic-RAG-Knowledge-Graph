import numpy as np
import matplotlib.pyplot as plt

def solve_roots(K):
    # Characteristic Equation: (s^2 - 3s + 2) + K(s^2 + 3s + 2) = 0
    # Rearranging: (1+K)s^2 + (3K - 3)s + (2 + 2K) = 0
    a = 1 + K
    b = 3 * K - 3
    c = 2 + 2 * K
    
    # Quadratic formula: (-b +/- sqrt(b^2 - 4ac)) / 2a
    discriminant = b**2 - 4*a*c
    
    # Handle complex results
    sqrt_disc = np.sqrt(discriminant.astype(complex))
    r1 = (-b + sqrt_disc) / (2*a)
    r2 = (-b - sqrt_disc) / (2*a)
    return r1, r2

# 1. Generate K values (Logarithmic scale to cover small and large gains)
gains = np.logspace(-3, 3, 1000) # K from 0.001 to 1000
roots = np.array([solve_roots(k) for k in gains])

# Flatten roots for plotting
real_parts = np.real(roots).flatten()
imag_parts = np.imag(roots).flatten()

# 2. Setup the Plot
plt.figure(figsize=(8, 6))
plt.title("Root Locus for G(s) = (s+2)(s+1) / ((s-2)(s-1))")
plt.xlabel("Real Axis (σ)")
plt.ylabel("Imaginary Axis (jω)")
plt.grid(True, which='both', linestyle='--', linewidth=0.5)
plt.axhline(0, color='black', linewidth=1)
plt.axvline(0, color='black', linewidth=1)

# 3. Plot the Locus
plt.plot(real_parts, imag_parts, 'purple', linewidth=2, label='Root Locus')

# 4. Mark Poles (X) and Zeros (O)
plt.plot([1, 2], [0, 0], 'rx', markersize=12, markeredgewidth=3, label='Open-Loop Poles (s=1, 2)')
plt.plot([-1, -2], [0, 0], 'bo', markersize=12, markerfacecolor='none', markeredgewidth=3, label='Open-Loop Zeros (s=-1, -2)')

# 5. Mark Breakaway and Entry Points
plt.plot(1.414, 0, 'g^', markersize=10, label='Breakaway (+1.414)')
plt.plot(-1.414, 0, 'gv', markersize=10, label='Entry Point (-1.414)')

# 6. Add Arrows (Visual approximation)
# Top branch arrow
plt.arrow(0, 1.4, -0.1, 0, head_width=0.1, head_length=0.1, fc='purple', ec='purple')
# Bottom branch arrow
plt.arrow(0, -1.4, -0.1, 0, head_width=0.1, head_length=0.1, fc='purple', ec='purple')


plt.legend(loc='upper right')
plt.xlim(-3.5, 3.5)
plt.ylim(-2.5, 2.5)

# Save/Show
plt.tight_layout()
plt.show()