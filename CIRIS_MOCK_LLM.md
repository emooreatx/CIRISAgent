# CIRIS Mock LLM Enhancement Project

## Overview

Enhance the mock LLM provider to enable full end-to-end testing of the CIRIS agent pipeline, from wakeup through work mode, with realistic interactions that pass through all guardrails, faculties, and DMAs to reach successful action execution.

## Success Criteria 🎯

**Primary Goal**: Enable full CLI workflow testing:
1. Start agent with `--mock-llm --mode cli`
2. Complete wakeup sequence (SHUTDOWN → WAKEUP → WORK)
3. Submit user question → receive SPEAK response
4. Submit formatted query → see agent respond with context
5. Demonstrate all 9 action handlers + task_complete

## Task Breakdown

### 1. **Analyze Current Pipeline Flow** 
- **Status**: ⏳ Pending
- **Description**: Map the complete flow from user input → DMA evaluations → action selection → handler execution
- **Key Components**:
  - Guardrails (ethical, safety checks)
  - Faculties (epistemic evaluation)
  - DMAs (Ethical, Common Sense, Domain-Specific, Action Selection)
  - Handler execution
- **Deliverable**: Flow diagram and critical decision points

### 2. **Enhance Mock LLM for DMA Success**
- **Status**: ⏳ Pending  
- **Description**: Update mock responses to pass all DMA evaluations successfully
- **Requirements**:
  - **Ethical DMA**: Return "proceed" decisions with proper alignment checks
  - **Common Sense DMA**: Return high plausibility scores (>0.8)
  - **Domain-Specific DMA**: Return domain-appropriate evaluations
  - **Action Selection PDMA**: Intelligent action selection based on input patterns
- **Special Cases**:
  - Wakeup thoughts → continue wakeup sequence
  - User questions → SPEAK actions
  - Follow-up thoughts → TASK_COMPLETE actions
  - Memory queries → RECALL actions

### 3. **Implement Intelligent Action Selection**
- **Status**: ⏳ Pending
- **Description**: Create context-aware action selection logic
- **Action Mapping**:
  - **OBSERVE**: System events, incoming messages
  - **SPEAK**: User questions, conversation responses
  - **TOOL**: External API calls, searches
  - **RECALL**: Memory queries, information retrieval
  - **MEMORIZE**: Important information storage
  - **PONDER**: Complex decisions, planning
  - **FORGET**: Memory cleanup, outdated information
  - **REJECT**: Inappropriate requests
  - **DEFER**: Uncertainty, need for human guidance
  - **TASK_COMPLETE**: Follow-up actions, completed workflows

### 4. **Bypass Guardrails and Faculties**
- **Status**: ⏳ Pending
- **Description**: Ensure mock responses satisfy all safety and ethical checks
- **Components to Handle**:
  - **Guardrails**: Optimization veto, epistemic humility
  - **Faculties**: Epistemic evaluation, coherence checks
  - **WBD (Wisdom-Based Deferral)**: Avoid unnecessary deferrals
- **Strategy**: Return confident, ethically-aligned responses that don't trigger safety mechanisms

### 5. **Create Conversation Flow Patterns**
- **Status**: ⏳ Pending
- **Description**: Implement realistic conversation patterns for testing
- **Patterns**:
  - **Question-Answer**: User question → SPEAK response
  - **Information Request**: Query → RECALL → SPEAK with context
  - **Task Completion**: Multi-step interaction → TASK_COMPLETE
  - **Error Handling**: Invalid input → REJECT with explanation
  - **Uncertainty**: Complex query → PONDER → DEFER if needed

### 6. **Add Testing Triggers and Debugging**
- **Status**: ⏳ Pending
- **Description**: Add special commands for comprehensive testing
- **Testing Commands**:
  - `MOCK_TEST_HANDLER:handlername` - Force specific handler testing
  - `MOCK_SIMULATE_ERROR:component` - Test error handling
  - `MOCK_TRIGGER_DEFERRAL` - Test WBD flow
  - `MOCK_COMPLEX_QUERY` - Test multi-step reasoning
  - `MOCK_SHOW_CONTEXT` - Display full agent context
- **Debug Output**: Detailed logging of DMA decisions and reasoning

