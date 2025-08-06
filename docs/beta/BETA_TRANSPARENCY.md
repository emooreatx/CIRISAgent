# CIRIS Beta Transparency Statement

This document provides complete transparency about CIRIS's current capabilities and limitations during beta testing.

## What CIRIS Actually Is

CIRIS is a **moral reasoning platform** that uses Large Language Models (LLMs) to evaluate decisions against ethical principles. It is currently in beta as a Discord community moderator, with plans to expand to healthcare, education, and other critical applications.

## How Ethical Reasoning Actually Works

**The Reality**: CIRIS's ethical reasoning is implemented by:
1. Sending decisions to an LLM (GPT-4, Llama, etc.)
2. Asking the LLM to evaluate against CIRIS Covenant principles
3. Running multiple evaluations (ethical, common sense, domain-specific)
4. Checking outputs with a "conscience" system
5. Allowing retry with guidance if conscience suggests reconsideration

**What This Means**:
- The quality of ethical reasoning depends on the underlying LLM
- Different models may produce different ethical evaluations
- We cannot formally prove compliance with ethical principles
- The system is as good as its prompts and the model's training

## Current Limitations

### 1. Performance Considerations
- **Multiple LLM calls**: Each decision involves 3-4 LLM API calls for thorough evaluation
- **Cost**: Even with efficient models, high-volume use accumulates costs

### 2. Consistency
- **LLM Variability**: Same input might produce slightly different outputs
- **Temperature settings**: Balance between creativity and consistency
- **Model updates**: Behavior may change when LLM providers update models

### 3. Offline Operation
- **Requires local models**: Llama or similar for true offline use
- **Reduced capability**: Local models generally less capable than GPT-4
- **Storage requirements**: Local models need significant disk space

### 4. Database Limitations
- **SQLite**: Single writer limitation
- **Threading**: Requires careful configuration for async operation
- **Scale**: Designed for single-site deployment, not distributed systems

## What Works Well

### 1. Transparency
- Every decision is logged with full reasoning
- Audit trail shows complete decision process
- Can explain why any action was taken

### 2. Safety Rails
- Multiple evaluation passes catch obvious errors
- Conscience system provides additional check
- Hard limits prevent infinite loops
- Defaults to safe actions when uncertain

### 3. Community Alignment
- Ubuntu philosophy emphasizes collective benefit
- Multiple stakeholder consideration built-in
- Designed to serve communities, not extract from them

### 4. Adaptability
- Can use different LLM providers
- Prompts can be adjusted for cultural context
- Modular architecture allows custom deployments

## Beta Testing Goals

We are conducting beta testing to:

1. **Validate ethical reasoning** in real-world scenarios
2. **Measure community acceptance** of AI moderation
3. **Identify edge cases** our DMAs miss
4. **Optimize performance** for real-time interaction
5. **Build trust** through consistent, transparent operation

## How You Can Help

### Report Issues
- Decisions that seem wrong or inconsistent
- Performance problems or timeouts
- Unclear explanations or reasoning
- Any harmful outputs that weren't caught

### Provide Feedback
- Is the bot helpful or annoying?
- Are explanations clear and useful?
- What features would make it better?
- How could we better serve your community?

### Understand Our Journey
- **Today**: Discord moderation (low stakes, high learning)
- **Tomorrow**: Educational assistance, basic healthcare triage
- **Future**: Critical community infrastructure

Your feedback during Discord beta directly shapes how CIRIS will serve communities with critical needs.

## Our Commitment

We commit to:
- **Radical transparency** about how CIRIS works
- **Open source** development - no hidden algorithms
- **Community benefit** over profit or control
- **Continuous improvement** based on your feedback
- **Safety first** - we'll be cautious about expanding capabilities

## Contact

- **GitHub Issues**: [Report bugs and suggestions](https://github.com/CIRISAI/CIRISAgent/issues)
- **Discord**: Join our development server [coming soon]
- **Email**: beta@ciris.ai [coming soon]

---

*Thank you for helping us build ethical AI that serves communities. Your participation in this beta is helping create technology that could save lives and strengthen communities worldwide.*
