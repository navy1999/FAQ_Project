from backend.retriever import retrieve

queries = [
    "how do I enroll",
    "how to enroll in vendor services",
    "I want to enroll",
    "how can I sign up",
    "want to enroll",
    "enroll in vendor services",
    "what is vendor services",
    "how does billing work",
    "tell me about pizza",
    "what is the capital of France",
    "billing",
]

print("=== RETRIEVER SEMANTIC CHECK ===")
for q in queries:
    result = retrieve(q)
    top_score = result.get("top_score")
    
    if top_score is None or top_score < 0.45:
        flag = "domain_miss"
    elif top_score < 0.72:
        flag = "clarification"
    else:
        flag = "OK"
        
    score_display = f"{top_score:.4f}" if top_score is not None else "NO SCORE"
    print(f"  [{flag:12}] {q!r:35}  ->  score: {score_display}")
