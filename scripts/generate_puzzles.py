"""
Synthetic NYT Connections puzzle generator.

Uses Haiku to generate candidate puzzles (few-shot from real examples),
then a second Haiku call validates each group for clarity, exclusivity,
and accuracy. Passing puzzles are appended to synthetic_puzzles.csv.

Usage:
    python scripts/generate_puzzles.py --n 200 --out environments/connections/synthetic_puzzles.csv
"""
import argparse
import asyncio
import csv
import json
import random
import re
import sys
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Load existing puzzles for RAG context + deduplication
# ---------------------------------------------------------------------------

def load_existing_puzzles(csv_path: Path) -> list[dict]:
    puzzles: dict[str, dict] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gid = row["Game ID"]
            if gid not in puzzles:
                puzzles[gid] = {"game_id": gid, "date": row["Puzzle Date"], "groups": []}
            g = next((g for g in puzzles[gid]["groups"] if g["name"] == row["Group Name"]), None)
            if g is None:
                g = {"name": row["Group Name"], "level": int(row["Group Level"]), "words": []}
                puzzles[gid]["groups"].append(g)
            g["words"].append(row["Word"].upper())
    return list(puzzles.values())


def existing_words(puzzles: list[dict]) -> set[str]:
    return {w for p in puzzles for g in p["groups"] for w in g["words"]}


def format_puzzle_for_prompt(puzzle: dict) -> str:
    lines = []
    for g in sorted(puzzle["groups"], key=lambda x: x["level"]):
        lines.append(f'  Level {g["level"]} | {g["name"]}: {", ".join(g["words"])}')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

GENERATE_SYSTEM = """You are a creative puzzle designer for NYT Connections.
Your job is to create new, original word-grouping puzzles.
Each puzzle has 16 words forming exactly 4 groups of 4.

Difficulty levels:
  Level 0 (Yellow): Obvious, direct connection. E.g. "WET WEATHER": RAIN, SNOW, HAIL, SLEET
  Level 1 (Green): Requires some thought. E.g. "NBA TEAMS": HEAT, NETS, JAZZ, BUCKS
  Level 2 (Blue): Lateral thinking needed. E.g. "TOMS": PETTY, CRUISE, HOLLAND, WAITS
  Level 3 (Purple): Tricky wordplay, hidden patterns. E.g. "PALINDROMES": LEVEL, KAYAK, RACECAR, MOM

Category ideas to draw from (mix and match freely):
- Celebrity last names sharing a first name: "MIKES" → TYSON, JORDAN, MYERS, PHELPS
- ___ + letter / letter + ___: "DANCE EVENTS + A LETTER" → RAVEN(RAVE+N), PROMO(PROM+O), DISCOG(DISCO+G)
- Hidden preceding word: "FIRE ___" → WORKS, PLACE, SIDE, TRUCK
- Hidden following word: "___ BALL" → BASKET, FOOT, BASE, SNOW
- Words hiding a smaller word inside: "CONTAIN A COLOR" → bLUEbell, gREENhouse, wHITEout, pINKy
- Words hiding an animal: "CONTAIN AN ANIMAL" → BEACON(BEAR-ish), PARSLEY(ASS?), actually use real examples
- Foods, cuisines, ingredients, cocktails, cheeses, pasta types
- Movies, TV shows, songs, albums, bands
- Sports teams, athletes, positions, stadiums
- Countries, capitals, currencies, languages
- Animals, plants, body parts, diseases
- Homophones or near-homophones of other words
- Rhyming words (all rhyme with X)
- Slang terms for the same thing
- Famous ___s (presidents, scientists, artists, inventors)
- Brand names, companies, logos
- Things associated with a number: "ASSOCIATED WITH 7" → DEADLY, SEAS, WONDERS, DWARFS
- Collective nouns for animals: "MURDER", "PRIDE", "SCHOOL", "GAGGLE"
- Abbreviations or acronyms
- Things that are a specific color
- Words that are also verbs meaning the same thing
- Portmanteau words or blends

Rules:
- All 16 words must be unique within the puzzle
- Single words preferred; short 2-word phrases (e.g. "LOST BOYS") are fine if well-known
- Be creative and original — do not reuse exact themes from the examples
- Level 0 should always have a clean, unambiguous connection as the easy entry point.
- Level 3 should use wordplay like: celebrity last names sharing a first name, hidden
  preceding/following word (e.g. "FIRE ___"), words that follow/precede a common word,
  double meanings, or "___ + a letter added". Do NOT use anagrams — they are too hard
  to verify and often incorrect.
- Try to include at least one word per group that could superficially seem to belong
  elsewhere (e.g. JAZZ in "NBA TEAMS" when there's also a music group)."""

