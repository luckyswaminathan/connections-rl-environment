# connections

### Overview
- **Environment ID**: `lswamina/connections`
- **Short description**: NYT Connections word-grouping puzzle game — find 4 groups of 4 related words from 16 shuffled words.
- **Tags**: multi-turn, game, word-puzzle, reasoning, train, eval

### Datasets
- **Primary dataset**: 915 NYT Connections puzzles (June 2023 – December 2025), scraped from public puzzle archives.
- **Synthetic dataset**: 107 additional puzzles generated via a two-stage LLM pipeline (see below).
- **Split sizes**: ~735 train puzzles (pre-2025, 4 shuffles each → 2940 examples) / 365 eval puzzles (2025 puzzles, 1 shuffle each)
- **Eval split**: held-out 2025 puzzles only — never seen during training.

### Synthetic Puzzle Generation

To augment the training set beyond the ~735 real pre-2025 puzzles, a generate → verify → fix pipeline was built:

1. **Generate** (`scripts/generate_puzzles.py`): Claude Haiku generates candidate puzzles few-shot from real examples drawn from the existing dataset (RAG-style context). Each candidate has 4 groups of 4 words across Yellow/Green/Blue/Purple difficulty levels, with a descriptive category name and an explanation of what connects each group.

2. **Verify** (`scripts/generate_puzzles.py` + `scripts/verify_puzzles.py`): Claude Sonnet validates each generated puzzle, checking each group for:
   - **Clarity** — the category name unambiguously describes the connection
   - **Exclusivity** — no word plausibly belongs to multiple groups
   - **Accuracy** — all words genuinely fit the stated category (including wordplay/prefix/suffix categories)
   - Structural checks: exact 4 words per group, no duplicates, no overlap with existing puzzles

3. **Fix** (`scripts/fix_puzzles.py`): Puzzles that fail verification are repaired by Claude Sonnet (bad groups swapped out, words corrected) rather than discarded, improving yield.

Passing puzzles are appended to `synthetic_puzzles.csv` and automatically included in training builds.

### Task
- **Type**: multi-turn
- **Output format**: One guess per turn inside XML tags: `<guess>WORD1, WORD2, WORD3, WORD4</guess>`, preceded by a brief reasoning in `<reason>` tags.
- **Max turns**: 16 (allows up to 8 full guess rounds)
- **Rubric overview**:
  - `difficulty_weighted_reward` (primary): sum of `(level + 1) / 10` for each found group, minus 0.1 per mistake. Max = 1.0 (all 4 groups, 0 mistakes). Yellow=0.1, Green=0.2, Blue=0.3, Purple=0.4.
  - `mistakes_used_metric`: number of mistakes made (0–4)
  - `groups_found_metric`: integer count of groups found (0–4)
  - `avg_difficulty_solved_metric`: average difficulty level of solved groups
  - `filter/gibberish`: fraction of responses flagged as gibberish
  - `filter/repetition`: fraction of responses flagged as repetitive

### Game Rules
- 16 words form exactly 4 groups of 4 related words
- Difficulty levels: Yellow (0, easiest) → Green (1) → Blue (2) → Purple (3, trickiest)
- 4 mistakes allowed before game over
- Environment responds with one of:
  - `"Correct! [Category]\nRemaining words (N): ..."` on a correct guess
  - `"Incorrect. X mistakes remaining.\nCurrent words (N): ..."` on a wrong guess
  - `"Incorrect. One away! X mistakes remaining."` when 3 of 4 guessed words match a real group
  - `"Congratulations! You found all 4 groups in M mistakes. Puzzle solved!"` on win
  - `"Game over! You found K/4 groups."` on loss

### Quickstart

```bash
prime eval run lswamina/connections -m gpt-4.1-mini -n 20 -r 3
```

Eval split only:
```bash
prime eval run lswamina/connections -m gpt-4.1-mini -n 20 -a '{"split": "eval"}'
```

### Environment Arguments

| Arg | Type | Default | Description |
| --- | ---- | ------- | ----------- |
| `split` | str | `"train"` | `"train"` (pre-2025 puzzles + synthetic) or `"eval"` (2025 puzzles only) |
| `num_examples` | int | `-1` | Limit dataset size (-1 = all) |
| `seed` | int | `42` | Random seed for word shuffling |

### Metrics

| Metric | Meaning |
| ------ | ------- |
| `difficulty_weighted_reward` | Primary reward: difficulty-weighted group score minus mistake penalty, max 1.0 |
| `mistakes_used_metric` | Mistakes made this game (0–4) |
| `groups_found_metric` | Number of groups correctly identified (0–4) |
| `avg_difficulty_solved_metric` | Avg difficulty level of solved groups (0=Yellow … 3=Purple) |
| `num_turns` | Total turns taken |
| `filter/gibberish` | Fraction of responses that are gibberish |
| `filter/repetition` | Fraction of responses with excessive repetition |

### Baseline Results

Evaluated on 100 eval-split puzzles with `max_tokens=16384`:

| Model | Reward | Win Rate | Groups Found |
| ----- | ------ | -------- | ------------ |
| Qwen3-30B-A3B-Thinking-2507 (base) | 0.57 | 61% | 2.9 / 4 |
