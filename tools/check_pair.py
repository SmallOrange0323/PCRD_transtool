with open('dashboard/map.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

stack = []
for idx in range(206, 522):
    line = lines[idx]
    for char in line:
        if char == '{':
            stack.append((idx + 1, line.strip()))
        elif char == '}':
            if stack:
                start_line, content = stack.pop()
                if start_line in [207, 208, 288, 292, 370]:
                    print(f"Closed '{content}' (from L{start_line}) at L{idx+1}")

print("\nRemaining unclosed in block:")
for l, c in stack:
    print(f"L{l}: {c}")
