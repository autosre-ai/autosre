# Demo Walkthrough Examples

This directory contains resources for the OpenSRE demo.

## Contents

### Terminal Session Recordings

To record terminal sessions for documentation:

```bash
# Install asciinema
pip install asciinema

# Record a demo session
asciinema rec opensre-demo.cast

# Run the demo
python demo.py --scenario 1

# Stop recording: Ctrl+D

# Play back
asciinema play opensre-demo.cast
```

### Screenshots

Key screenshots to capture:

1. **Alert Screen** - The initial alert panel with severity colors
2. **Signal Collection** - Observer agent gathering data
3. **AI Analysis** - The LLM's root cause analysis
4. **Action Prompt** - Human-in-the-loop approval UI
5. **Summary Table** - Results from all scenarios

### Creating GIFs

Convert asciinema recordings to GIFs:

```bash
# Install agg (asciinema gif generator)
cargo install --git https://github.com/asciinema/agg

# Convert to GIF
agg opensre-demo.cast opensre-demo.gif
```

Or use a web service:
- https://asciinema.org - Upload and share
- https://gifmaker.me - Convert video to GIF

## Demo Assets

| File | Description |
|------|-------------|
| `scenario1-memory-leak.cast` | Terminal recording of memory leak scenario |
| `scenario2-database.cast` | Terminal recording of DB connection issue |
| `all-scenarios-summary.png` | Screenshot of summary table |
| `opensre-demo.gif` | Animated demo GIF for README |

## Quick Demo Commands

```bash
# Full interactive demo
python demo.py

# Single scenario (non-interactive)
python demo.py --scenario 1 --quick

# All scenarios with summary
python demo.py --all

# Using different LLM providers
python demo.py --provider openai
python demo.py --provider anthropic

# Mock mode (no LLM required - perfect for demos)
python demo.py --mock

# Run diagnostics
python demo.py --diag

# Export results to JSON
python demo.py --all --quick --export results.json
```

## Recording Tips

1. **Clean Terminal**: Clear history and use a minimal prompt
   ```bash
   export PS1="\[\033[1;36m\]opensre\[\033[0m\] $ "
   clear
   ```

2. **Increase Font Size**: 16-18pt for visibility
   
3. **Disable Line Wrapping**: Set terminal to 120x30 minimum

4. **Pause Before Actions**: Give viewers time to read

5. **Highlight Key Outputs**: Use mouse cursor or annotations
