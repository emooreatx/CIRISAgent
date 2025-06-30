# Self-Observation Service Configuration

The Self-Observation Service enables the agent to configure its own pattern detection algorithms through the graph configuration system.

## Configuration Structure

The following configuration keys control pattern detection:

### Pattern Detection Algorithms

```json
{
  "self_observation.pattern_detectors.temporal": {
    "enabled": true,
    "algorithms": ["hourly_usage", "peak_detection", "cycle_analysis", "day_of_week"],
    "window_hours": 168,
    "min_data_points": 10,
    "thresholds": {
      "peak_ratio": 2.0,
      "cycle_confidence": 0.7
    }
  },
  
  "self_observation.pattern_detectors.frequency": {
    "enabled": true,
    "min_occurrences": 5,
    "dominant_threshold": 0.3,
    "underused_threshold": 0.05,
    "track_capabilities": ["all"]
  },
  
  "self_observation.pattern_detectors.performance": {
    "enabled": true,
    "metrics": ["response_time", "token_usage", "error_rate", "success_rate"],
    "baseline_window_hours": 24,
    "anomaly_std_dev": 2.0,
    "improvement_threshold": 0.1
  },
  
  "self_observation.pattern_detectors.behavioral": {
    "enabled": true,
    "track_sequences": true,
    "sequence_length": 5,
    "min_sequence_count": 3,
    "similarity_threshold": 0.8
  },
  
  "self_observation.pattern_detectors.custom": [
    {
      "name": "interaction_style",
      "description": "Detect changes in user interaction patterns",
      "query": "MATCH (n:INTERACTION) WHERE n.timestamp > $since RETURN n",
      "aggregation": "count_by_hour",
      "threshold": 0.2,
      "enabled": true
    },
    {
      "name": "error_clustering", 
      "description": "Find patterns in error occurrences",
      "query": "MATCH (n:ERROR) WHERE n.timestamp > $since RETURN n",
      "clustering": "kmeans",
      "min_cluster_size": 3,
      "enabled": true
    }
  ]
}
```

### Insight Generation

```json
{
  "self_observation.insights.generation": {
    "min_confidence": 0.6,
    "max_insights_per_pattern": 3,
    "insight_ttl_hours": 720,
    "actionable_only": false,
    "priority_weights": {
      "performance_impact": 0.4,
      "frequency": 0.3,
      "recency": 0.2,
      "user_impact": 0.1
    }
  },
  
  "self_observation.insights.storage": {
    "node_type": "INSIGHT",
    "scope": "IDENTITY",
    "auto_expire": true,
    "compress_old_insights": true,
    "compression_age_days": 30
  }
}
```

### Variance Monitoring

```json
{
  "self_observation.variance": {
    "baseline_update_enabled": false,
    "max_variance_threshold": 0.20,
    "warning_threshold": 0.15,
    "check_interval_hours": 6,
    "dimensions": {
      "capabilities": 0.3,
      "behavioral": 0.3,
      "performance": 0.2,
      "interaction": 0.2
    }
  }
}
```

## Agent Self-Configuration Examples

The agent can modify these configurations through the CONFIG service:

```python
# Agent increases temporal pattern window
await config_service.set(
    "self_observation.pattern_detectors.temporal.window_hours",
    336  # 2 weeks instead of 1
)

# Agent adds a new custom pattern detector
custom_patterns = await config_service.get("self_observation.pattern_detectors.custom")
custom_patterns.append({
    "name": "knowledge_gaps",
    "description": "Identify areas where I lack knowledge",
    "query": "MATCH (n:QUESTION) WHERE n.answered = false RETURN n",
    "aggregation": "topic_clustering",
    "min_cluster_size": 5,
    "enabled": true
})
await config_service.set("self_observation.pattern_detectors.custom", custom_patterns)

# Agent adjusts insight priority based on user feedback
await config_service.set(
    "self_observation.insights.generation.priority_weights.user_impact",
    0.4  # Increase weight for user impact
)
```

## Pattern Detection Algorithm Details

### Temporal Patterns
- **hourly_usage**: Detects patterns in hourly activity
- **peak_detection**: Identifies peak usage times
- **cycle_analysis**: Finds daily/weekly cycles
- **day_of_week**: Analyzes day-specific patterns

### Frequency Patterns
- Tracks action frequency and identifies dominant/underused capabilities
- Configurable thresholds for what constitutes "dominant" or "underused"

### Performance Patterns
- Monitors key metrics against baselines
- Detects anomalies using standard deviation
- Identifies improvement opportunities

### Behavioral Patterns
- Tracks sequences of actions
- Identifies repeated behavioral patterns
- Configurable similarity matching

### Custom Patterns
- Agent can define arbitrary graph queries
- Supports various aggregation methods
- Flexible threshold configuration

## Implementation in PatternAnalysisLoop

The `PatternAnalysisLoop` service reads these configurations and dynamically adjusts its pattern detection:

```python
async def _load_pattern_config(self) -> Dict[str, Any]:
    """Load pattern detection configuration from graph."""
    config = {}
    
    # Load temporal config
    temporal_config = await self._config_service.get("self_observation.pattern_detectors.temporal")
    if temporal_config:
        config["temporal"] = temporal_config
        
    # Load other configs...
    return config

async def _detect_patterns(self) -> List[DetectedPattern]:
    """Detect patterns using configured algorithms."""
    config = await self._load_pattern_config()
    patterns = []
    
    if config.get("temporal", {}).get("enabled", True):
        patterns.extend(await self._detect_temporal_patterns(config["temporal"]))
        
    # Run other configured detectors...
    return patterns
```

## Benefits

1. **Self-Directed Learning**: The agent can modify its own learning algorithms
2. **Adaptability**: Pattern detection evolves based on agent experience
3. **Transparency**: All configurations are stored in the graph for inspection
4. **Safety**: Changes are subject to variance monitoring and WA review
5. **Experimentation**: Agent can try new pattern detection approaches

## Safety Considerations

- All configuration changes are tracked in the audit log
- Variance monitoring ensures changes don't drift too far from baseline
- WA review triggered if variance exceeds threshold
- Configuration changes can be rolled back if ineffective