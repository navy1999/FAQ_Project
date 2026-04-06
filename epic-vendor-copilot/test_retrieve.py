import json
from backend.retriever import Retriever, _encode_query

r = Retriever()
emb = _encode_query("What is the subscription fee?")
D, I = r.index.search(emb, 3)
res = []
for idx, dist in zip(I[0], D[0]):
    res.append({"id": r.entries[idx]["id"], "score": float(dist)})
print(res)

print("cost:", r._check_bloom("How much does it cost?"))
print("price:", r._check_bloom("What is the price?"))
print("process:", r._check_bloom("What is the process to sign up?"))
