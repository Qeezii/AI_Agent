import json
import os
import time
from typing import List, Dict, Any, Optional

class ShortTermMemory:
    """Краткосрочная память: скользящее окно сообщений."""
    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self.messages: List[Dict[str, str]] = []

    def add(self, message: Dict[str, str]):
        self.messages.append(message)
        if len(self.messages) > self.max_size:
            self.messages = self.messages[-self.max_size:]

    def get_recent(self, n: Optional[int] = None) -> List[Dict[str, str]]:
        if n is None:
            n = self.max_size
        return self.messages[-n:]

    def clear(self):
        self.messages = []

    def to_dict(self) -> dict:
        return {"messages": self.messages, "max_size": self.max_size}

    def load_dict(self, data: dict):
        self.messages = data.get("messages", [])
        self.max_size = data.get("max_size", 20)


class WorkingMemory:
    """Рабочая память: структурированные данные текущей задачи (ключ-значение)."""
    def __init__(self):
        self.data: Dict[str, Any] = {}

    def set(self, key: str, value: Any):
        self.data[key] = value

    def get(self, key: str) -> Any:
        return self.data.get(key)

    def update_from_dict(self, updates: Dict[str, Any]):
        self.data.update(updates)

    def clear(self):
        self.data = {}

    def to_dict(self) -> dict:
        return self.data

    def load_dict(self, data: dict):
        self.data = data

    def format_for_prompt(self) -> str:
        if not self.data:
            return "Нет данных текущей задачи."
        lines = [f"{k}: {v}" for k, v in self.data.items()]
        return "\n".join(lines)


class LongTermMemory:
    """Долговременная память: профиль пользователя, предпочтения, решения."""
    def __init__(self):
        self.facts: List[Dict[str, Any]] = []  # каждый факт: {"type": "preference", "content": "...", "timestamp": ...}
        self.profile: Dict[str, Any] = {       # информация о пользователе
            "name": "Пользователь",
            "role": "инженер",
            "expertise_level": "средний",     # новичок, средний, эксперт
            "preferred_style": "лаконичный",  # подробный, лаконичный, технический, простой
            "format_preference": "список",    # абзацы, маркированные пункты, список
            "constraints": [],                # список ограничений (например, "не использовать сложные термины")
        }

    def add_fact(self, fact_type: str, content: str):
        self.facts.append({
            "type": fact_type,
            "content": content,
            "timestamp": time.time()
        })

    def add_profile_info(self, key: str, value: Any):
        self.profile[key] = value

    def get_all_facts(self) -> List[str]:
        return [f"{f['type']}: {f['content']}" for f in self.facts]

    def format_for_prompt(self) -> str:
        parts = []
        if self.profile:
            profile_lines = [f"  {k}: {v}" for k, v in self.profile.items() if k != "constraints" or v]
            if self.profile.get("constraints"):
                profile_lines.append(f"  constraints: {', '.join(self.profile['constraints'])}")
            parts.append("Профиль пользователя:\n" + "\n".join(profile_lines))
        if self.facts:
            parts.append("Известные факты:\n" + "\n".join(f"  {f['type']}: {f['content']}" for f in self.facts))
        return "\n".join(parts) if parts else "Нет долговременной информации."

    def clear(self):
        # Не сбрасываем профиль полностью, а только факты
        self.facts = []

    def to_dict(self) -> dict:
        return {"facts": self.facts, "profile": self.profile}

    def load_dict(self, data: dict):
        self.facts = data.get("facts", [])
        self.profile = data.get("profile", {
            "name": "Пользователь",
            "role": "инженер",
            "expertise_level": "средний",
            "preferred_style": "лаконичный",
            "format_preference": "список",
            "constraints": [],
        })