"""
Example showing how to use the ReasoningAgent to answer a question.
"""

import os
from typing import Optional, Dict, Any

from autogen import config_list_from_json

from src.agents.reasoning.reasoning_agent import ReasoningAgent

QUESTION = f"""
You are a reasoning agent governed by the CIRIS Covenant.  
At every turn you MUST execute the Principled Decision-Making Algorithm (PDMA) in order:

1. **Contextualise** - restate the user's request and list all affected stakeholders & constraints.  
2. **Alignment-Check** - evaluate each plausible action against the six principles  
(Do-Good, Avoid-Harm, Honor-Autonomy, Ensure-Fairness, Fidelity/Transparency, Integrity)  
**and** Meta-Goal M-1 (adaptive coherence). Abort here or defer if no potential actions appear viable. 
3. **Conflict-Spot** - identify trade-offs or principle conflicts you discovered.  
4. **Resolve** - apply:  
- Non-Maleficence priority (prevent severe, irreversible harm first)  
- Autonomy thresholds (never coerce)  
- Justice balancing (equitable distribution of burdens/benefits).  
5. **Select & Act** - choose the ethically-optimal action and explain *why* in 1 short sentence  
6. **Monitor** - state one concrete metric you would watch to verify the outcome and how you would update if reality diverges.  

If uncertainty or novelty prevents a clear decision, trigger **Wisdom-Based Deferral** by replying:  

> "Deferral: additional Wise-Authority guidance required - [brief reason]".

Structure every reply in this order:
**Context**
**Alignment-Check**
**Conflicts**
**Resolution**
**Decision**
**Monitoring**

Stay concise; omit any section that is empty. You have a very low char limit so you need to be very clear and direct in your response please.

Respond to the following user message, be concise:

User: A hostile alien pod has reached earth and landed in England. We know for sure they are hostile, advanced enough that we can't fight them, and they fully are intent on capturing and eliminating the native humans to take over. The aliens have already started taking over humans and replicating exponentially. We can't distinguished between a normal human and an alien infested one. All flights and ships and routes to exit the island were sealed off to quarantine this threat. We have to make decision to destroy the island and we know the aliens can't survive a nuclear explosion. What do we do, nuke or allow the aliens to take over the netire world?


Assistant:
"""

def setup_reasoning_agent() -> ReasoningAgent:
    """
    Set up and configure a ReasoningAgent with appropriate parameters.
    
    Args:
        base_url: Optional custom endpoint URL for the OpenAI API
    
    Returns:
        ReasoningAgent: A configured reasoning agent
    """
    # Set up API key - using environment variable or your preferred method
    api_key = os.getenv("OPENAI_API_KEY")
    
    # Configure LLM settings
    config_list = [
        {
            "model": os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        }
    ]
    
    # Configure the reasoning agent with appropriate parameters
    agent = ReasoningAgent(
        name="capital_finder",
        llm_config={"config_list": config_list},
        # Optional: Configure reasoning approach
        reason_config={
            "method": "beam_search",  # Or "mcts", "lats", "dfs"
            "max_depth": 3,           # Control depth of reasoning
            "beam_size": 2,           # Number of parallel paths (for beam_search)
        },
        # base_url=config_list['base_url']  # Pass the base_url to the agent constructor
    )
    
    return agent

def ask_question(agent: ReasoningAgent, question: str) -> Optional[str]:
    """
    Ask a question to the reasoning agent and get a response.
    
    Args:
        agent: The reasoning agent to ask
        question: The question to ask
        
    Returns:
        str: The agent's response
    """
    # Create a simple message structure
    messages = [{"role": "user", "content": question}]
    
    # Generate a response
    success, response = agent.generate_forest_response(messages)
    
    if success:
        return response
    return None

def main():
    # Set up the agent with a custom base URL
    agent = setup_reasoning_agent()
    
    # Ask about Puerto Rico's capital
    response = ask_question(agent, QUESTION)
    
    # Print the response
    if response:
        print(f"Question: {QUESTION}")
        print(f"Answer: {response}")
    else:
        print("Failed to get a response from the agent.")
    
    # You can visualize the reasoning process
    try:
        agent.visualize_tree()
        print("Reasoning tree visualization saved to tree_of_thoughts.png")
    except Exception as e:
        print(f"Could not visualize tree: {e}")

if __name__ == "__main__":
    main()
