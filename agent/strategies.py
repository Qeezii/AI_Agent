from typing import List, Dict, Optional, TYPE_CHECKING, cast
from openai.types.chat import ChatCompletionMessageParam
if TYPE_CHECKING:
    from .agent import Agent

class Strategy:
    """Базовый класс стратегии управления контекстом."""
    def __init__(self, agent: 'Agent'):
        self.agent = agent

    def prepare_context(self, user_input: str) -> List[Dict[str, str]]:
        raise NotImplementedError

    def update_memory(self, user_input: str, assistant_response: str):
        pass

    def reset(self):
        """Сбрасывает специфичные для стратегии данные."""
        pass

    def load_state(self, state: dict):
        pass

    def save_state(self) -> dict:
        return {}

# ---------- Стратегия 1: Sliding Window ----------
class SlidingWindowStrategy(Strategy):
    def prepare_context(self, user_input: str) -> List[Dict[str, str]]:
        context = []
        if self.agent.system_instruction:
            context.append({"role": "system", "content": self.agent.system_instruction})
        messages = self.agent.messages[-self.agent.window_size:] if self.agent.window_size > 0 else []
        context.extend(messages)
        context.append({"role": "user", "content": user_input})
        return context

# ---------- Стратегия 2: Sticky Facts ----------
class StickyFactsStrategy(Strategy):
    def __init__(self, agent: 'Agent'):
        super().__init__(agent)
        self.facts: Dict[str, str] = {}
        self.facts_update_prompt = (
            "Из последнего диалога извлеки важные факты (цели, ограничения, предпочтения, решения, договорённости). "
            "Обнови существующий список фактов (ключ-значение). Верни только обновлённый список в формате:\n"
            "ключ1: значение1\nключ2: значение2\n...\nЕсли факты не изменились, верни пустую строку."
        )

    def format_facts(self) -> str:
        return "\n".join([f"{k}: {v}" for k, v in self.facts.items()])

    def _update_facts_from_messages(self, recent_messages: List[Dict[str, str]]) -> str:
        conversation = "\n".join([f"{m['role']}: {m['content']}" for m in recent_messages])
        prompt = f"{self.facts_update_prompt}\n\nТекущие факты:\n{self.format_facts()}\n\nПоследний диалог:\n{conversation}"
        try:
            response = self.agent.client.chat.completions.create(
                model=f"gpt://{self.agent.folder_id}/{self.agent.model}",
                messages=cast(List[ChatCompletionMessageParam], [{"role": "user", "content": prompt}]),
                temperature=0.2,
                max_tokens=300
            )
            answer = response.choices[0].message.content or ""
            return answer.strip()
        except Exception as e:
            print(f"⚠️ Ошибка обновления фактов: {e}")
            return ""

    def update_memory(self, user_input: str, assistant_response: str):
        recent = self.agent.messages[-6:] if len(self.agent.messages) >= 6 else self.agent.messages[:]
        recent.append({"role": "assistant", "content": assistant_response})
        new_facts_text = self._update_facts_from_messages(recent)
        if new_facts_text:
            for line in new_facts_text.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    self.facts[key.strip()] = val.strip()

    def prepare_context(self, user_input: str) -> List[Dict[str, str]]:
        context = []
        if self.agent.system_instruction:
            context.append({"role": "system", "content": self.agent.system_instruction})
        if self.facts:
            context.append({"role": "system", "content": f"Важные факты из диалога:\n{self.format_facts()}"})
        messages = self.agent.messages[-self.agent.window_size:] if self.agent.window_size > 0 else []
        context.extend(messages)
        context.append({"role": "user", "content": user_input})
        return context

    def reset(self):
        self.facts = {}

    def save_state(self) -> dict:
        return {"facts": self.facts}

    def load_state(self, state: dict):
        self.facts = state.get("facts", {})

# ---------- Стратегия 3: Branching ----------
class BranchingStrategy(Strategy):
    def __init__(self, agent: 'Agent'):
        super().__init__(agent)
        self.branches: Dict[str, List[Dict[str, str]]] = {}
        self.current_branch: str = "main"
        if "main" not in self.branches:
            self.branches["main"] = []

    def create_branch(self, name: str, from_branch: Optional[str] = None):
        if from_branch is None:
            from_branch = self.current_branch
        if from_branch not in self.branches:
            print(f"Ветка {from_branch} не существует!")
            return False
        if name in self.branches:
            print(f"Ветка {name} уже существует!")
            return False
        self.branches[name] = self.branches[from_branch].copy()
        return True

    def switch_branch(self, name: str):
        if name not in self.branches:
            print(f"Ветка {name} не существует!")
            return False
        self.current_branch = name
        self.agent.messages = self.branches[name]
        return True

    def delete_branch(self, name: str):
        if name == "main":
            print("Нельзя удалить основную ветку.")
            return False
        if name not in self.branches:
            return False
        del self.branches[name]
        if self.current_branch == name:
            self.switch_branch("main")
        return True

    def update_memory(self, user_input: str, assistant_response: str):
        pass

    def prepare_context(self, user_input: str) -> List[Dict[str, str]]:
        context = []
        if self.agent.system_instruction:
            context.append({"role": "system", "content": self.agent.system_instruction})
        context.extend(self.agent.messages)
        context.append({"role": "user", "content": user_input})
        return context

    def reset(self):
        self.branches = {"main": self.agent.messages.copy()}
        self.current_branch = "main"
        self.agent.messages = self.branches["main"]

    def save_state(self) -> dict:
        return {
            "branches": self.branches,
            "current_branch": self.current_branch
        }

    def load_state(self, state: dict):
        self.branches = state.get("branches", {"main": []})
        self.current_branch = state.get("current_branch", "main")
        if self.current_branch in self.branches:
            self.agent.messages = self.branches[self.current_branch]
        else:
            self.agent.messages = []