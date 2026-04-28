# Demo Assets

This directory should contain the demo GIF and screenshots for the README.

## Required Files

### `autosre-demo.gif`
The main demo GIF for the README. To create:

1. Run the demo script: `python demo.py`
2. Record with a tool like:
   - **macOS**: Built-in screen recording or [Gifox](https://gifox.io/)
   - **Linux**: [Peek](https://github.com/phw/peek), [Byzanz](https://github.com/GNOME/byzanz)
   - **Cross-platform**: [Terminalizer](https://github.com/faressoft/terminalizer)

3. Optimize the GIF:
   ```bash
   # Using gifsicle
   gifsicle -O3 --colors 256 autosre-demo.gif -o autosre-demo-optimized.gif
   ```

### Recommended Settings
- Terminal size: 120x30
- Font size: 16pt
- Theme: Dark (Dracula, One Dark, or similar)
- Duration: 30-60 seconds

## Creating with Terminalizer

```bash
# Install
npm install -g terminalizer

# Record
terminalizer record autosre-demo

# Play back to verify
terminalizer play autosre-demo

# Render to GIF
terminalizer render autosre-demo
```

## Screenshots Needed

- `autosre-status.png` - Output of `autosre status`
- `autosre-eval.png` - Output of `autosre eval run`
- `autosre-context.png` - Output of `autosre context show`

## Current Status

⚠️ Demo GIF is pending recording. The README references this file but it doesn't exist yet.

To record, follow the [DEMO_SCRIPT.md](../../DEMO_SCRIPT.md) for guidance.
