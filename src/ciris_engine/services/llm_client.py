"""LLM client for CIRIS system."""

import logging
import json
import re
from typing import Dict, Any

from openai import AsyncOpenAI # Changed import

class CIRISLLMClient:
    """Client for interacting with LLMs in the CIRIS system."""
    
    def __init__(self, api_key: str, base_url: str, model_name: str) -> None:
        """Initialize the LLM client."""
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url) # Changed to AsyncOpenAI
        self.model_name = model_name

    @staticmethod
    def extract_json(raw: str) -> Dict[str, Any]:
        """
        Extracts JSON from a string that may contain markdown formatting,
        newlines within the JSON structure, or other LLM artifacts.
        """
        if not isinstance(raw, str):
            logging.warning(f"extract_json received non-string input: {type(raw)}. Returning error.")
            return {"error": "Invalid input type to extract_json."}

        # Attempt to find JSON within markdown code blocks (```json ... ``` or ``` ... ```)
        # This regex will find the content within the first encountered JSON code block.
        # It handles optional "json" language specifier and potential leading/trailing newlines.
        match_markdown = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match_markdown:
            json_str = match_markdown.group(1)
            logging.debug(f"Found JSON in markdown: {json_str[:200]}...")
        else:
            # If no markdown block, assume the raw string might be JSON or contain it directly.
            # Attempt to find the first '{' and last '}' to bound the potential JSON object.
            # This is a common pattern for LLMs that don't use markdown fences but still output JSON.
            first_brace = raw.find('{')
            last_brace = raw.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_str = raw[first_brace : last_brace + 1]
                logging.debug(f"Attempting to parse bounded JSON: {json_str[:200]}...")
            else:
                # If no clear braces, use the original raw string cleaned of typical non-JSON prefixes/suffixes.
                # This is less reliable but provides a last attempt.
                json_str = raw.strip()
                logging.debug(f"No clear JSON structure, trying raw stripped input: {json_str[:200]}...")

        try:
            # Attempt to parse the extracted/cleaned string.
            return json.loads(json_str)
        except json.JSONDecodeError as e1:
            logging.warning(f"Initial JSONDecodeError for string '{json_str[:200]}...': {e1}")
            # Try replacing single quotes as a fallback if initial parsing fails.
            try:
                json_str_fixed_quotes = json_str.replace("'", '"')
                logging.debug(f"Retrying with single quotes replaced: {json_str_fixed_quotes[:200]}...")
                return json.loads(json_str_fixed_quotes)
            except json.JSONDecodeError as e2:
                logging.error(f"Persistent JSONDecodeError even after attempting quote fix for string '{json_str_fixed_quotes[:200]}...': {e2}")
                # Final fallback: try to find ANY valid JSON object within the raw string as a last resort.
                try:
                    best_match = None
                    # Recursive regex for balanced braces; might be slow on very long strings
                    for match in re.finditer(r"\{(?:[^{}]|(?R))*\}", raw, re.DOTALL): 
                        try:
                            candidate_json = json.loads(match.group(0))
                            if best_match is None or len(match.group(0)) > len(json.dumps(best_match)):
                                best_match = candidate_json
                        except json.JSONDecodeError:
                            continue
                    if best_match:
                        logging.warning(f"Successfully parsed JSON using recursive brace matching fallback.")
                        return best_match
                except Exception as fallback_ex: 
                     logging.error(f"Error during recursive brace matching fallback: {fallback_ex}")

                return {"error": f"Failed to parse JSON. Original error: {e1}. Quote fix error: {e2}. Raw content: {raw[:500]}..."}

    async def call_llm(self, prompt: str, max_tokens: int = 512) -> str: # Changed to async def
        """Make a raw call to the LLM.
        
        Args:
            prompt: The complete prompt to send
            max_tokens: Maximum tokens in the response
            
        Returns:
            Raw LLM response text
        """
        try:
            resp = await self.client.chat.completions.create( # Added await
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logging.exception("Error in LLM call:")
            raise e
