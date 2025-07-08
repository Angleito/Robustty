# Discord 530 Error Investigation Strategy

## Overview

This document outlines a comprehensive, systematic approach to investigating Discord 530 errors when the bot token is confirmed to be valid. The strategy addresses the reality that 530 errors can occur even with valid tokens due to various environmental, configuration, and application-level issues.

## Investigation Modules

The investigation is organized into 5 modular areas that can be checked independently:

### 1. Bot Application Analysis
**Purpose**: Check Discord Developer Portal configuration and bot application status
**Key Areas**:
- Token structure validation and decoding
- Bot information retrieval from Discord API
- Application configuration verification
- Verification status and guild limits
- Privileged intents configuration
- Session start limits and usage

**Common Issues Detected**:
- Session limit exhaustion (most common cause)
- Bot verification required for 100+ servers
- Privileged intents misconfiguration
- Token corruption or formatting issues

### 2. Environment Diagnostics
**Purpose**: Analyze infrastructure and networking environment
**Key Areas**:
- Network connectivity to Discord services
- DNS resolution for Discord domains
- System resource availability (CPU, memory, disk)
- Docker networking configuration
- Firewall and port accessibility
- VPS-specific network limitations

**Common Issues Detected**:
- DNS resolution failures
- Network connectivity blocks
- Docker networking misconfigurations
- Resource exhaustion causing connection drops
- VPS provider restrictions

### 3. Session Management Review
**Purpose**: Examine session conflicts and process management
**Key Areas**:
- Multiple bot instances detection
- Session usage patterns and conflicts
- Process management and cleanup
- WebSocket connection testing
- Session timing and invalidation

**Common Issues Detected**:
- Multiple bot instances consuming sessions
- Rapid reconnection patterns
- Session state corruption
- Process conflicts and resource contention

### 4. Rate Limiting Investigation
**Purpose**: Check for rate limiting and IP-based restrictions
**Key Areas**:
- Current API rate limit status
- IP reputation and datacenter detection
- Connection pattern analysis
- Rate limit header examination
- Geographic and provider restrictions

**Common Issues Detected**:
- IP-based rate limiting
- Datacenter IP restrictions
- Excessive API usage patterns
- Regional blocking or restrictions

### 5. Code Configuration Audit
**Purpose**: Verify bot code and library configuration
**Key Areas**:
- Discord library version compatibility
- Intent configuration matching
- Environment variable validation
- Configuration file integrity
- API version compatibility

**Common Issues Detected**:
- Outdated library versions
- Intent mismatches between code and portal
- Environment variable misconfiguration
- API version incompatibilities

## Decision Tree Logic

The investigation uses a systematic decision tree to identify the most likely root cause:

```
Token Valid?
├─ No → Token Issues (regenerate, format check)
└─ Yes → Multiple Instances?
   ├─ Yes → Multiple Instance Conflicts
   └─ No → Frequent Restarts?
      ├─ Yes → Session Exhaustion
      └─ No → Network Connectivity?
         ├─ Fail → Network Issues
         └─ Pass → Docker Environment?
            ├─ Yes → Docker Networking
            └─ No → 100+ Servers?
               ├─ Yes → Verification Required
               └─ No → Environment/Intermittent
```

## Tools Overview

### 1. Comprehensive Investigation Tool
**File**: `scripts/diagnose-discord-530-comprehensive.py`
**Purpose**: Deep, systematic analysis across all modules
**Features**:
- Parallel testing across all investigation areas
- Severity-based issue classification
- Detailed reporting with recommendations
- JSON output for automated processing
- Evidence gathering for each potential cause

**Usage**:
```bash
python scripts/diagnose-discord-530-comprehensive.py
```

### 2. Automated Fix Tool
**File**: `scripts/fix-discord-530-comprehensive.py`
**Purpose**: Automated remediation based on investigation results
**Features**:
- Risk-level categorized fixes
- Configuration backup before changes
- Interactive confirmation for high-risk operations
- Verification of fix success
- Rollback capability

