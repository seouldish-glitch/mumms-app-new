import os
import re

public_dir = r"c:\Users\Dell\Downloads\mumms-app-new-main (3)\mumms-app-new-main\public"
html_files = [f for f in os.listdir(public_dir) if f.endswith('.html')]

# We want to change z-[100], z-[200], z-[300] etc to z-[10000+] for modals/overlays
# so they appear above the mobile nav (z-9999)

for filename in html_files:
    filepath = os.path.join(public_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace z-[XXX] with z-[10000] for high-level overlays
    # We look for classes that suggest modals or overlays
    new_content = re.sub(r'z-\[([1-9][0-9]{2})\]', r'z-[10000]', content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated z-index in {filename}")
    else:
        print(f"No z-index updates needed in {filename}")
