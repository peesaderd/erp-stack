import os
import re
import json
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    log_file = "C:/Users/ADMIN/.gemini/antigravity/brain/ca6c0922-752b-46b7-8f24-5c8d4ab469f5/.system_generated/logs/transcript_full.jsonl"
    if not os.path.exists(log_file):
        print(f"Error: Log file not found at {log_file}")
        return
        
    print(f"Reading logs from {log_file}...")
    
    # We want to find the user inputs that contain JSON arrays of cookies
    cookie_sets = []
    
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                step = json.loads(line)
                if step.get("type") == "USER_INPUT":
                    content = step.get("content", "")
                    # Check if this content contains a JSON array of cookies
                    # Let's search for JSON array pattern: [ ... ]
                    match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
                    if match:
                        try:
                            cookies_array = json.loads(match.group(0))
                            # Verify if it looks like cookies (has name, value, domain)
                            if isinstance(cookies_array, list) and len(cookies_array) > 0:
                                if "name" in cookies_array[0] and "value" in cookies_array[0]:
                                    cookie_sets.append(cookies_array)
                                    print(f"Found cookie set with {len(cookies_array)} cookies")
                        except Exception as e:
                            pass
            except Exception as e:
                pass
                
    if len(cookie_sets) < 2:
        print(f"Error: Could not find at least two cookie sets in logs. Found: {len(cookie_sets)}")
        return
        
    # We merge them: set 1 (earlier) and set 2 (latest)
    # The last one in the list is the latest one
    set1 = cookie_sets[-2]
    set2 = cookie_sets[-1]
    
    print(f"\nMerging Set 1 ({len(set1)} cookies) and Set 2 ({len(set2)} cookies)...")
    
    merged = {}
    
    # Add set 1 cookies
    for c in set1:
        key = (c.get("domain", ""), c.get("name", ""), c.get("path", "/"))
        # Standardize sameSite to titlecase or omit if None
        if "sameSite" in c:
            if c["sameSite"] is None:
                c["sameSite"] = "None"
            elif isinstance(c["sameSite"], str):
                # Standardize values: "no_restriction" -> "None", "lax" -> "Lax", etc.
                val = c["sameSite"].lower()
                if "none" in val or "no_restriction" in val:
                    c["sameSite"] = "None"
                elif "lax" in val:
                    c["sameSite"] = "Lax"
                elif "strict" in val:
                    c["sameSite"] = "Strict"
        # Standardize secure
        if "secure" not in c:
            c["secure"] = True
        merged[key] = c
        
    # Add set 2 cookies (overwrite duplicate keys)
    for c in set2:
        key = (c.get("domain", ""), c.get("name", ""), c.get("path", "/"))
        if "sameSite" in c:
            if c["sameSite"] is None:
                c["sameSite"] = "None"
            elif isinstance(c["sameSite"], str):
                val = c["sameSite"].lower()
                if "none" in val or "no_restriction" in val:
                    c["sameSite"] = "None"
                elif "lax" in val:
                    c["sameSite"] = "Lax"
                elif "strict" in val:
                    c["sameSite"] = "Strict"
        if "secure" not in c:
            c["secure"] = True
        merged[key] = c
        
    merged_list = list(merged.values())
    print(f"Total merged cookies: {len(merged_list)}")
    
    # Save to cookies.json
    output_file = "cookies.json"
    with open(output_file, 'w', encoding='utf-8') as f_out:
        json.dump(merged_list, f_out, indent=4, ensure_ascii=False)
        
    print(f"Saved merged cookies to {output_file}")

if __name__ == "__main__":
    main()
