# Discord WebSocket 530 Diagnostic Tools

Comprehensive diagnostic suite for troubleshooting Discord WebSocket 530 errors ("Session no longer valid"). These tools provide automated diagnosis, guided troubleshooting, and detailed analysis to resolve authentication and connection issues.

## Overview

The diagnostic suite consists of three complementary tools:

1. **Quick Decision Tree** (`discord-530-decision-tree.py`) - Interactive guided troubleshooting
2. **Comprehensive Analysis** (`diagnose-discord-530-comprehensive.py`) - Deep diagnostic investigation
3. **Master Controller** (`discord-530-master.py`) - Unified workflow orchestration

## Quick Start

```bash
# Run complete diagnostic workflow (recommended)
python scripts/discord-530-master.py

# Quick guided troubleshooting only
python scripts/discord-530-decision-tree.py

# Deep comprehensive analysis only
python scripts/diagnose-discord-530-comprehensive.py
```

## Tool Details

### 🤖 Quick Decision Tree (`discord-530-decision-tree.py`)

Interactive troubleshooting that guides you through step-by-step diagnosis.

**Features:**
- Automated checks for common issues
- Guided decision-making process
- Immediate actionable recommendations
- Quick resolution for straightforward problems

**Use when:**
- You need fast results
- The issue might be simple (token, multiple instances, etc.)
- You prefer guided troubleshooting

```bash
python scripts/discord-530-decision-tree.py
```

**Output:** Interactive prompts with immediate recommendations

### 🔬 Comprehensive Analysis (`diagnose-discord-530-comprehensive.py`)

Deep investigation with 5 specialized diagnostic modules.

**Modules:**
1. **Bot Application Status** - Token validation, gateway limits, bot info
2. **Environment & Network** - DNS, connectivity, platform detection
3. **Instance & Session Detection** - Multiple processes, containers, port conflicts
4. **Rate Limiting & IP Investigation** - Rate limits, VPS detection, timing analysis
5. **Code & Configuration Audit** - Intent settings, discord.py version, code issues

**Use when:**
- Complex or unknown issues
- Need detailed technical analysis
- VPS deployment troubleshooting
- Preparing comprehensive reports

```bash
python scripts/diagnose-discord-530-comprehensive.py
```

**Output:** Detailed JSON report with structured findings

### 🚀 Master Controller (`discord-530-master.py`)

Unified workflow that intelligently combines both tools.

**Intelligent Workflow:**
1. Runs quick diagnosis first
2. Automatically determines if deep analysis is needed
3. Generates unified recommendations from all sources
4. Provides final summary with next steps

**Modes:**
- `auto` (default) - Quick + comprehensive as needed
- `quick` - Decision tree only
- `comprehensive` - Deep analysis only
- `guided` - Interactive mode

```bash
# Auto mode (recommended)
python scripts/discord-530-master.py

# Specific modes
python scripts/discord-530-master.py --mode quick
python scripts/discord-530-master.py --mode comprehensive
python scripts/discord-530-master.py --mode guided
```

## Common Issues Diagnosed

### ✅ Token Issues
- Missing or invalid Discord bot token
- Token format validation
- Authentication failures

### ✅ Session Limits
- Gateway session exhaustion
- Session cleanup problems
- Limit monitoring

### ✅ Multiple Instances
- Duplicate bot processes
- Docker container conflicts
- Port usage conflicts

### ✅ Configuration Problems
- Missing privileged intents
- Outdated discord.py version
- Multiple bot.run() calls
- Intent mismatches

### ✅ Network Issues
- DNS resolution problems
- Firewall/proxy blocking
- VPS-specific connectivity issues
- Rate limiting detection

### ✅ Environment Detection
- Local vs Docker vs VPS
- Platform-specific optimizations
- Resource constraints

## Prerequisites

### Required Python Packages
```bash
pip install aiohttp psutil websockets discord.py requests
```

Or install full project requirements:
```bash
pip install -r requirements.txt
```

### Environment Setup
```bash
# Ensure Discord token is available
export DISCORD_TOKEN="your_bot_token_here"

# Or create .env file
echo "DISCORD_TOKEN=your_bot_token_here" > .env
```