def generate_prompt(examples: list[dict], blocked_themes: set[str]) -> str:
    example_text = "\n\n".join(
        f"Example {i+1}:\n{format_puzzle_for_prompt(p)}"
        for i, p in enumerate(examples)
    )
    # Show a sample of blocked themes so the model avoids them
    blocked_sample = sorted(blocked_themes)[:150]
    blocked_text = ", ".join(blocked_sample)
    return f"""Here are {len(examples)} real NYT Connections puzzles for reference:

{example_text}

ALREADY USED THEMES (do NOT reuse any of these, not even close variations):
{blocked_text}

Now create a brand new puzzle with completely original themes not in the list above.
Before outputting, verify: (1) no word appears in more than one group, (2) all group names are original.

Output ONLY valid JSON in this exact format:
{{
  "groups": [
    {{"level": 0, "name": "GROUP NAME", "words": ["W1", "W2", "W3", "W4"]}},
    {{"level": 1, "name": "GROUP NAME", "words": ["W1", "W2", "W3", "W4"]}},
    {{"level": 2, "name": "GROUP NAME", "words": ["W1", "W2", "W3", "W4"]}},
    {{"level": 3, "name": "GROUP NAME", "words": ["W1", "W2", "W3", "W4"]}}
  ]
}}"""


VALIDATE_SYSTEM = """You are a strict quality reviewer for NYT Connections puzzles.
You evaluate whether a puzzle meets publication standards."""

def validate_prompt(puzzle_groups: list[dict]) -> str:
    groups_text = "\n".join(
        f'  Level {g["level"]} | {g["name"]}: {", ".join(g["words"])}'
        for g in sorted(puzzle_groups, key=lambda x: x["level"])
    )
    return f"""Review this NYT Connections puzzle:

{groups_text}

For each group, evaluate:
1. clarity (0-10): Are all 4 words genuinely connected by the group name?
2. exclusivity (0-10): Is each word clearly in THIS group and not another? (9-10 = perfect fit, 6-7 = some ambiguity which is fine for harder groups)
3. accuracy (0-10): Is the group name a precise description of the connection?

Also check:
- Do any words appear in multiple groups?

Output ONLY valid JSON:
{{
  "duplicate_words": false,
  "groups": [
    {{"level": 0, "name": "...", "clarity": 9, "exclusivity": 8, "accuracy": 9}},
    {{"level": 1, "name": "...", "clarity": 8, "exclusivity": 7, "accuracy": 8}},
    {{"level": 2, "name": "...", "clarity": 7, "exclusivity": 8, "accuracy": 9}},
    {{"level": 3, "name": "...", "clarity": 6, "exclusivity": 8, "accuracy": 7}}
  ],
  "overall_score": 8.0,
  "rejection_reason": null
}}
Set rejection_reason to a short string if there is a clear problem, else null."""


# ---------------------------------------------------------------------------
# Generation + validation
# ---------------------------------------------------------------------------

def extract_first_json(text: str) -> dict | None:
    """Extract the first complete balanced JSON object from text."""
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i+1])
    return None


async def generate_puzzle(client: anthropic.AsyncAnthropic, examples: list[dict], blocked_themes: set[str]) -> dict | None:
    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=GENERATE_SYSTEM,
            messages=[{"role": "user", "content": generate_prompt(examples, blocked_themes)}],
        )
        text = resp.content[0].text.strip()
        return extract_first_json(text)
    except Exception as e:
        print(f"  [generate error] {e}", file=sys.stderr)
        return None


async def validate_puzzle(client: anthropic.AsyncAnthropic, groups: list[dict]) -> dict | None:
    try:
        resp = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=512,
            system=VALIDATE_SYSTEM,
            messages=[{"role": "user", "content": validate_prompt(groups)}],
        )
        text = resp.content[0].text.strip()
        return extract_first_json(text)
    except Exception as e:
        print(f"  [validate error] {e}", file=sys.stderr)
        return None


