with open('dashboard/map.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

stack = []
for idx in range(206, 520):
    line = lines[idx]
    for col, char in enumerate(line):
        if char == '{':
            stack.append((idx + 1, col + 1, line.strip()))
        elif char == '}':
            if stack:
                top_line, top_col, top_text = stack.pop()
                print(f"L{idx+1:3d}:{col+1:2d} '}}' closes L{top_line:3d}:{top_col:2d} '{top_text[:30]}'")
            else:
                print(f"L{idx+1:3d}:{col+1:2d} '}}' WITHOUT MATCHING '{'{'}'!")

print("\n--- UNCLOSED STACK AT L516 ---")
for l, c, text in stack:
    print(f"L{l:3d}:{c:2d} -> {text[:40]}")
