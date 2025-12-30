# Daily Routines

This script runs a morning briefing with reminders, weather, and other daily information.

## Automatic Execution

The daily routines are **automatically called** when you run `main.py`:

```bash
uv run python main.py
```

This displays the daily briefing at startup before entering the conversation loop.

## Manual Execution

You can also run the routines standalone:

```bash
uv run python daily_routines.py
```

## Scheduled Execution

### Using Cron (macOS/Linux)

1. Open crontab editor:
   ```bash
   crontab -e
   ```

2. Add a line to run daily at 8:00 AM:
   ```cron
   0 8 * * * cd /Users/gokhandemirtas/Projects/langbox && /path/to/uv run python daily_routines.py >> /tmp/langbox_routines.log 2>&1
   ```

3. To find the path to `uv`:
   ```bash
   which uv
   ```

4. Example with full paths:
   ```cron
   0 8 * * * cd /Users/gokhandemirtas/Projects/langbox && /Users/gokhandemirtas/.cargo/bin/uv run python daily_routines.py >> /tmp/langbox_routines.log 2>&1
   ```

### Cron Schedule Examples

```cron
# Every day at 8:00 AM
0 8 * * *

# Every weekday at 7:30 AM
30 7 * * 1-5

# Every day at 8 AM and 6 PM
0 8,18 * * *

# Every Monday at 9 AM
0 9 * * 1
```

### Using launchd (macOS Alternative)

Create `~/Library/LaunchAgents/com.langbox.dailyroutines.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.langbox.dailyroutines</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/uv</string>
        <string>run</string>
        <string>python</string>
        <string>daily_routines.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/gokhandemirtas/Projects/langbox</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/langbox_routines.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/langbox_routines.err</string>
</dict>
</plist>
```

Load the agent:
```bash
launchctl load ~/Library/LaunchAgents/com.langbox.dailyroutines.plist
```

## Current Routines

1. **Today's Reminders** - Lists all reminders scheduled for today
2. **London Weather** - Current weather and forecast for London using `query_weather()`
3. **Future Routines** (placeholder) - Space for additional routines

## Adding New Routines

To add a new routine, edit `daily_routines.py`:

```python
# Add import at the top
from handlers.your_module.handler_name import your_function

# Add routine in run_daily_routines()
print("🎯 YOUR ROUTINE NAME")
print("-" * 70)
try:
    response = await your_function(params)
    print(response)
except Exception as e:
    logger.error(f"Failed to run routine: {e}")
    print("❌ Could not complete routine")
print()
```

## Troubleshooting

### Check if cron job is running:
```bash
# View cron logs (macOS)
log show --predicate 'process == "cron"' --last 1h

# View output log
tail -f /tmp/langbox_routines.log
```

### Test MongoDB connection:
```bash
cd db && docker-compose ps
```

### Verify uv environment:
```bash
cd /Users/gokhandemirtas/Projects/langbox
uv run python -c "print('Environment OK')"
```

### Test the script:
```bash
uv run python daily_routines.py
```
