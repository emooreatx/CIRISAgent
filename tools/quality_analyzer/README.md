# Quality Analyzer Tool

A unified quality analysis tool that orchestrates existing CIRIS tools to provide comprehensive code quality insights.

## Features

- **Orchestrates Existing Tools**:
  - `ciris_mypy_toolkit` - For type safety analysis and Dict[str, Any] detection
  - `sonar_tool` - For code quality metrics, coverage, and technical debt
- **Unified Prioritization**: Combines all metrics into a single priority score
- **Smart Analysis**: No crude grep - uses proper AST parsing from mypy toolkit
- **AI Time Estimates**: Realistic estimates for AI-assisted development (÷15)

## Usage

```bash
# Run unified analysis (recommended)
python -m tools.quality_analyzer

# Run cross-analysis only
python -m tools.quality_analyzer cross
```

## Output

The tool generates:

1. **Top Priority Files**: Files with multiple quality issues
2. **Categorized Actions**:
   - Type safety quick wins
   - Test coverage quick wins
   - Complexity reduction targets
3. **Impact Summary**: Total effort estimates with AI acceleration
4. **Execution Plan**: Week-by-week recommendations

## Integration

This tool complements:
- **sonar_tool**: For detailed SonarCloud analysis
- **ciris_mypy_toolkit**: For type safety compliance
- **test_tool**: For running and analyzing tests

## Example Output

```
🎯 TOP 10 PRIORITY FILES:

1. ciris_engine/persistence/graph/memory.py
   Priority Score: 48.2/100
   Issues: Complexity: 60 | Debt: 9.1h
   AI Time Estimate: 0.6 hours
```
