import csv
import json
import random
import re
from pathlib import Path

import verifiers as vf
from datasets import Dataset

SYSTEM_PROMPT = """You are playing NYT Connections. The puzzle contains 16 words that form exactly 4 groups of 4 related words.

Rules:
- Guess one group of 4 related words at a time
- You have 4 mistakes allowed before the game ends
- Win by correctly identifying all 4 groups

Before each guess, briefly explain WHY these 4 words belong together in <reason> tags, then provide your guess in <guess> tags:

<reason>Brief explanation of what connects the 4 words</reason>
<guess>WORD1, WORD2, WORD3, WORD4</guess>

Make exactly one guess per response."""

def _build_rows(seed: int = 42, train_shuffles: int = 4) -> tuple[list[dict], list[dict]]:
    """Parse connections_data.csv and return (train_rows, eval_rows).

    Each training puzzle is shuffled train_shuffles times to augment the dataset.
    Eval puzzles get a single canonical shuffle.
    """
    csv_paths = [Path(__file__).parent / "connections_data.csv"]
    synthetic_path = Path(__file__).parent / "synthetic_puzzles.csv"
    if synthetic_path.exists() and synthetic_path.stat().st_size > 0:
        csv_paths.append(synthetic_path)

    puzzles: dict[str, dict] = {}
    for csv_path in csv_paths:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                gid = row["Game ID"]
                if gid not in puzzles:
                    puzzles[gid] = {
                        "game_id": gid,
                        "date": row["Puzzle Date"],
                        "words": [],
                        "groups": {},
                    }
                puzzles[gid]["words"].append(row["Word"])
                gname = row["Group Name"]
                if gname not in puzzles[gid]["groups"]:
                    puzzles[gid]["groups"][gname] = {
                        "name": gname,
                        "level": int(row["Group Level"]),
                        "words": [],
                    }
                puzzles[gid]["groups"][gname]["words"].append(row["Word"])

    rng = random.Random(seed)
    train_rows: list[dict] = []
    eval_rows: list[dict] = []

    for puzzle in puzzles.values():
        groups = list(puzzle["groups"].values())
        is_eval = puzzle["date"].startswith("2025")
        n_shuffles = 1 if is_eval else train_shuffles

        for i in range(n_shuffles):
            words = list(puzzle["words"])
            rng.shuffle(words)
            question = (
                f"The 16 words are:\n{', '.join(words)}\n\n"
                "Find the 4 groups of 4 related words. Make your first guess."
            )
            info = json.dumps(
                {
                    "game_id": puzzle["game_id"],
                    "date": puzzle["date"],
                    "shuffled_words": words,
                    "groups": groups,
                }
            )
            row = {"question": question, "info": info}
            if is_eval:
                eval_rows.append(row)
            else:
                train_rows.append(row)

    return train_rows, eval_rows


class ConnectionsEnv(vf.MultiTurnEnv):
    """NYT Connections word-grouping game as a MultiTurnEnv."""

    async def setup_state(self, state: vf.State) -> vf.State:
        raw = state["info"]
        info = raw if isinstance(raw, dict) else json.loads(raw)
        state["remaining_words"] = [w.upper() for w in info["shuffled_words"]]
        state["mistakes"] = 0
        state["max_mistakes"] = 4
        state["found_groups"] = []  # list of {"name": str, "level": int}
        # Store group words as sorted lists (JSON-serializable for IPC)
        state["groups"] = [
            {
                "name": g["name"],
                "level": g["level"],
                "words": sorted(w.upper() for w in g["words"]),
            }
            for g in info["groups"]
        ]
        return await super().setup_state(state)

    async def env_response(
        self, messages: vf.Messages, state: vf.State
    ) -> vf.Messages:
        remaining = state["remaining_words"]
        found_names = {g["name"] for g in state["found_groups"]}
        unfound_groups = [g for g in state["groups"] if g["name"] not in found_names]

        # --- parse guess and reason from last assistant message ---
        last_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                last_content = msg.get("content") or ""
                break
        parsed = self.parser.parse(last_content)
        guess_raw = getattr(parsed, "guess", None)
        last_reason = (getattr(parsed, "reason", None) or "").strip()

        def _mistake(reason: str, guessed: list[str] | None = None) -> vf.Messages:
            state["mistakes"] += 1
            left = state["max_mistakes"] - state["mistakes"]
            guess_line = f"Your incorrect guess: {', '.join(guessed)}\n" if guessed else ""
            if left <= 0:
                msg = f"{guess_line}{reason} No mistakes remaining. Game over! You found {len(state['found_groups'])}/4 groups."
                state["final_env_response"] = [{"role": "user", "content": msg}]
                return state["final_env_response"]
            s = "s" if left != 1 else ""
            return [
                {
                    "role": "user",
                    "content": (
                        f"{guess_line}{reason} {left} mistake{s} remaining.\n\n"
                        f"Current words ({len(remaining)}): {', '.join(remaining)}"
                    ),
                }
            ]

        if not guess_raw or not guess_raw.strip():
            return _mistake("No <guess> tags found. Please format your guess as: <guess>WORD1, WORD2, WORD3, WORD4</guess>.")

        guess_words = [
            w.strip().upper()
            for w in re.split(r"[,\n]+", guess_raw.strip())
            if w.strip()
        ]

        if len(guess_words) != 4:
            return _mistake(
                f"Please guess exactly 4 words (you provided {len(guess_words)}).",
                guessed=guess_words,
            )

        guess_set = frozenset(guess_words)

        invalid = guess_set - frozenset(remaining)
        if invalid:
            return _mistake(
                f"Word(s) not in current puzzle: {', '.join(sorted(invalid))}.",
                guessed=guess_words,
            )

        # --- check against ground truth ---
        correct_group = next(
            (g for g in unfound_groups if set(g["words"]) == guess_set), None
        )

        if correct_group:
            state["found_groups"].append(
                {
                    "name": correct_group["name"],
                    "level": correct_group["level"],
                    "reason": last_reason,
                }
            )
            state["remaining_words"] = [
                w for w in remaining if w not in guess_set
            ]

            if len(state["found_groups"]) == 4:
                m = state["mistakes"]
                msg = (
                    f"Correct! {correct_group['name']}\n\n"
                    f"Congratulations! You found all 4 groups in "
                    f"{m} mistake{'s' if m != 1 else ''}. Puzzle solved!"
                )
                state["final_env_response"] = [{"role": "user", "content": msg}]
                return state["final_env_response"]

            new_remaining = state["remaining_words"]
            return [
                {
                    "role": "user",
                    "content": (
                        f"Correct! {correct_group['name']}\n\n"
                        f"Remaining words ({len(new_remaining)}): {', '.join(new_remaining)}\n\n"
                        "Make your next guess."
                    ),
                }
            ]

        # --- incorrect guess: check one-away ---
        one_away = any(
            len(guess_set & set(g["words"])) == 3 for g in unfound_groups
        )
        prefix = "Incorrect. One away!" if one_away else "Incorrect."
        return _mistake(prefix, guessed=guess_words)

    @vf.stop
    async def game_won(self, state: vf.State) -> bool:
        return len(state.get("found_groups", [])) >= 4

    @vf.stop
    async def game_lost(self, state: vf.State) -> bool:
        return state.get("mistakes", 0) >= state.get("max_mistakes", 4)