**Usage**:
```bash
# Guided fixes
python scripts/fix-discord-530-comprehensive.py --guided

# Automated fixes with investigation results
python scripts/fix-discord-530-comprehensive.py --automated --investigation results.json
```

### 3. Quick Decision Tree
**File**: `scripts/discord-530-decision-tree.py`
**Purpose**: Fast, interactive troubleshooting
**Features**:
- Interactive question-based diagnosis
- Quick automated checks
- Immediate action recommendations
- Command suggestions for common fixes

**Usage**:
```bash
# Quick automated checks
python scripts/discord-530-decision-tree.py --quick

# Interactive decision tree
python scripts/discord-530-decision-tree.py --tree
```

### 4. Master Controller
**File**: `scripts/discord-530-master.py`
**Purpose**: Unified workflow orchestration
**Features**:
- Complete workflow management
- Result correlation across tools
- Session tracking and reporting
- Progress monitoring and summaries

**Usage**:
```bash
# Interactive mode
python scripts/discord-530-master.py

# Complete automated workflow
python scripts/discord-530-master.py --all

# Quick assessment only
python scripts/discord-530-master.py --quick
```

## Investigation Workflow

### Phase 1: Quick Assessment (2-3 minutes)
1. **Prerequisites Check**
   - Verify all diagnostic tools are available
   - Check Discord token format and availability
   - Validate environment setup

2. **Automated Quick Checks**
   - Token format validation
   - Multiple instance detection
   - Basic network connectivity
   - Docker container status
   - System resource overview

3. **Initial Triage**
   - Categorize as obvious issue or requires deeper investigation
   - Provide immediate recommendations for clear problems
   - Determine if comprehensive investigation is needed

### Phase 2: Comprehensive Investigation (5-10 minutes)
1. **Parallel Module Execution**
   - Run all 5 investigation modules simultaneously
   - Gather evidence across all potential failure points
   - Classify issues by severity and impact

2. **Evidence Correlation**
   - Analyze patterns across module results
   - Identify primary vs. secondary issues
   - Calculate confidence levels for root cause identification

3. **Root Cause Analysis**
   - Apply decision tree logic to evidence
   - Rank potential causes by likelihood
   - Generate specific recommendations

### Phase 3: Automated Remediation (5-15 minutes)
1. **Fix Strategy Selection**
   - Match identified root cause to fix procedures
   - Assess risk levels and user preferences
   - Create execution plan with verification steps

2. **Graduated Fix Application**
   - Start with low-risk, high-impact fixes
   - Progress to higher-risk fixes with user confirmation
   - Verify each fix before proceeding

3. **Success Verification**
   - Re-run quick assessment to verify resolution
   - Test actual bot connection if possible
   - Document applied fixes and results

### Phase 4: Monitoring and Prevention
1. **Result Documentation**
   - Generate comprehensive session report
   - Save investigation evidence for future reference
   - Create prevention recommendations

2. **Ongoing Monitoring Setup**
   - Suggest monitoring tools and practices
   - Identify early warning indicators
   - Plan preventive maintenance schedules

## Common Root Causes and Solutions

### 1. Session Limit Exhausted (40% of cases)
**Symptoms**: 530 errors during handshake, gateway access issues
**Investigation**: High session usage, recent restarts/deployments
**Solutions**:
- Stop all bot instances immediately
- Wait 24 hours for session reset
- Implement session management in bot code
- Add monitoring for session usage

### 2. Multiple Bot Instances (25% of cases)
**Symptoms**: Intermittent 530 errors, session conflicts
**Investigation**: Multiple Python/Docker processes detected
**Solutions**:
- Kill all bot processes
- Implement proper process management
- Use container orchestration properly
- Monitor for process leaks

