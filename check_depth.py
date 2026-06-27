with open('dashboard/map.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

depth = 0
for idx in range(206, 520):
    line = lines[idx]
    opens = line.count('{')
    closes = line.count('}')
    old_depth = depth
    depth += opens - closes
    print(f"L{idx+1:3d} | d_in={old_depth:2d} d_out={depth:2d} (+{opens}, -{closes}) | {line.strip()[:40]}")
