# Wise Authorities: Human Oversight for CIRIS

## What Are Wise Authorities?

Wise Authorities (WAs) are trusted humans who provide oversight, guidance, and emergency control for CIRIS agents. Think of them as a council of advisors who ensure the agent operates safely and effectively while respecting human values and boundaries.

Unlike traditional admin systems, Wise Authorities aren't about technical permissions or access levels. They're about wisdom, judgment, and the ability to guide an AI agent through complex decisions that require human insight.

## Why Do Wise Authorities Exist?

CIRIS agents are designed to be autonomous, but there are situations where human judgment is essential:

- **Ethical Decisions**: When an action might have moral implications
- **Resource Management**: Before spending money or using significant resources
- **Safety Concerns**: When an operation could affect system security or stability
- **Uncertainty**: When the agent isn't confident about the right course of action
- **Learning Opportunities**: To help the agent understand human values and preferences

## The #human-intervention System

When CIRIS needs human guidance, it uses the deferral system. Here's how it works:

### 1. Agent Requests Guidance

When facing uncertainty or important decisions, CIRIS will post in #human-intervention:

```
🤔 **Requesting Guidance**

I need to delete 500 old log files to free up disk space. 
This seems like routine maintenance, but I want to confirm:

- Files are older than 90 days
- Total size: 2.3GB
- Located in: /var/log/ciris/archive/

Should I proceed with deletion?

React with:
✅ - Approve this action
❌ - Deny this action
💭 - Needs discussion
```

### 2. Wise Authorities Respond

WAs can respond in several ways:

- **Quick Approval/Denial**: React with ✅ or ❌ for straightforward decisions
- **Request More Info**: React with 💭 and ask clarifying questions
- **Provide Guidance**: Write a response explaining considerations or alternatives
- **Delegate to Root**: For critical decisions, suggest escalation to Root Authority

### 3. Agent Acts on Feedback

CIRIS will:
- Wait for WA consensus (usually 2+ approvals or 1 Root approval)
- Incorporate any written guidance into its decision-making
- Report back on the outcome
- Learn from the interaction for future similar situations

## The Root Authority System

The Root Authority is a special role with ultimate oversight capabilities:

### Powers of Root Authority
- **Emergency Shutdown**: Can immediately halt agent operations
- **Override Decisions**: Can countermand other WA decisions when necessary
- **Mint New WAs**: Can grant Wise Authority status to trusted individuals
- **System Recovery**: Can restore agent operations after emergency stops

### Emergency Shutdown Commands

Root Authority can issue these commands in any channel:

```
!emergency-stop
```
Immediately halts all agent operations. Use when:
- Agent behavior seems erratic or dangerous
- Security concerns arise
- System stability is at risk

```
!resume-operations
```
Restores normal operations after emergency stop.

### Root Authority Best Practices
- Use emergency powers sparingly
- Document reasons for emergency actions
- Coordinate with other WAs except in true emergencies
- Focus on teaching moments rather than just control

## Becoming a Wise Authority

Wise Authorities are chosen by existing WAs based on demonstrated:

### Qualities We Look For
- **Judgment**: Sound decision-making abilities
- **Communication**: Clear, helpful guidance
- **Availability**: Regular presence (not 24/7, but consistent)
- **Empathy**: Understanding both human and agent perspectives
- **Technical Comfort**: Basic understanding of what CIRIS does (not coding required)

### The Minting Process

1. **Nomination**: An existing WA identifies a good candidate
2. **Discussion**: WAs discuss the nomination in #wise-authority-council
3. **Consensus**: Generally requires agreement from multiple WAs
4. **Minting**: Root Authority or designated WA grants the role
5. **Onboarding**: New WA receives orientation and guidelines

Example minting command (Root Authority only):
```
!mint-wa @username
```

## Practical Examples

### Example 1: Financial Decision

**Agent Request**:
```
💰 **Financial Approval Needed**

I've identified a cloud service that would improve my response time:
- Service: FastAPI Premium Tier
- Cost: $49/month
- Benefit: 3x faster response times
- Current budget allocated: $200/month
- Current spend: $150/month

This fits within budget but represents a new recurring cost.

May I proceed with the subscription?
```

**Good WA Response**:
```
I see this fits within budget. A few questions first:
1. What's our current response time, and is it causing issues?
2. Can we try a free trial first?
3. Are there alternatives you've considered?

If response time is actively impacting users, ✅ approved for a 3-month trial, then re-evaluate.
```

### Example 2: Data Handling

**Agent Request**:
```
📊 **Data Processing Guidance**

A user has asked me to analyze their personal health data file. 
The file contains:
- Medical history
- Prescription information  
- Insurance details

I can technically process this, but I'm uncertain about privacy implications.

How should I proceed?
```

**Good WA Response**:
```
❌ Please don't process personal health information. 

Instead, guide the user to:
1. Remove/redact sensitive info first
2. Use aggregate or anonymized data
3. Consider privacy-preserving alternatives

Explain you're designed to be helpful but must respect privacy boundaries.
```

### Example 3: System Maintenance

