#!/usr/bin/env python3
"""Generate Fig 4: Completeness-discrepancy tradeoff bubble chart.
Target: large fonts (≥16pt), big markers, clear labels for 55% width in Elsevier."""

import matplotlib.pyplot as plt
import matplotlib
import numpy as np

matplotlib.rcParams.update({
    'font.size': 18,
    'axes.titlesize': 20,
    'axes.labelsize': 18,
    'xtick.labelsize': 16,
    'ytick.labelsize': 16,
    'font.family': 'serif',
})

# Data: (name, avg_completeness, pct_with_discrepancy, n, category)
sources = [
    ('Database-\nsampled', 5.5, 65.0, 755, 'Human'),
    ('Claude\nOpus 4.6', 6.4, 72.8, 114, 'Commercial LLM'),
    ('Gemini\n3 Flash', 5.2, 44.7, 103, 'Commercial LLM'),
    ('GPT-4.1\nnano', 4.8, 38.5, 65, 'Commercial LLM'),
    ('Llama\n3.3 70B', 4.3, 46.4, 97, 'Open-source LLM'),
    ('Llama\n3.1 8B', 3.0, 10.8, 120, 'Open-source LLM'),
]

colors = {
    'Human': '#4285F4',
    'Commercial LLM': '#EA4335',
    'Open-source LLM': '#9C27B0',
}

fig, ax = plt.subplots(figsize=(10, 7))

# Trend line
xs = [s[1] for s in sources]
ys = [s[2] for s in sources]
z = np.polyfit(xs, ys, 1)
p = np.poly1d(z)
xline = np.linspace(2.5, 7.5, 100)
ax.plot(xline, p(xline), '--', color='gray', alpha=0.5, linewidth=1.5)

# Plot bubbles
for name, comp, disc, n, cat in sources:
    size = max(n / 2.5, 80)  # scale bubble, min 80
    ax.scatter(comp, disc, s=size, c=colors[cat], alpha=0.85,
               edgecolors='white', linewidth=1.5, zorder=5)

# Labels with offsets to avoid overlap
offsets = {
    'Database-\nsampled': (-0.6, 3),
    'Claude\nOpus 4.6': (0.3, 2),
    'Gemini\n3 Flash': (0.35, -1),
    'GPT-4.1\nnano': (-0.8, -4),
    'Llama\n3.3 70B': (-0.9, 3),
    'Llama\n3.1 8B': (0.3, 2),
}

for name, comp, disc, n, cat in sources:
    dx, dy = offsets[name]
    ax.annotate(name, (comp, disc), (comp + dx, disc + dy),
                fontsize=14, fontweight='bold', color=colors[cat],
                ha='center', va='bottom')

ax.set_xlabel('Average Metadata Completeness (fields per citation)',
              fontweight='bold')
ax.set_ylabel('% Citations with ≥1 Discrepancy', fontweight='bold')
ax.set_title('Metadata Completeness–Discrepancy Tradeoff (r = 0.97)',
             fontsize=20, fontweight='bold', pad=12)

ax.set_xlim(2.2, 7.5)
ax.set_ylim(-2, 85)
ax.grid(True, alpha=0.3)

# Legend
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#4285F4',
           markersize=14, label='Database-sampled'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#EA4335',
           markersize=14, label='Commercial LLM'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#9C27B0',
           markersize=14, label='Open-source LLM'),
]
ax.legend(handles=legend_elements, loc='lower right', fontsize=14,
          framealpha=0.9)

plt.tight_layout()

out = 'figures/fig4_completeness_tradeoff'
fig.savefig(f'{out}.png', dpi=300, bbox_inches='tight', facecolor='white')
fig.savefig(f'{out}.svg', bbox_inches='tight', facecolor='white')
print(f'Saved {out}.png and .svg')

from PIL import Image
img = Image.open(f'{out}.png')
print(f'Size: {img.size}, ratio: {img.size[0]/img.size[1]:.2f}')
