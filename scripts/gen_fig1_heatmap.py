#!/usr/bin/env python3
"""Generate Fig 1: Inter-database agreement heatmap.
Target: wide & short (3:2 ratio), large fonts for Elsevier preprint."""

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

fields = ['Title', 'Year', 'Journal', 'Volume', 'Pages', 'DOI', 'Authors']
databases = ['CrossRef', 'OpenAlex', 'Sem. Scholar']

data = np.array([
    [97.1, 97.0, 93.2],
    [88.5, 88.5, 86.6],
    [78.2, 76.6, 73.5],
    [99.7, 99.7, 97.9],
    [70.5, 71.1, 53.2],
    [100.0, 100.0, 100.0],
    [56.6, 56.9, 30.3],
])

fig, ax = plt.subplots(figsize=(10, 5))  # 2:1 wide ratio

cmap = matplotlib.colormaps['RdYlGn']
im = ax.imshow(data, cmap=cmap, vmin=25, vmax=100, aspect='auto')

ax.set_xticks(range(len(databases)))
ax.set_xticklabels(databases, fontweight='bold')
ax.set_yticks(range(len(fields)))
ax.set_yticklabels(fields)

ax.set_title('Inter-Database Agreement Rate by Metadata Field',
             fontsize=18, fontweight='bold', pad=12)

# Annotate cells
for i in range(len(fields)):
    for j in range(len(databases)):
        val = data[i, j]
        color = 'white' if val < 60 else 'black'
        ax.text(j, i, f'{val:.1f}%', ha='center', va='center',
                fontsize=15, fontweight='bold', color=color)

cbar = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
cbar.set_label('Agreement Rate (%)', fontsize=14)
cbar.ax.tick_params(labelsize=13)

plt.tight_layout()

# Save
out = 'figures/fig1_agreement_heatmap'
fig.savefig(f'{out}.png', dpi=300, bbox_inches='tight', facecolor='white')
fig.savefig(f'{out}.svg', bbox_inches='tight', facecolor='white')
print(f'Saved {out}.png and .svg')

from PIL import Image
img = Image.open(f'{out}.png')
print(f'Size: {img.size}, ratio: {img.size[0]/img.size[1]:.2f}')