## Usage Examples

### Example 1: Complete Diagnosis
```bash
# Run comprehensive workflow
python scripts/discord-530-master.py

# Review generated reports
ls discord-530-*.json
```

### Example 2: Quick Token Check
```bash
# Quick validation only
python scripts/discord-530-decision-tree.py
# Follows guided steps automatically
```

### Example 3: VPS Troubleshooting
```bash
# Force comprehensive analysis for VPS
python scripts/discord-530-master.py --mode comprehensive

# Check VPS-specific recommendations
grep -i "vps" discord-530-*.json
```

### Example 4: CI/CD Integration
```bash
# Non-interactive mode for automation
python scripts/diagnose-discord-530-comprehensive.py > diagnostic-report.txt
echo $?  # Check exit code: 0=OK, 1=issues, 2=error
```

## Output Files

All tools generate timestamped JSON reports:

- `discord-530-master-YYYYMMDD-HHMMSS.json` - Complete workflow results
- `discord-530-quick-YYYYMMDD-HHMMSS.json` - Decision tree findings
- `discord-530-comprehensive-YYYYMMDD-HHMMSS.json` - Detailed analysis

### Sample Output Structure
```json
{
  "timestamp": "2025-01-27T10:30:00Z",
  "summary": {
    "authentication_status": "OK",
    "environment_type": "VPS",
    "critical_issues": [],
    "warnings": ["Multiple instances detected"]
  },
  "recommendations": [
    {
      "priority": "HIGH",
      "category": "Multiple Instances",
      "actions": ["Stop all instances: pkill -f robustty", "..."]
    }
  ]
}
```

## Exit Codes

- `0` - Success, no critical issues
- `1` - Issues found, action required
- `2` - Diagnostic error or failure
- `130` - User interrupted (Ctrl+C)

## Advanced Usage

### Verbose Debugging
```bash
python scripts/discord-530-master.py --verbose
```

### Skip File Output
```bash
python scripts/discord-530-master.py --no-save
```

### Manual Module Testing
```bash
# Test individual components
python -c "
import sys; sys.path.append('scripts')
exec(open('scripts/discord-530-decision-tree.py').read())
"
```

## Integration with Project

### CLAUDE.md Integration
These tools are referenced in the main project documentation:

```bash
# From CLAUDE.md - VPS Deployment & Validation
./scripts/validate-pre-deployment.sh              # Run before using diagnostics
python scripts/discord-530-master.py              # Run 530 diagnostics
```

### Docker Integration
```bash
# Run inside Docker container
docker-compose exec robustty python scripts/discord-530-master.py

# Check container-specific issues
docker-compose exec robustty python scripts/diagnose-discord-530-comprehensive.py
```

## Troubleshooting the Diagnostics

### Import Errors
```bash
# Install missing packages
pip install aiohttp psutil websockets

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

### Permission Issues
```bash
# Make scripts executable
chmod +x scripts/discord-530-*.py

# Check file permissions
ls -la scripts/discord-530-*.py
```

### Network Issues
```bash
# Test basic connectivity first
ping discord.com
curl -I https://discord.com/api/v10/gateway
```

## Development

### Adding New Checks
1. Add check function to appropriate module
2. Update decision tree logic if needed
3. Add to comprehensive analysis modules
4. Update master controller workflow

### Testing
```bash
# Syntax check
python -m py_compile scripts/discord-530-*.py

# Import test
python -c "
import scripts/discord-530-decision-tree as dt
import scripts/diagnose-discord-530-comprehensive as comp
print('All imports successful')
"
```

## Support

For issues with the diagnostic tools:

1. Check this README for common solutions
2. Review generated diagnostic reports
3. Run with `--verbose` for detailed debugging
4. Check Discord status: https://discordstatus.com
5. Consult main project documentation in CLAUDE.md

---

**Note:** These tools are designed to diagnose Discord WebSocket 530 errors specifically. For other Discord API issues or general bot problems, refer to the main project troubleshooting guide in CLAUDE.md.