def load_environment(
    split: str = "train",
    num_examples: int = -1,
    seed: int = 42,
) -> vf.Environment:
    """Load the NYT Connections game environment.

    Args:
        split: "train" uses pre-2025 puzzles; "eval" uses 2025 puzzles.
        num_examples: Limit dataset size (-1 = use all).
        seed: Random seed for word shuffling.
    """
    train_rows, eval_rows = _build_rows(seed=seed)

    def _make(rows: list[dict], n: int) -> Dataset:
        ds = Dataset.from_list(rows)
        if n > 0:
            ds = ds.select(range(min(n, len(ds))))
        return ds

    train_dataset = _make(train_rows, num_examples if split == "train" else -1)
    eval_dataset = _make(eval_rows, num_examples if split == "eval" else -1)

    parser = vf.XMLParser(fields=["reason", "guess"])

    # Difficulty-weighted correctness (Yellow=0.1, Green=0.2, Blue=0.3, Purple=0.4)
    # Perfect game = 1.0; each mistake costs 0.1 (max penalty 0.4)
    # Mild thinking-length penalty discourages runaway <think> traces.
    _THINK_PENALTY_PER_TOKEN = 0.00005

    async def difficulty_weighted_reward(state) -> float:
        found = state.get("found_groups", [])
        mistakes = state.get("mistakes", 0)
        group_score = sum((g["level"] + 1) / 10.0 for g in found)
        penalty = 0.1 * mistakes

        # Count thinking tokens across all assistant messages
        thinking_tokens = 0
        for msg in state.get("messages", []):
            if msg.get("role") == "assistant":
                content = msg.get("content") or ""
                for m in re.finditer(r"<think>(.*?)</think>", content, re.DOTALL):
                    thinking_tokens += len(m.group(1).split())

        think_penalty = _THINK_PENALTY_PER_TOKEN * thinking_tokens
        return max(0.0, group_score - penalty - think_penalty)

    async def thinking_tokens_metric(state) -> float:
        total = 0
        for msg in state.get("messages", []):
            if msg.get("role") == "assistant":
                content = msg.get("content") or ""
                for m in re.finditer(r"<think>(.*?)</think>", content, re.DOTALL):
                    total += len(m.group(1).split())
        return float(total)

    async def mistakes_used_metric(state) -> float:
        return float(state.get("mistakes", 0))

    async def groups_found_metric(state) -> float:
        return float(len(state.get("found_groups", [])))

    async def avg_difficulty_solved_metric(state) -> float:
        found = state.get("found_groups", [])
        if not found:
            return 0.0
        return sum(g["level"] for g in found) / len(found)

    rubric = vf.Rubric(funcs=[difficulty_weighted_reward], parser=parser)
    rubric.add_metric(mistakes_used_metric)
    rubric.add_metric(groups_found_metric)
    rubric.add_metric(avg_difficulty_solved_metric)
    rubric.add_metric(thinking_tokens_metric)

    return ConnectionsEnv(
        dataset=train_dataset,
        eval_dataset=eval_dataset,
        rubric=rubric,
        parser=parser,
        system_prompt=SYSTEM_PROMPT,
        max_turns=16,
    )
