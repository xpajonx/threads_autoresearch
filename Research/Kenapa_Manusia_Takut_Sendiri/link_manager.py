import json
import re
import os

def process_markdown_citations(md_path, json_path):
    # 1. Load the sources database
    with open(json_path, 'r', encoding='utf-8') as f:
        sources = json.load(f)

    # 2. Read the markdown content
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 3. Clean existing references section if any (optional)
    if "## Referensi" in content:
        content = content.split("## Referensi")[0].strip()

    # 4. Find all citation numbers in the text [1], [12, 13], etc.
    # This regex finds all digits inside square brackets
    found_citations = re.findall(r'\[(\d+(?:,\s*\d+)*)\]', content)
    
    # Flatten list if multiple numbers were in one bracket e.g. "1, 2" -> ["1", "2"]
    citation_ids = set()
    for group in found_citations:
        ids = [i.strip() for i in group.split(',')]
        citation_ids.update(ids)

    # 5. Build the References section
    ref_section = "\n\n## Referensi\n"
    found_any = False
    
    # Sort for cleaner output
    for cid in sorted(list(citation_ids), key=int):
        if cid in sources:
            source = sources[cid]
            ref_section += f"- [{cid}]: **{source['title']}** - {source['publisher']}. [Buka Link]({source['url']})\n"
            found_any = True
        else:
            ref_section += f"- [{cid}]: *Sumber tidak ditemukan dalam JSON.*\n"

    # 6. Append and Write back
    if found_any:
        new_content = content.strip() + ref_section
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Success: Updated {md_path} with {len(citation_ids)} references.")
    else:
        print(f"Warning: No citations found in {md_path}.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Specific markdown file to process")
    parser.add_argument("--dir", help="Directory containing markdown files and sources.json")
    args = parser.parse_args()

    # Define fallback paths
    DEFAULT_RESEARCH_DIR = r"D:\Pribadi\Obsidian\Writing\Research\Kenapa_Manusia_Takut_Sendiri"
    
    if args.file:
        target_dir = os.path.dirname(os.path.abspath(args.file))
        json_db = os.path.join(target_dir, "sources.json")
        if os.path.exists(json_db):
            process_markdown_citations(args.file, json_db)
    elif args.dir:
        json_db = os.path.join(args.dir, "sources.json")
        for file_name in ["Research_Report.md", "Source_of_Truth.md"]:
            file_path = os.path.join(args.dir, file_name)
            if os.path.exists(file_path):
                process_markdown_citations(file_path, json_db)
    else:
        # Fallback to current directory or default
        json_db = os.path.join(DEFAULT_RESEARCH_DIR, "sources.json")
        for file_name in ["Research_Report.md", "Source_of_Truth.md"]:
            file_path = os.path.join(DEFAULT_RESEARCH_DIR, file_name)
            if os.path.exists(file_path):
                process_markdown_citations(file_path, json_db)
