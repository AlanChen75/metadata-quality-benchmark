#!/usr/bin/env python3
"""Generate Fig 2: Domain variation bar chart.
Target: wide & short (2.5:1 ratio) to share page with Fig 1 + Table 2."""

import matplotlib.pyplot as plt
import matplotlib
import numpy as np

matplotlib.rcParams.update({
    'font.size': 16,
    'axes.titlesize': 18,
    'axes.labelsize': 16,
    'xtick.labelsize': 15,
    'ytick.labelsize': 15,
    'font.family': 'serif',
})

domains = ['Biomedicine', 'CS/ML', 'Engineering', 'Finance', 'Social Sci.']
rates = [17.3, 11.9, 16.1, 14.6, 17.3]
colors = ['#EA4335', '#34A853', '#EA4335', '#FBBC04', '#EA4335']
mean_rate = 15.4

fig, ax = plt.subplots(figsize=(10, 6))  # same ratio as fig3 (~1.7:1)

bars = ax.bar(domains, rates, color=colors, width=0.6, edgecolor='white', linewidth=1)

ax.axhline(y=mean_rate, color='gray', linestyle='--', linewidth=1.5, alpha=0.7)
ax.text(4.6, mean_rate + 0.5, f'Mean: {mean_rate}%', fontsize=13,
        color='gray', ha='right', bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='none'))

for bar, rate in zip(bars, rates):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
            f'{rate}%', ha='center', va='bottom', fontsize=14, fontweight='bold')

ax.set_ylabel('% Citations with ≥1 Discrepancy', fontweight='bold')
ax.set_title('Metadata Discrepancy Rate by Academic Domain',
             fontsize=18, fontweight='bold', pad=10)
ax.set_ylim(0, 21)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()

out = 'figures/fig2_domain_variation'
fig.savefig(f'{out}.png', dpi=300, bbox_inches='tight', facecolor='white')
fig.savefig(f'{out}.svg', bbox_inches='tight', facecolor='white')
print(f'Saved {out}.png and .svg')

from PIL import Image
img = Image.open(f'{out}.png')
print(f'Size: {img.size}, ratio: {img.size[0]/img.size[1]:.2f}')