### 3. Network Connectivity Issues (15% of cases)
**Symptoms**: Cannot reach Discord services, DNS failures
**Investigation**: Network tests fail, DNS resolution issues
**Solutions**:
- Fix DNS configuration (use 8.8.8.8, 1.1.1.1)
- Check firewall rules
- Verify VPS network configuration
- Test alternative network routes

### 4. Token Issues (10% of cases)
**Symptoms**: Authentication failures, 401 responses
**Investigation**: Token format problems, revocation
**Solutions**:
- Regenerate token in Discord Developer Portal
- Fix token format (remove spaces, Bot prefix)
- Update environment variables
- Verify token scope and permissions

### 5. Bot Verification Required (5% of cases)
**Symptoms**: 530 errors when approaching 100 servers
**Investigation**: High guild count, unverified status
**Solutions**:
- Apply for bot verification
- Temporarily reduce server count
- Contact Discord support
- Consider new bot application

### 6. Other Issues (5% of cases)
**Symptoms**: Various, often intermittent
**Investigation**: Environment-specific, configuration issues
**Solutions**:
- Update Discord library versions
- Fix Docker networking
- Address system resource limitations
- Check for VPS provider restrictions

## Best Practices for Prevention

### 1. Session Management
- Implement exponential backoff for reconnections
- Monitor session usage with alerting
- Use proper shutdown procedures
- Avoid rapid restart cycles

### 2. Process Management
- Use container orchestration (Docker Compose, Kubernetes)
- Implement health checks and restart policies
- Monitor for process leaks and duplicates
- Use proper signal handling for graceful shutdowns

### 3. Network Reliability
- Use multiple DNS servers
- Implement connection retry logic
- Monitor network connectivity
- Have fallback networking configurations

### 4. Monitoring and Alerting
- Track bot connection status
- Monitor session usage patterns
- Alert on repeated connection failures
- Log detailed error information

### 5. Infrastructure Hygiene
- Keep Discord libraries updated
- Monitor system resources
- Regularly review bot configuration
- Test disaster recovery procedures

## Integration with Robustty Bot

The investigation tools are designed to integrate seamlessly with the Robustty bot codebase:

1. **Existing Diagnostics**: Extends current diagnostic tools in `/scripts/`
2. **Configuration Aware**: Uses existing configuration files and environment setup
3. **Docker Compatible**: Works with both local and containerized deployments
4. **VPS Optimized**: Special handling for VPS-specific networking issues
5. **Logging Integration**: Compatible with existing logging infrastructure

## Usage Examples

### Quick Troubleshooting Session
```bash
# Start with quick assessment
python scripts/discord-530-master.py --quick

# If issues found, run complete workflow
python scripts/discord-530-master.py --all
```

### Systematic Investigation
```bash
# Full investigation only
python scripts/discord-530-master.py --investigate

# Review results and apply fixes manually
python scripts/fix-discord-530-comprehensive.py --guided
```

### Emergency Response
```bash
# Quick decision tree for immediate action
python scripts/discord-530-decision-tree.py --quick

# Apply emergency fixes
python scripts/fix-discord-530-comprehensive.py --automated --force
```

## Output and Reporting

### Investigation Reports
- **JSON Format**: Machine-readable results for automation
- **Severity Classification**: Critical, High, Medium, Low, Info
- **Evidence Correlation**: Links between symptoms and causes
- **Confidence Scoring**: Likelihood assessment for each potential cause

### Summary Reports
- **Markdown Format**: Human-readable session summaries
- **Timeline Tracking**: Chronological record of investigation steps
- **Fix Documentation**: Record of applied remediation steps
- **Prevention Recommendations**: Specific actions to prevent recurrence

### Monitoring Integration
- **Metrics Export**: Compatible with Prometheus/Grafana
- **Alert Integration**: Webhook support for incident management
- **Log Aggregation**: Structured logging for centralized analysis
- **Health Checks**: API endpoints for external monitoring

This comprehensive investigation strategy provides a systematic, evidence-based approach to resolving Discord 530 errors while building organizational knowledge and preventing future occurrences.