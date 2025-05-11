import yaml
import importlib
from typing import Type # For type hinting dsdma_cls

from ciris_engine.agent_profile import AgentProfile # Assuming AgentProfile is here
# If AgentProfile is elsewhere, adjust the import path.

def load_profile(path: str) -> AgentProfile:
    """
    Loads an agent profile from a YAML file.
    Dynamically imports the DSDMA class specified in the YAML.
    """
    with open(path, 'r') as f:
        raw = yaml.safe_load(f)
    
    mod_path, cls_name = raw["dsdma_cls"].rsplit(".", 1)
    
    try:
        module = importlib.import_module(mod_path)
        dsdma_cls: Type = getattr(module, cls_name)
    except ImportError:
        # Potentially try a relative import if the absolute one fails,
        # depending on how dsdma_cls paths are structured.
        # For now, keeping it simple.
        raise ImportError(f"Could not import DSDMA module {mod_path}")
    except AttributeError:
        raise AttributeError(f"Could not find DSDMA class {cls_name} in module {mod_path}")

    return AgentProfile(
        name=raw["name"],
        dsdma_cls=dsdma_cls,
        dsdma_kwargs=raw.get("dsdma_kwargs", {}),
        action_prompt_overrides=raw.get("action_prompt_overrides")
    )

if __name__ == '__main__':
    # Example usage (assuming student.yaml is in ../../ciris_profiles/ relative to this file if run directly)
    # This part is for testing and might need path adjustment if you run this script.
    try:
        # Adjust path for direct script execution if needed.
        # For example, if ciris_profiles is at the project root:
        # profile = load_profile("../../ciris_profiles/student.yaml")
        
        # Assuming ciris_profiles is at the same level as src when running from project root
        # For testing, let's assume a path relative to the project root
        # This example won't run as is without correct pathing for student.yaml
        # For now, just demonstrating the load_profile function structure.
        print("Profile loader defined. Example usage would require correct path to student.yaml.")
        # Example:
        # student_profile = load_profile('ciris_profiles/student.yaml') # if run from project root
        # print(f"Loaded profile: {student_profile.name}")
        # print(f"DSDMA class: {student_profile.dsdma_cls}")

    except Exception as e:
        print(f"Error during example usage: {e}")
