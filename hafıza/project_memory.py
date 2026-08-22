import os
import json
import time

class ProjectMemoryL2:
    """
    Project-level static memory (L2).
    Stores architecture rules, decisions, goals, and constraints in a structured JSON file 
    inside the project's .ghost directory (.ghost/project_memory.json).
    This ensures that these rules are version controlled and travel with the code.
    """
    
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.ghost_dir = os.path.join(root_dir, ".ghost")
        self.file_path = os.path.join(self.ghost_dir, "project_memory.json")
        
    def _ensure_dir(self):
        if not os.path.exists(self.ghost_dir):
            os.makedirs(self.ghost_dir, exist_ok=True)
            
    def load(self) -> dict:
        """Loads the project memory. Returns an empty default structure if it doesn't exist."""
        if not os.path.exists(self.file_path):
            return self._get_default_schema()
            
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all keys exist
                default = self._get_default_schema()
                for k, v in default.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            print(f"[ProjectMemoryL2] Hata: {e}")
            return self._get_default_schema()

    def save(self, data: dict):
        """Saves the project memory to the JSON file."""
        self._ensure_dir()
        data["updated_at"] = int(time.time())
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ProjectMemoryL2] Kaydetme hatası: {e}")

    def _get_default_schema(self) -> dict:
        return {
            "architecture": [],
            "decisions": [],
            "current_goals": [],
            "known_errors": [],
            "constraints": [],
            "updated_at": 0
        }
        
    def add_item(self, category: str, item: str):
        """Adds a new string item to a specific category."""
        data = self.load()
        if category in data and isinstance(data[category], list):
            if item not in data[category]:
                data[category].append(item)
                self.save(data)
                
    def remove_item(self, category: str, item: str):
        """Removes an item from a specific category."""
        data = self.load()
        if category in data and isinstance(data[category], list):
            if item in data[category]:
                data[category].remove(item)
                self.save(data)

    def get_formatted_context(self) -> str:
        """Returns the project memory formatted as a string for LLM context."""
        data = self.load()
        
        has_content = any(len(data.get(k, [])) > 0 for k in ["architecture", "decisions", "current_goals", "known_errors", "constraints"])
        if not has_content:
            return ""
            
        context = "### PROJECT L2 MEMORY (STATIC RULES & CONTEXT) ###\n"
        
        if data.get("architecture"):
            context += "- Architecture & Stack:\n"
            for item in data["architecture"]:
                context += f"  * {item}\n"
                
        if data.get("decisions"):
            context += "- Key Decisions:\n"
            for item in data["decisions"]:
                context += f"  * {item}\n"
                
        if data.get("constraints"):
            context += "- Constraints & Rules:\n"
            for item in data["constraints"]:
                context += f"  * {item}\n"
                
        if data.get("current_goals"):
            context += "- Current Goals:\n"
            for item in data["current_goals"]:
                context += f"  * {item}\n"
                
        if data.get("known_errors"):
            context += "- Known Errors & Workarounds:\n"
            for item in data["known_errors"]:
                context += f"  * {item}\n"
                
        return context