def puzzle_passes(validation: dict, min_score: float = 6.0) -> bool:
    if validation.get("duplicate_words"):
        return False
    if validation.get("rejection_reason"):
        return False
    if validation.get("overall_score", 0) < min_score:
        return False
    for g in validation.get("groups", []):
        if min(g.get("clarity", 0), g.get("exclusivity", 0), g.get("accuracy", 0)) < 4:
            return False
    return True


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

CSV_FIELDS = ["Game ID", "Puzzle Date", "Group Name", "Group Level", "Word"]

def append_to_csv(out_path: Path, game_id: int, groups: list[dict]):
    write_header = not out_path.exists() or out_path.stat().st_size == 0
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        # Use a fake date in 2022 so _build_rows treats it as train data
        date = f"2022-01-{(game_id % 28) + 1:02d}"
        for g in groups:
            for word in g["words"]:
                writer.writerow({
                    "Game ID": f"syn-{game_id}",
                    "Puzzle Date": date,
                    "Group Name": g["name"],
                    "Group Level": g["level"],
                    "Word": word.upper(),
                })


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def main(n: int, out_path: Path, examples_per_prompt: int = 5):
    data_csv = Path(__file__).parent.parent / "environments" / "connections" / "connections_data.csv"
    existing = load_existing_puzzles(data_csv)

    # Deduplicate on group theme names, not individual words
    used_themes = {g["name"].upper() for p in existing for g in p["groups"]}

    if out_path.exists() and out_path.stat().st_size > 0:
        syn_puzzles = load_existing_puzzles(out_path)
        used_themes |= {g["name"].upper() for p in syn_puzzles for g in p["groups"]}
        next_id = len(syn_puzzles) + 1
    else:
        next_id = 1

    client = anthropic.AsyncAnthropic()
    accepted = 0
    attempts = 0
    consecutive_failures = 0
    max_consecutive_failures = 100

    print(f"Generating {n} puzzles. {len(used_themes)} existing themes to avoid.")

    while accepted < n:
        attempts += 1
        examples = random.sample(existing, min(examples_per_prompt, len(existing)))

        print(f"  Attempt {attempts} (streak={consecutive_failures}): generating...", end=" ", flush=True)
        raw = await generate_puzzle(client, examples, used_themes)
        if not raw or "groups" not in raw:
            print("bad JSON")
            consecutive_failures += 1
        else:
            groups = raw["groups"]
            if len(groups) != 4 or any(len(g.get("words", [])) != 4 for g in groups):
                print("wrong structure")
                consecutive_failures += 1
            else:
                for g in groups:
                    g["words"] = [w.upper() for w in g["words"]]

                all_words = [w for g in groups for w in g["words"]]
                if len(set(all_words)) != 16:
                    print("duplicate words in puzzle")
                    consecutive_failures += 1
                else:
                    new_themes = {g["name"].upper() for g in groups}
                    if new_themes & used_themes:
                        print(f"duplicate theme(s): {new_themes & used_themes}")
                        consecutive_failures += 1
                    else:
                        print("validating...", end=" ", flush=True)
                        validation = await validate_puzzle(client, groups)
                        if not validation:
                            print("bad validation JSON")
                            consecutive_failures += 1
                        else:
                            score = validation.get("overall_score", 0)
                            if puzzle_passes(validation):
                                append_to_csv(out_path, next_id, groups)
                                used_themes.update(new_themes)
                                accepted += 1
                                next_id += 1
                                consecutive_failures = 0
                                print(f"ACCEPTED (score={score:.1f}) [{accepted}/{n}]")
                            else:
                                reason = validation.get("rejection_reason") or f"score={score:.1f}"
                                print(f"rejected ({reason})")
                                consecutive_failures += 1

        if consecutive_failures >= max_consecutive_failures:
            print(f"\n⚠️  {max_consecutive_failures} consecutive failures — stopping to preserve API credits.")
            print(f"   {accepted} puzzles saved so far. Re-run to continue with fresh context.")
            break

    rate = f"{100*accepted/attempts:.0f}%" if attempts else "n/a"
    print(f"\nDone. {accepted} puzzles accepted in {attempts} attempts ({rate} acceptance rate).")
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200, help="Number of puzzles to generate")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent.parent / "environments" / "connections" / "synthetic_puzzles.csv",
    )
    args = parser.parse_args()
    asyncio.run(main(args.n, args.out))
