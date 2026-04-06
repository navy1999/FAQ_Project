import re
with open("test_result.txt", "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("FAILED"):
            print(line.strip())
