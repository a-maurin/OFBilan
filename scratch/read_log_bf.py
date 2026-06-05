import json

log_path = "C:/Users/aguirre.maurin/.gemini/antigravity/brain/bf3abe42-decc-4784-93c0-e31041792c99/.system_generated/logs/transcript.jsonl"

with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        try:
            obj = json.loads(line)
            source = obj.get("source")
            step_type = obj.get("type")
            content = obj.get("content")
            if step_type in ["USER_INPUT", "PLANNER_RESPONSE"] and content:
                print(f"=== Step {obj.get('step_index')} ({source}/{step_type}) ===")
                print(content[:500])
                if len(content) > 500:
                    print("... [TRUNCATED]")
                print("\n" + "="*40 + "\n")
        except Exception as e:
            pass
