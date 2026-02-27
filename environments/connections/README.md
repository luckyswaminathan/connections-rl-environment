# connections

### Overview
- **Environment ID**: `connections`
- **Short description**: NYT Connections word-grouping puzzle game — find 4 groups of 4 related words from 16 shuffled words.
- **Tags**: multi-turn, game, word-puzzle, reasoning, train, eval

### Datasets
- **Primary dataset**: 915 NYT Connections puzzles (June 2023 – December 2025), scraped from public puzzle archives.
- **Split sizes**: 568 train (pre-2025) / 347 eval (2025 puzzles)

### Task
- **Type**: multi-turn
- **Output format**: One guess per turn inside XML tags: `<guess>WORD1, WORD2, WORD3, WORD4</guess>`
- **Rubric overview**:
  - `groups_solved_reward` (weight=1.0): 0.25 per group correctly identified; 1.0 for solving all 4
  - `mistakes_used_metric` (weight=0): number of mistakes made (0–4)
  - `groups_found_metric` (weight=0): integer count of groups found
  - `avg_difficulty_solved_metric` (weight=0): average difficulty level (0=Yellow, 3=Purple) of solved groups

### Game Rules
- 16 words form exactly 4 groups of 4 related words
- Difficulty levels: Yellow (0, easiest) → Green (1) → Blue (2) → Purple (3, trickiest)
- 4 mistakes allowed before game over
- Environment responds: "Correct! [Category]", "Incorrect. X mistakes remaining.", or "Incorrect. One away! X mistakes remaining." when 3 of 4 guessed words match a group

### Quickstart

```bash
prime eval run connections -m gpt-4.1-mini -n 20 -r 3
```

Train split only:
```bash
prime eval run connections -m gpt-4.1-mini -n 20 -a '{"split": "train"}'
```

### Environment Arguments

| Arg | Type | Default | Description |
| --- | ---- | ------- | ----------- |
| `split` | str | `"train"` | `"train"` (pre-2025 puzzles) or `"eval"` (2025 puzzles) |
| `num_examples` | int | `-1` | Limit dataset size (-1 = all) |
| `seed` | int | `42` | Random seed for word shuffling |

### Metrics

| Metric | Meaning |
| ------ | ------- |
| `groups_solved_reward` | Primary reward: 0.25 per group found, max 1.0 |
| `mistakes_used_metric` | Mistakes made this game (0–4) |
| `groups_found_metric` | Number of groups correctly identified (0–4) |
| `avg_difficulty_solved_metric` | Avg difficulty of solved groups (0=Yellow … 3=Purple) |
| `num_turns` | Total turns taken (from MultiTurnEnv monitor) |
