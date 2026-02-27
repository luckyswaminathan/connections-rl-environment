# Project Memory: connections-rl-environment

## Environment: NYT Connections (`environments/connections/`)

### Status: Working, smoke-tested

### Key files
- `environments/connections/connections.py` — main implementation
- `environments/connections/connections_data.csv` — bundled dataset (copy from project root)
- `environments/connections/pyproject.toml` — package config

### Dataset
- 915 puzzles total: 568 train (pre-2025), 347 eval (2025)
- CSV at project root AND bundled in `environments/connections/connections_data.csv`
- Split logic: `puzzle["date"].startswith("2025")` → eval

### Implementation notes
- `MultiTurnEnv` subclass: `ConnectionsEnv`
- State stores group words as **sorted lists** (not sets/frozensets — ZMQ can't serialize those)
- `parser.parse(text_str)` takes a **string**, not a list of messages. Extract last assistant message manually:
  ```python
  for msg in reversed(messages):
      if msg.get("role") == "assistant":
          last_content = msg.get("content") or ""
          break
  parsed = self.parser.parse(last_content)
  ```
- `state["info"]` arrives as a **dict** (verifiers auto-parses JSON), handle with: `raw if isinstance(raw, dict) else json.loads(raw)`
- Terminal states use `state["final_env_response"]` to signal end-of-game

### Bug fixes applied
1. Root `connections.py` (empty file) was shadowing the environment module — deleted it
2. `frozenset` in state not JSON-serializable for ZMQ IPC — changed to sorted lists
3. `parser.parse(messages)` fails — must extract last assistant content string first
4. `json.loads(state["info"])` fails — verifiers pre-parses `info` dict

### Smoke test results (qwen/qwen3-8b, n=5, r=3)
- avg reward: 0.183
- avg groups_found: 0.733 / 4
- avg mistakes_used: 3.267 / 4
- stop_conditions: game_lost 73.3%, has_error 26.7% (EmptyModelResponseError from model)
- The EmptyModelResponseError is a qwen3-8b behavior, not an env bug

### Endpoints
- `qwen3-8b` added to `configs/endpoints.toml` (model: `qwen/qwen3-8b`)

### Hub
- Username: `lswamina`
- Public Hub URL: https://app.primeintellect.ai/dashboard/environments/lswamina/connections
- Hub ID: `lswamina/connections`
- Training config: `configs/rl/connections.toml`

### Commands
```bash
prime env install connections
prime env push --path environments/connections --visibility PUBLIC  # republish after changes
prime eval run connections -m qwen/qwen3-8b -n 5       # smoke
prime eval run connections -m qwen/qwen3-8b -n 50 -r 1 -s  # medium eval
prime train run configs/rl/connections.toml            # start RL training
```