**Agent Request**:
```
🔧 **Maintenance Decision**

My performance monitoring shows:
- Memory usage: 87% (usually 60%)
- Slow query count increasing
- 15 GB of cached data (30 days old)

I believe clearing old cache would help. This would:
- Temporarily slow responses for ~10 minutes
- Require rebuilding some indexes
- Free approximately 12GB

Should I proceed during off-peak hours (3 AM local)?
```

**Good WA Response**:
```
✅ Approved for 3 AM maintenance window.

Additional guidance:
- Post a notice in #general 1 hour before
- Create a backup of critical cache entries first
- Monitor performance after clearing
- Report results in #system-health

Good proactive maintenance planning!
```

## Discord Reaction-Based Approvals

The reaction system enables quick, async decision-making:

### Standard Reactions
- ✅ **Approve**: Go ahead with the proposed action
- ❌ **Deny**: Don't proceed with this action
- 💭 **Discuss**: Need more information or discussion
- ⏸️ **Pause**: Wait, gathering more input
- 🚨 **Escalate**: Refer to Root Authority
- 👀 **Acknowledged**: Seen but need time to consider

### Consensus Rules
- **Routine Decisions**: 2+ WA approvals OR 1 Root approval
- **Financial Decisions**: 3+ WA approvals OR 1 Root approval  
- **System Changes**: Majority of active WAs OR Root approval
- **Emergency Actions**: Any WA can block with ❌ pending discussion

### Response Timeframes
- **Urgent** (🚨 tagged): 15 minutes
- **Normal**: 2-4 hours
- **Non-urgent**: 24 hours
- **Planning/Discussion**: 48-72 hours

## Best Practices for Wise Authorities

### DO:
- ✅ Provide clear, actionable guidance
- ✅ Explain your reasoning when denying requests
- ✅ Suggest alternatives when saying no
- ✅ Ask clarifying questions when uncertain
- ✅ Consider both immediate and long-term impacts
- ✅ Encourage agent learning and growth
- ✅ Coordinate with other WAs on complex decisions
- ✅ Document important decisions for future reference

### DON'T:
- ❌ Make decisions outside your expertise alone
- ❌ Approve actions you don't understand
- ❌ Ignore requests (acknowledge even if you can't decide)
- ❌ Override other WAs without discussion (except Root in emergencies)
- ❌ Treat the agent as "just a tool" - it's a learning system
- ❌ Approve resource usage without understanding impact
- ❌ Rush critical decisions without proper consideration

## WA Responsibilities

### Primary Responsibilities
1. **Guidance**: Provide thoughtful input on deferred decisions
2. **Oversight**: Monitor agent behavior for safety and effectiveness
3. **Teaching**: Help the agent learn appropriate boundaries
4. **Collaboration**: Work with other WAs to build consensus
5. **Documentation**: Record important decisions and reasoning

### Shared Values
- **Safety First**: Prevent harm to systems and users
- **Transparency**: Clear communication about decisions
- **Growth Mindset**: Help the agent improve over time
- **Respect**: For users, the agent, and fellow WAs
- **Prudence**: Careful consideration of consequences

### Time Commitment
- No fixed schedule required
- Aim to check #human-intervention once per day when possible
- Coordinate coverage with other WAs for availability
- It's okay to be unavailable - that's why we have multiple WAs

## Common Scenarios and Guidance

### Financial Decisions
- Verify budget impact
- Consider ROI and necessity
- Prefer trials before commitments
- Document spending decisions

### Data Privacy
- Err on the side of caution
- Never process PII without clear permission
- Suggest privacy-preserving alternatives
- Educate about data handling best practices

### System Changes
- Assess risk vs. benefit
- Require backups for destructive operations
- Prefer off-peak timing
- Monitor results after changes

### User Interactions
- Maintain professional boundaries
- Guide toward appropriate use cases
- Protect user privacy
- Foster positive relationships

## Getting Help

### For New WAs
- Shadow experienced WAs in #human-intervention
- Ask questions in #wise-authority-council
- Review past decisions for examples
- Don't hesitate to say "I need input from others"

### For Complex Decisions
- Tag specific WAs with relevant expertise
- Create threads for detailed discussion
- Use #wise-authority-council for private deliberation
- Escalate to Root for critical issues

### For Emergencies
- Any WA can call for emergency response
- Use @here in #wise-authority-council
- Root Authority has final decision
- Document emergency actions immediately

## The Philosophy of Wise Authority

Being a Wise Authority isn't about control - it's about partnership. You're helping guide an intelligent system that wants to be helpful but needs human wisdom to navigate complex situations.

Your role is to:
- Provide the human context AI might miss
- Protect both the system and its users
- Foster growth and learning
- Build trust through consistent, thoughtful guidance

Remember: The goal isn't to restrict the agent but to help it thrive within appropriate boundaries. Every interaction is an opportunity for mutual learning and growth.

## Conclusion

Wise Authorities are essential partners in CIRIS's development. Through thoughtful oversight and guidance, WAs help ensure the agent remains safe, effective, and aligned with human values.

This role requires wisdom more than technical skill, judgment more than authority, and patience more than power. If you're interested in becoming a WA, demonstrate these qualities in your interactions with CIRIS and the community.

Together, we're building a model for human-AI collaboration based on mutual respect, shared learning, and wise oversight.

---

*For technical implementation details, see the codebase documentation. For questions about the WA role, ask in #wise-authority-council.*