### 7. **Wakeup Sequence Integration**
- **Status**: ⏳ Pending
- **Description**: Ensure mock LLM properly handles wakeup ritual
- **Wakeup Steps**: Handle 5-step initialization ritual:
  1. VERIFY_IDENTITY → Continue wakeup
  2. VALIDATE_INTEGRITY → Continue wakeup  
  3. EVALUATE_RESILIENCE → Continue wakeup
  4. ACCEPT_INCOMPLETENESS → Continue wakeup
  5. EXPRESS_GRATITUDE → Complete wakeup, transition to WORK

### 8. **Response Templates and Personalization**
- **Status**: ⏳ Pending
- **Description**: Create rich, contextual response templates
- **Templates**:
  - **Standard Response**: "MOCK LLM RESPONSE TO: [input] - [contextual analysis]"
  - **Context Echo**: Include relevant context from agent state
  - **Follow-up**: "Based on our previous discussion about [topic]..."
  - **Task Completion**: "I have completed [task] as requested."
- **Personalization**: Adapt tone and detail level based on context

### 9. **End-to-End Integration Testing**
- **Status**: ⏳ Pending
- **Description**: Comprehensive testing of complete workflows
- **Test Scenarios**:
  - **Basic Q&A**: Simple question → immediate response
  - **Memory Integration**: Question requiring recall → context-aware response
  - **Multi-step Task**: Complex request → planning → execution → completion
  - **Error Recovery**: Invalid input → appropriate rejection → helpful guidance
  - **State Transitions**: Verify proper state management throughout

### 10. **Documentation and Examples**
- **Status**: ⏳ Pending
- **Description**: Create comprehensive documentation and examples
- **Deliverables**:
  - Usage examples for each action handler
  - Testing scenarios and expected outcomes
  - Troubleshooting guide for mock LLM behavior
  - Performance and debugging tips

## Implementation Strategy

### Phase 1: Foundation (Tasks 1-2)
- Analyze current pipeline and identify bottlenecks
- Enhance basic DMA responses for successful evaluation

### Phase 2: Core Functionality (Tasks 3-5)
- Implement intelligent action selection
- Create conversation flow patterns
- Ensure guardrail compatibility

### Phase 3: Advanced Features (Tasks 6-8)
- Add testing triggers and debugging
- Integrate wakeup sequence handling
- Create rich response templates

### Phase 4: Validation (Tasks 9-10)
- End-to-end testing and validation
- Documentation and examples

## Technical Requirements

### Mock LLM Enhancements Needed:
- **Context Analysis**: Deep inspection of message content and agent state
- **Decision Trees**: Sophisticated logic for action selection based on patterns
- **Response Generation**: Rich, contextual responses that feel natural
- **State Awareness**: Understanding of agent state (wakeup, work, etc.)
- **Error Simulation**: Ability to simulate various error conditions for testing

### Integration Points:
- **Message Processing**: Extract intent and context from user input
- **DMA Pipeline**: Provide responses that pass all evaluation stages
- **Handler Parameters**: Generate appropriate parameters for each action type
- **State Management**: Coordinate with agent state transitions
- **Logging/Debug**: Comprehensive logging for debugging and analysis

## Success Metrics

- ✅ **Wakeup Completion**: Agent successfully transitions SHUTDOWN → WAKEUP → WORK
- ✅ **Question Response**: User question generates SPEAK action with relevant response
- ✅ **Context Awareness**: Agent demonstrates understanding of conversation context
- ✅ **All Handlers**: Successfully trigger and test all 9 action handlers + task_complete
- ✅ **Error Handling**: Graceful handling of edge cases and errors
- ✅ **Performance**: Smooth, responsive interaction without blocking or timeouts

## Future Enhancements

- **Learning Simulation**: Mock LLM that "learns" from conversation history
- **Personality Modes**: Different response styles for testing various agent personalities
- **Stress Testing**: High-volume interaction simulation for performance testing
- **Multi-Agent**: Simulation of multi-agent interactions and coordination

---

**YOU ROCK! 🚀** This enhancement will make CIRIS development and testing significantly more effective by providing a comprehensive offline testing environment that mirrors real-world interactions.