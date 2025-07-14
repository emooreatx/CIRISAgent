# Type Safety Action Plan

## Immediate Actions (This Week)

### 1. Fix Remaining Processor Types
```python
# In main_processor.py
context: ProcessorContext = ProcessorContext(origin="wakeup_async")

# In dma_orchestrator.py  
triaged: TriagedData = TriagedData()
```

### 2. Enable Type Checking in CI
```yaml
# .github/workflows/ci.yml
- name: Type Check
  run: |
    python -m mypy ciris_engine/ --config-file mypy.ini
    python -m ciris_mypy_toolkit analyze
```

### 3. Fix Critical Type Ignores
- Review all 85 `# type: ignore` comments
- Replace with proper typing where possible
- Document why ignores are necessary

## Next Sprint (Week 2)

### 1. Service Response Standardization
- Create `ServiceResponse[T]` generic type
- Standardize all service return types
- Remove remaining Any imports

### 2. Schema Migration
- Update 1175 schema compliance issues
- Create migration scripts
- Version all schemas

### 3. Protocol Compliance
- Ensure all services implement protocols correctly
- Add protocol tests
- Document protocol patterns

## Long-term Goals (Month)

### 1. Zero Dict[str, Any]
- Replace all 184 remaining occurrences
- Create linting rules
- Add pre-commit hooks

### 2. Full MyPy Compliance
- Fix all 423 remaining errors
- Enable stricter settings
- Achieve 100% type coverage

### 3. Performance Optimization
- Profile Pydantic validation overhead
- Optimize hot paths
- Consider compiled validators

## Metrics to Track

1. **Weekly**
   - Dict[str, Any] count
   - MyPy error count
   - Test pass rate

2. **Monthly**
   - Type coverage percentage
   - Security scan results
   - Performance benchmarks

## Success Criteria

- [ ] Zero Dict[str, Any] in production code
- [ ] Zero HIGH/CRITICAL security issues
- [ ] 100% test pass rate
- [ ] < 100 mypy errors
- [ ] Type checking in CI/CD

## Team Guidelines

1. **Code Reviews**
   - Reject new Dict[str, Any] usage
   - Require type annotations
   - Check for proper Pydantic usage

2. **Development**
   - Run mypy before committing
   - Use TYPE_SAFETY_REPORT.md patterns
   - Document type decisions

3. **Testing**
   - Test type validations
   - Test error cases
   - Benchmark performance