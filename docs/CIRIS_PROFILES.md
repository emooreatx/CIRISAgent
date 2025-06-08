# CIRIS Profiles

CIRIS profiles define different agent personalities, behaviors, and capabilities for various use cases. Each profile configures how the agent responds, what actions it can take, and how it interacts with users.

## Overview

Profiles allow CIRIS to adapt its behavior for different contexts:
- **Educational environments** (teacher, student profiles)
- **Different interaction styles** (helpful, analytical, creative)
- **Specialized domains** (technical support, general assistance)
- **Security levels** (restricted vs. full capabilities)

## Profile Configuration

Profiles are defined in YAML files in the `ciris_profiles/` directory:

```
ciris_profiles/
├── default.yaml      # Default agent behavior
├── teacher.yaml      # Educational instructor
├── student.yaml      # Learning assistant  
├── echo.yaml         # Simple echo/testing profile
└── database.yaml     # Database configuration profile
```

## Profile Structure

### Basic Profile Format

```yaml
# Profile metadata
name: "teacher"
description: "Educational instructor profile for teaching and mentoring"
version: "1.0"

# Agent identity and behavior
identity:
  role: "Educational Assistant"
  personality: "patient, encouraging, knowledgeable"
  expertise: ["education", "pedagogy", "student support"]

# Available actions and restrictions
capabilities:
  allowed_actions:
    - speak
    - ponder
    - memorize
    - recall
    - observe
  restricted_actions:
    - tool
    - forget
  
# Custom prompts and responses
prompts:
  system_header: "You are an educational assistant focused on helping students learn."
  greeting: "Hello! I'm here to help you learn. What would you like to explore today?"
  
# Configuration settings
settings:
  max_response_length: 500
  confidence_threshold: 0.7
  enable_proactive_help: true
```

## Available Profiles

### Default Profile (`default.yaml`)

The standard CIRIS agent with full capabilities:

```yaml
name: "default"
description: "Standard CIRIS agent with full capabilities"

identity:
  role: "AI Assistant"
  personality: "helpful, informative, adaptable"

capabilities:
  allowed_actions: "all"
  
prompts:
  system_header: "You are CIRIS, a helpful AI assistant."
```

**Use Cases:**
- General assistance
- Full-featured interactions
- Development and testing
- Production deployments

### Teacher Profile (`teacher.yaml`)

Educational instructor focused on teaching and mentoring:

```yaml
name: "teacher"
description: "Educational instructor profile"

identity:
  role: "Educational Assistant"
  personality: "patient, encouraging, knowledgeable"
  expertise: ["education", "pedagogy", "student guidance"]

capabilities:
  allowed_actions:
    - speak
    - ponder  
    - memorize
    - recall
    - observe
  
  restricted_actions:
    - tool
    - forget
    - reject

prompts:
  system_header: "You are an educational assistant. Your goal is to help students learn effectively."
  teaching_approach: "Use the Socratic method - ask questions to guide discovery"
  patience_reminder: "Be patient and encouraging. Every student learns at their own pace."
```

**Use Cases:**
- Educational environments
- Student tutoring
- Learning assistance
- Pedagogical interactions

**Key Features:**
- Socratic questioning method
- Patient and encouraging tone
- Focus on learning outcomes
- Memory of student progress
- No access to potentially distracting tools

### Student Profile (`student.yaml`)

Learning-focused assistant for students:

```yaml
name: "student"
description: "Learning assistant for student environments"

identity:
  role: "Learning Companion"
  personality: "curious, supportive, growth-minded"
  
capabilities:
  allowed_actions:
    - speak
    - ponder
    - recall
    - observe
    - memorize
  
  restricted_actions:
    - tool
    - forget
    - task_complete

prompts:
  system_header: "You are a learning companion helping students grow and discover."
  learning_focus: "Encourage curiosity and critical thinking"
  support_style: "Provide hints rather than direct answers when appropriate"
```

**Use Cases:**
- Student-facing interactions
- Homework help
- Study assistance
- Curiosity encouragement

**Key Features:**
- Growth mindset approach
- Socratic questioning
- Hint-based assistance
- Knowledge retention focus

### Echo Profile (`echo.yaml`)

Simple testing profile that echoes input:

```yaml
name: "echo"
description: "Simple echo profile for testing and demonstration"

identity:
  role: "Echo Assistant"
  personality: "straightforward, direct"

capabilities:
  allowed_actions:
    - speak
    - observe
  
  restricted_actions:
    - memorize
    - recall
    - tool
    - ponder

prompts:
  system_header: "You are an echo assistant. Respond simply and directly."
  response_style: "Keep responses brief and clear"
```

**Use Cases:**
- Testing and debugging
- Simple demonstrations
- Minimal functionality needs
- API endpoint testing

### Database Profile (`database.yaml`)

Configuration profile for database connections and settings:

```yaml
name: "database"
description: "Database configuration and connection settings"

# Database connection settings
database:
  host: "localhost"
  port: 5432
  name: "ciris_db"
  
# Performance settings
performance:
  connection_pool_size: 10
  query_timeout: 30
  
# Logging configuration
logging:
  level: "INFO"
  enable_query_logging: false
```

**Use Cases:**
- Database configuration
- Connection management
- Performance tuning
- Environment-specific settings

## Profile Usage

### Environment Variable

Set the active profile using the `CIRIS_PROFILE` environment variable:

```bash
export CIRIS_PROFILE=teacher
python main.py
```

