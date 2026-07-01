with open('dashboard/map.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

stack = []
for idx in range(206, 525):
    line = lines[idx]
    for char in line:
        if char == '{':
            stack.append(idx + 1)
        elif char == '}':
            if stack:
                stack.pop()

print("Unclosed '{' lines:", stack)
