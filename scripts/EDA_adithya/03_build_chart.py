"""
Build standalone HTML scatter chart: DS_z vs. trip volume change
======================================================================
Reads scatter_data.json (from 02_zone_lookup_merge.py) and generates a
self-contained HTML file with an embedded Chart.js bubble chart —
DS_z (fee burden) on the x-axis, pct_volume_change on the y-axis,
bubble size proportional to trip volume (N_z), pickup/dropoff as
separate series, plus a least-squares trend line.

Requires: none beyond the standard library (json)
Input: scatter_data.json
Output: ds_z_vs_volume_change.html
"""

import json

with open("scatter_data.json") as f:
    data = json.load(f)

pickup = [d for d in data if d["direction"] == "pickup"]
dropoff = [d for d in data if d["direction"] == "dropoff"]


def to_points(rows):
    return [
        {
            "x": round(r["DS_z"] * 100, 3),
            "y": round(r["pct_volume_change"] * 100, 2),
            "r": r["N_z"],
            "zone": r["zone"],
            "name": r["Zone"],
            "n2024": r["n_2024"],
            "n2025": r["n_2025"],
        }
        for r in rows
    ]


pickup_pts = to_points(pickup)
dropoff_pts = to_points(dropoff)

# Least-squares trend line over the combined (pickup + dropoff) points,
# in the same percentage units used for plotting
xs = [d["x"] for d in pickup_pts + dropoff_pts]
ys = [d["y"] for d in pickup_pts + dropoff_pts]
n = len(xs)
mx = sum(xs) / n
my = sum(ys) / n
num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
den = sum((x - mx) ** 2 for x in xs)
slope = num / den
intercept = my - slope * mx
minx, maxx = min(xs), max(xs)

pickup_json = json.dumps(pickup_pts, separators=(",", ":"))
dropoff_json = json.dumps(dropoff_pts, separators=(",", ":"))

CHART_FRAGMENT = f"""<div style="font-family: 'Helvetica Neue', Arial, sans-serif;">
  <p style="font-size: 14px; color: #5F5E5A; margin: 0 0 1rem; line-height: 1.6;">
    Each bubble is one TLC zone, split by pickup or dropoff direction. Bubble size reflects trip volume (N_z).
  </p>
  <div style="position: relative; width: 100%; height: 460px;">
    <canvas id="dsZChart" role="img" aria-label="Scatter chart comparing Zone Disruption Score to trip volume change across NYC TLC zones, showing a negative relationship: zones with higher fee burden saw larger declines in trip volume.">
      Scatter plot of DS_z (fee burden, x-axis) versus trip volume change (y-axis) for {n} zone-direction pairs.
    </canvas>
  </div>
  <div style="display: flex; flex-wrap: wrap; gap: 16px; margin-top: 10px; font-size: 12px; color: #5F5E5A;">
    <span style="display: flex; align-items: center; gap: 4px;"><span style="width: 10px; height: 10px; border-radius: 50%; background: #1D9E75;"></span>Pickup</span>
    <span style="display: flex; align-items: center; gap: 4px;"><span style="width: 10px; height: 10px; border-radius: 50%; background: #D85A30;"></span>Dropoff</span>
    <span style="display: flex; align-items: center; gap: 4px;"><span style="width: 14px; height: 0; border-top: 2px dashed #888780;"></span>Linear trend</span>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
(function() {{
  const pickup = {pickup_json};
  const dropoff = {dropoff_json};
  const slope = {slope};
  const intercept = {intercept};
  const trendLine = [
    {{ x: {minx}, y: intercept + slope * {minx} }},
    {{ x: {maxx}, y: intercept + slope * {maxx} }}
  ];

  const isDark = matchMedia('(prefers-color-scheme: dark)').matches;
  const gridColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
  const textColor = isDark ? '#B4B2A9' : '#5F5E5A';

  new Chart(document.getElementById('dsZChart'), {{
    type: 'bubble',
    data: {{
      datasets: [
        {{ label: 'Pickup', data: pickup,
           backgroundColor: 'rgba(29,158,117,0.45)', borderColor: 'rgba(29,158,117,0.9)', borderWidth: 1 }},
        {{ label: 'Dropoff', data: dropoff,
           backgroundColor: 'rgba(216,90,48,0.45)', borderColor: 'rgba(216,90,48,0.9)', borderWidth: 1 }},
        {{ label: 'Linear trend', type: 'line', data: trendLine,
           borderColor: textColor, borderWidth: 1.5, borderDash: [6, 4], pointRadius: 0, fill: false, tension: 0 }}
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      layout: {{ padding: 12 }},
      scales: {{
        x: {{ type: 'linear', min: 0, max: 7,
              title: {{ display: true, text: 'Zone Disruption Score, DS_z (%)', color: textColor, font: {{ size: 12 }} }},
              grid: {{ color: gridColor }}, ticks: {{ color: textColor, callback: (v) => v + '%' }} }},
        y: {{ title: {{ display: true, text: 'Trip volume change, 2024 to 2025 (%)', color: textColor, font: {{ size: 12 }} }},
              grid: {{ color: gridColor }}, ticks: {{ color: textColor, callback: (v) => v + '%' }} }}
      }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            label: function(context) {{
              const d = context.raw;
              if (!d.name) return '';
              return [
                d.name + ' (zone ' + d.zone + ')',
                'DS_z: ' + d.x.toFixed(2) + '%',
                'Volume change: ' + (d.y >= 0 ? '+' : '') + d.y.toFixed(1) + '%',
                '2024: ' + d.n2024.toLocaleString() + ' trips, 2025: ' + d.n2025.toLocaleString() + ' trips'
              ];
            }}
          }}
        }}
      }}
    }}
  }});
}})();
</script>"""

doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DS_z vs trip volume change — NYC HVFHV zones</title>
<style>
  body {{ margin: 0; padding: 32px 24px; background: #ffffff; color: #18181b; font-family: 'Helvetica Neue', Arial, sans-serif; }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #0c0a09; color: #e7e5e4; }} }}
  .wrap {{ max-width: 920px; margin: 0 auto; }}
  h1 {{ font-size: 20px; font-weight: 600; margin: 0 0 4px; }}
  .sub {{ font-size: 13px; color: #78716c; margin: 0 0 20px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Fee burden vs. trip volume change, by zone</h1>
  <p class="sub">NYC HVFHV &middot; CBD congestion fee &middot; Feb&ndash;Jun 2024 vs Feb&ndash;Jun 2025</p>
  {CHART_FRAGMENT}
</div>
</body>
</html>"""

with open("ds_z_vs_volume_change.html", "w") as f:
    f.write(doc)

print(f"Wrote ds_z_vs_volume_change.html ({len(doc):,} chars)")
print(f"Trend line: slope={slope:.3f}, intercept={intercept:.3f}")
