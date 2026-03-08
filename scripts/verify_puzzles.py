"""
Verify synthetic puzzles for correctness, especially wordplay-based categories.
"""
import csv
import re
from pathlib import Path

# Load a word list for validation
WORD_LIST_PATH = "/usr/share/dict/words"
try:
    with open(WORD_LIST_PATH) as f:
        VALID_WORDS = {w.strip().upper() for w in f}
    # Add some common words that might be missing
    VALID_WORDS.update({"THUNK", "TANGLE", "TRAPPED", "MAG", "GAR", "HOR"})
except FileNotFoundError:
    VALID_WORDS = set()


def load_puzzles(csv_path: Path) -> dict[str, dict]:
    """Load puzzles grouped by game ID."""
    puzzles = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gid = row["Game ID"]
            if gid not in puzzles:
                puzzles[gid] = {"groups": []}
            
            group_name = row["Group Name"]
            existing = next((g for g in puzzles[gid]["groups"] if g["name"] == group_name), None)
            if existing is None:
                existing = {"name": group_name, "level": int(row["Group Level"]), "words": []}
                puzzles[gid]["groups"].append(existing)
            existing["words"].append(row["Word"].upper())
    return puzzles


def check_remove_prefix(words: list[str], prefix: str) -> list[str]:
    """
    REMOVE 'X' FROM START means: T + word = valid word
    So we check if prefix + word is a valid word.
    """
    failures = []
    prefix = prefix.upper()
    for word in words:
        word_upper = word.upper()
        combined = prefix + word_upper
        if VALID_WORDS and combined not in VALID_WORDS:
            failures.append(f"'{prefix}' + '{word}' = '{combined}' (not found in dictionary)")
    return failures


def check_remove_suffix(words: list[str], suffix: str) -> list[str]:
    """
    REMOVE 'X' FROM END means: word ends with suffix and removing it gives a valid word.
    """
    failures = []
    suffix = suffix.upper()
    for word in words:
        word_upper = word.upper()
        if word_upper.endswith(suffix):
            remainder = word_upper[:-len(suffix)]
            if VALID_WORDS and remainder and remainder not in VALID_WORDS:
                failures.append(f"'{word}' - '{suffix}' = '{remainder}' (not a valid word)")
        else:
            failures.append(f"'{word}' does not end with '{suffix}'")
    return failures


def check_hidden_specific(words: list[str], hidden: str) -> list[str]:
    """Check if each word contains the specific hidden string."""
    failures = []
    hidden_upper = hidden.upper()
    for word in words:
        # Handle multi-word entries
        word_clean = word.upper().replace(" ", "")
        if hidden_upper not in word_clean:
            failures.append(f"'{word}' does not contain '{hidden}'")
    return failures


def verify_group(group_name: str, words: list[str]) -> tuple[str, list[str]]:
    """Verify a single group based on its category pattern. Returns (category_type, failures)."""
    name_upper = group_name.upper()
    
    # REMOVE 'X' FROM START patterns
    match = re.search(r"REMOVE\s*['\"]?([A-Z]+)['\"]?\s*FROM\s*START", name_upper)
    if match:
        prefix = match.group(1)
        return ("REMOVE_PREFIX", check_remove_prefix(words, prefix))
    
    # REMOVE 'X' FROM END patterns  
    match = re.search(r"REMOVE\s*['\"]?([A-Z]+)['\"]?\s*FROM\s*END", name_upper)
    if match:
        suffix = match.group(1)
        return ("REMOVE_SUFFIX", check_remove_suffix(words, suffix))
    
    # REMOVE 'ED' TO GET patterns
    match = re.search(r"REMOVE\s*['\"]?([A-Z]+)['\"]?\s*TO\s*GET", name_upper)
    if match:
        suffix = match.group(1)
        return ("REMOVE_SUFFIX", check_remove_suffix(words, suffix))
    
    # WORDS HIDING 'X' - specific string hidden
    match = re.search(r"HIDING\s*['\"]([A-Z]+)['\"]", name_upper)
    if match:
        hidden = match.group(1)
        return ("HIDDEN_SPECIFIC", check_hidden_specific(words, hidden))
    
    # REMOVE 'S' TO GET A VERB / ROCK BAND etc
    match = re.search(r"REMOVE\s*['\"]?([A-Z])['\"]?\s*TO\s*GET", name_upper)
    if match:
        letter = match.group(1)
        failures = []
        for word in words:
            if not word.upper().startswith(letter) and not word.upper().endswith(letter):
                failures.append(f"'{word}' doesn't start or end with '{letter}'")
        return ("REMOVE_LETTER", failures)
    
    # REMOVE THE FIRST LETTER TO GET patterns
    if "REMOVE" in name_upper and "FIRST LETTER" in name_upper:
        failures = []
        for word in words:
            remainder = word[1:].upper()
            if VALID_WORDS and remainder not in VALID_WORDS:
                failures.append(f"'{word}' minus first letter = '{remainder}' (not valid)")
        return ("REMOVE_FIRST", failures)
    
    # REMOVE FIRST & LAST LETTER patterns
    if "FIRST" in name_upper and "LAST" in name_upper and "REMOVE" in name_upper:
        failures = []
        for word in words:
            if len(word) > 2:
                remainder = word[1:-1].upper()
                if VALID_WORDS and remainder not in VALID_WORDS:
                    failures.append(f"'{word}' without first/last = '{remainder}' (not valid)")
        return ("REMOVE_BOTH", failures)
    
    # Skip generic category patterns - these are semantic not wordplay
    skip_patterns = [
        "THINGS THAT", "TYPES OF", "WORDS THAT FOLLOW", "WORDS THAT PRECEDE",
        "FAMOUS", "CELEBRITIES", "___ ", "SYNONYMS", "ANAGRAM", "HOMOPHONE",
        "PRECEDE", "FOLLOW", "CHARACTERS", "INGREDIENTS", "PARTS OF",
        "SHADES OF", "FLAVORS", "COCKTAIL", "CONTAINING", "HIDDEN", "CONTAIN"
    ]
    for pattern in skip_patterns:
        if pattern in name_upper:
            return ("SEMANTIC", [])
    
    return ("UNKNOWN", [])


def main():
    csv_path = Path(__file__).parent.parent / "environments" / "connections" / "synthetic_puzzles.csv"
    puzzles = load_puzzles(csv_path)
    
    print(f"Loaded {len(puzzles)} puzzles")
    print(f"Word list has {len(VALID_WORDS)} words\n")
    
    issues = []
    category_counts = {}
    
    for gid, puzzle in sorted(puzzles.items(), key=lambda x: int(x[0].replace("syn-", ""))):
        for group in puzzle["groups"]:
            cat_type, failures = verify_group(group["name"], group["words"])
            category_counts[cat_type] = category_counts.get(cat_type, 0) + 1
            
            if failures:
                issues.append({
                    "game_id": gid,
                    "group": group["name"],
                    "level": group["level"],
                    "words": group["words"],
                    "category": cat_type,
                    "failures": failures
                })
    
    print("Category breakdown:")
    for cat, count in sorted(category_counts.items()):
        print(f"  {cat}: {count}")
    print()
    
    if issues:
        print(f"Found {len(issues)} groups with issues:\n")
        for issue in issues:
            print(f"=== {issue['game_id']} | Level {issue['level']} | {issue['group']} ===")
            print(f"Words: {', '.join(issue['words'])}")
            for f in issue["failures"]:
                print(f"  ❌ {f}")
            print()
    else:
        print("No issues found!")
    
    return issues


if __name__ == "__main__":
    main()
