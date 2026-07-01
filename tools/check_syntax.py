import js2py

try:
    with open('dashboard/map.js', 'r', encoding='utf-8') as f:
        code = f.read()
    print("Reading JS file success, length:", len(code))
except Exception as e:
    print(e)
