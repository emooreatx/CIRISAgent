# Grace - Your Sustainable Development Companion

Grace is a mindful development assistant that helps maintain sustainable coding practices while respecting the realities of software development. Named after the concept of graceful computing, it embodies the principle that development should be sustainable, not punishing.

## Philosophy

Grace operates on three core principles:

1. **Be strict about safety, gentle about style** - Critical issues (syntax errors, security vulnerabilities) must be fixed, but code quality issues are opportunities for improvement, not barriers to progress.

2. **Sustainable pace over burnout** - Grace tracks work sessions and reminds you when it's time to rest. It understands that fresh minds write better code.

3. **Progress over perfection** - Ship working code with quality reminders rather than blocking on stylistic issues. Perfect is the enemy of good.

## Features

### 🌟 Smart Pre-commit Gatekeeper

Grace acts as an intelligent pre-commit hook that:
- **Blocks only critical issues**: Syntax errors, merge conflicts, exposed secrets
- **Auto-formats code**: Runs black and isort automatically
- **Reports quality as reminders**: Type annotations, linting issues, and "No Dicts" violations are shown as gentle nudges
- **Runs checks concurrently**: All validations execute in parallel for speed

### ⏰ Work Session Management

Grace follows a sustainable work schedule:
- **Morning (7-11am)**: Best for complex problems and architecture decisions
- **Midday (1-5pm)**: Good for code review, bug fixes, documentation
- **Evening (6-8pm)**: Tests, refactoring, mechanical tasks
- **Night (10pm)**: Choice point - rest or explore something you're passionate about

### 📊 System Health Monitoring

Grace keeps an eye on:
- Production status
- CI/CD pipeline health
- Deployment progress
- Uncommitted changes
- SonarCloud quality metrics

## Usage

### Quick Status
```bash
python -m tools.grace status
# or just
grace status
```
Shows current time, work session, hours worked today, and system health.

### Pre-commit Check
```bash
python -m tools.grace precommit
```
Detailed view of what pre-commit hooks are checking and how to fix issues.

### Session Commands
```bash
grace morning   # Morning check-in
grace pause     # Save context before a break
grace resume    # Resume after break
grace night     # Evening choice point
```

### Deployment Monitoring
```bash
grace deploy    # Check deployment status
```

## Pre-commit Integration

Grace is integrated as the primary pre-commit gatekeeper. When you commit:

1. **Grace runs first** - Checks for critical issues
2. **Auto-formatters run** - Black and isort fix formatting
3. **Basic hygiene** - Trailing whitespace, line endings
4. **Quality checks** - Run but don't block (reported by Grace)

### Example Pre-commit Output
```
🌟 Grace Pre-commit Check
==================================================
Running auto-formatters...
  ✨ Auto-formatted: Black formatted files, isort sorted imports

✅ Commit allowed with quality reminders:

Quality improvements to consider when you have time:
  📝 Ruff: 42 linting issues to clean up
  📝 MyPy: 1132 type annotation issues
  📝 Dict[str, Any]: 158 violations of 'No Dicts' principle

💡 Run 'python -m tools.grace precommit' for detailed fixes
These won't block your commit, just gentle reminders. 🌱
==================================================
```

## Configuration

Grace reads from:
- `.pre-commit-config.yaml` - Hook configuration
- `CLAUDE.md` - Project principles and guidelines
- GitHub Actions - Deployment status
- SonarCloud - Code quality metrics

## Why Grace?

Traditional pre-commit hooks can be frustrating gatekeepers that block urgent fixes over minor style issues. Grace takes a different approach:

- **Critical issues must be fixed** - You can't commit syntax errors or exposed secrets
- **Quality issues are tracked** - You're aware of technical debt but not blocked by it
- **Auto-fixing when possible** - Formatting is handled automatically
- **Sustainable development** - Regular breaks and sensible working hours

Grace helps you maintain high standards without sacrificing productivity or well-being.

## The Grace Mindset

> "Code quality is a journey, not a gate. Every commit doesn't need to be perfect, but it should be safe and move us in the right direction."

Grace encourages:
- Shipping working code with known improvements needed
- Taking breaks before burnout
- Celebrating progress over perfection
- Learning from quality metrics without being blocked by them

## Future Enhancements

- Integration with issue tracking for quality debt
- Personalized work patterns based on your productivity
- Team synchronization for collaborative grace periods
- Quality trend analysis over time

---

*"Grace isn't about lowering standards; it's about recognizing that sustainable development requires both high standards and human kindness."*