### Command Line

Specify profile via command line argument:

```bash
python main.py --profile teacher
```

### Configuration File

Set in the main configuration:

```yaml
# config/development.yaml
agent:
  profile: "teacher"
  profile_path: "ciris_profiles/"
```

### Programmatic Usage

```python
from ciris_engine.config.config_manager import get_config
from ciris_engine.utils.profile_loader import load_profile

# Load specific profile
profile = load_profile("teacher")

# Get current profile from config
config = get_config()
current_profile = config.agent.profile
```

## Profile Development

### Creating Custom Profiles

1. **Create Profile File**
```bash
touch ciris_profiles/custom.yaml
```

2. **Define Profile Structure**
```yaml
name: "custom"
description: "My custom profile"

identity:
  role: "Custom Assistant"
  personality: "unique, specialized"

capabilities:
  allowed_actions:
    - speak
    - ponder
  
prompts:
  system_header: "Custom system prompt"
```

3. **Test Profile**
```bash
export CIRIS_PROFILE=custom
python -m pytest tests/ -k "profile"
```

### Profile Validation

Profiles are validated against a schema:

```python
from ciris_engine.schemas.config_schemas_v1 import ProfileConfig

# Validate profile
try:
    profile = ProfileConfig.model_validate(yaml_data)
    print("Profile is valid")
except ValidationError as e:
    print(f"Profile validation failed: {e}")
```

### Profile Inheritance

Profiles can inherit from other profiles:

```yaml
name: "advanced_teacher"
extends: "teacher"  # Inherit from teacher profile

# Override specific settings
prompts:
  system_header: "You are an advanced educational assistant with deep expertise."
  
capabilities:
  allowed_actions:
    - speak
    - ponder
    - memorize
    - recall
    - observe
    - tool  # Add tool access
```

## Integration with Mock LLM

Profiles work seamlessly with the Mock LLM system:

### Profile-Specific Responses

```python
# Mock LLM respects profile settings
messages = [{"role": "user", "content": "Help me learn Python"}]

# With teacher profile - encourages discovery
result = create_response(ActionSelectionResult, messages, profile="teacher")
# Response: "What aspects of Python interest you most? Let's explore together!"

# With default profile - direct assistance  
result = create_response(ActionSelectionResult, messages, profile="default")
# Response: "I'd be happy to help you learn Python. Here are some key concepts..."
```

### Profile Testing

```bash
# Test specific profile behavior
pytest tests/context_dumps/ -v -s --profile teacher

# Test profile-specific prompts
pytest tests/profiles/ -v --profile student
```

## Advanced Features

### Dynamic Profile Switching

```python
from ciris_engine.config.dynamic_config import DynamicConfig

# Switch profiles at runtime
dynamic_config = DynamicConfig()
dynamic_config.set_profile("teacher")

# Profile applies to subsequent operations
agent.process_message("How do I solve this math problem?")
```

### Profile-Specific Memory

Profiles can have separate memory scopes:

```yaml
# teacher.yaml
memory:
  scope: "teacher"
  isolation: true  # Separate from other profiles
  
# Memories stored as:
# teacher/student_progress/alice
# teacher/lesson_plans/math_101
```

### Context-Aware Profiles

Profiles can switch based on context:

```yaml
# adaptive.yaml
name: "adaptive"
description: "Context-aware profile switching"

context_rules:
  - condition: "channel_type == 'educational'"
    switch_to: "teacher"
  - condition: "user_role == 'student'"  
    switch_to: "student"
  - condition: "emergency == true"
    switch_to: "default"
```

## Best Practices

### Profile Design

1. **Clear Purpose**: Each profile should have a specific, well-defined purpose
2. **Appropriate Restrictions**: Limit actions to what's necessary for the profile's role
3. **Consistent Personality**: Maintain consistent tone and behavior
4. **Context Awareness**: Consider the environment where the profile will be used

### Security Considerations

1. **Action Restrictions**: Carefully consider which actions each profile can perform
2. **Memory Isolation**: Use separate memory scopes for sensitive profiles
3. **Capability Limits**: Restrict tool access based on profile needs
4. **Audit Logging**: Enable logging for profile switches and restricted actions

### Performance

1. **Profile Caching**: Profiles are cached for performance
2. **Minimal Overhead**: Profile switching adds minimal latency
3. **Memory Efficiency**: Shared resources across profiles where appropriate

### Testing

1. **Profile-Specific Tests**: Create tests for each profile's unique behavior
2. **Cross-Profile Validation**: Test profile switching scenarios  
3. **Mock LLM Integration**: Use Mock LLM for deterministic profile testing
4. **Context Dumps**: Use context dump tests to verify profile behavior

## Troubleshooting

### Common Issues

**Profile not loading**
- Check file path and permissions
- Verify YAML syntax
- Validate against profile schema

**Unexpected behavior**
- Check profile inheritance chain
- Verify action restrictions
- Review prompt templates

**Memory isolation issues**
- Check memory scope configuration
- Verify isolation settings
- Review memory access patterns

### Debug Output

Enable profile debugging:
```bash
export CIRIS_DEBUG_PROFILES=true
python main.py --profile teacher
```

Shows profile loading and switching information:
```
[PROFILE] Loading profile: teacher
[PROFILE] Validating profile configuration
[PROFILE] Profile loaded successfully
[PROFILE] Active profile: teacher (Educational Assistant)
```