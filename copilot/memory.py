"""Memory module for Smart Event Planning Copilot.

This module provides persistence for user event-planning preferences,
allowing the Copilot to learn from past interactions.
"""

import os
import json
from typing import Dict, Any

DEFAULT_MEMORY_FILE = os.path.expanduser("~/.gemini/antigravity-ide/smart_event_copilot_memory.json")

class MemoryManager:
    """Manages user preferences stored in a local JSON file."""

    def __init__(self, filepath: str = DEFAULT_MEMORY_FILE):
        self.filepath = filepath
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self.preferences = self._load()

    def _load(self) -> Dict[str, Any]:
        """Loads preferences from disk."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save(self) -> None:
        """Saves current preferences to disk."""
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.preferences, f, indent=4)
        except Exception as e:
            print(f"Error saving memory file: {e}")

    def update_preference(self, key: str, value: Any) -> str:
        """Updates a specific preference and saves it."""
        valid_keys = [
            "preferred_city", 
            "event_type", 
            "budget_preferences", 
            "venue_preferences", 
            "guest_count_preferences"
        ]
        if key not in valid_keys:
            return f"Error: '{key}' is not a valid preference key. Choose from {valid_keys}."
        
        self.preferences[key] = value
        self.save()
        return f"Successfully updated user preference: {key} = {value}."

    def clear(self) -> str:
        """Clears all stored preferences."""
        self.preferences = {}
        self.save()
        return "All stored event planning preferences have been cleared."

    def get_all(self) -> Dict[str, Any]:
        """Gets all stored preferences."""
        return self.preferences

    def format_as_instruction(self) -> str:
        """Formats stored preferences as instructions for the agent's context."""
        if not self.preferences:
            return ""
        
        instruction_lines = ["\n[USER PREFERENCES RETRIEVED FROM MEMORY]"]
        # NOTE: preferred_city is intentionally excluded — the agent must NOT assume
        # a default city. Location must always come from the user's prompt.
        if "event_type" in self.preferences:
            instruction_lines.append(f"- Preferred Event Type: {self.preferences['event_type']}")
        if "budget_preferences" in self.preferences:
            instruction_lines.append(f"- Budget Class/Preferences: {self.preferences['budget_preferences']}")
        if "venue_preferences" in self.preferences:
            instruction_lines.append(f"- Venue Styles/Preferences: {self.preferences['venue_preferences']}")
        if "guest_count_preferences" in self.preferences:
            instruction_lines.append(f"- Default/Preferred Guest Count: {self.preferences['guest_count_preferences']}")
        instruction_lines.append("Use these user preferences if not explicitly overridden by the prompt.\n")
        instruction_lines.append("IMPORTANT: Do NOT assume or default the event location/city. "
                                 "Only use a location if it is explicitly mentioned in the user's prompt.\n")
        
        return "\n".join(instruction_lines)


# Singleton memory manager instance
_memory_manager = MemoryManager()

# Custom tools that agents can call
def save_user_preference(key: str, value: str) -> str:
    """Saves a user preference (e.g. event type, budget class) to persistent memory.

    Args:
        key: The preference field. Choose from: 'event_type',
             'budget_preferences', 'venue_preferences', 'guest_count_preferences'.
             Do NOT save 'preferred_city' — location must come from the user's prompt.
        value: The value to store (e.g. 'Luxury Weddings', 'INR 50,000', 'Rooftop').
    """
    return _memory_manager.update_preference(key, value)

def load_user_preferences() -> Dict[str, Any]:
    """Retrieves all saved user planning preferences from persistent memory.
    
    Returns:
        A dictionary containing all saved preferences.
    """
    return _memory_manager.get_all()
