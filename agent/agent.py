import os
import json
import openai
from typing import List, Dict, cast
from openai.types.chat import ChatCompletionMessageParam
from .strategies import (
    Strategy, SlidingWindowStrategy, StickyFactsStrategy, BranchingStrategy
)
from .memory import ShortTermMemory, WorkingMemory, LongTermMemory

class Agent:
    def __init__(self, folder_id: str, api_key: str, model: str,
                 history_file: str = "data/agent_state.json",
                 window_size: int = 10,
                 system_instruction: str = ""):
        self.folder_id = folder_id
        self.model = model
        self.history_file = history_file
        self.window_size = window_size
        self.system_instruction = system_instruction
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            project=folder_id
        )
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.last_stats = (0, 0, 0)

        # Инициализация трёх слоёв памяти
        self.short_term = ShortTermMemory(max_size=window_size * 2)  # храним до 20 сообщений
        self.working = WorkingMemory()
        self.long_term = LongTermMemory()

        # Стратегии
        self.strategies: Dict[int, Strategy] = {
            1: SlidingWindowStrategy(self),
            2: StickyFactsStrategy(self),
            3: BranchingStrategy(self)
        }
        self.current_strategy_id: int = 1
        self.strategy: Strategy = self.strategies[self.current_strategy_id]

        self.load_memory()

        # Убедимся, что профиль загружен
        if not self.long_term.profile:
            self.long_term.profile = {
                "name": "Пользователь",
                "role": "инженер",
                "expertise_level": "средний",
                "preferred_style": "лаконичный",
                "format_preference": "список",
                "constraints": [],
            }
    
    def set_profile(self, **kwargs):
        """Установить одно или несколько полей профиля."""
        for key, value in kwargs.items():
            if key in self.long_term.profile:
                self.long_term.profile[key] = value
            else:
                print(f"Неизвестное поле профиля: {key}")
        self.save_memory()
        print("Профиль обновлён.")

    def get_profile(self) -> dict:
        return self.long_term.profile

    def load_profile_preset(self, preset_name: str):
        """Загрузить предустановленный профиль."""
        presets = {
            "эксперт": {
                "name": "Эксперт",
                "role": "технический специалист",
                "expertise_level": "эксперт",
                "preferred_style": "технический",
                "format_preference": "параграфы",
                "constraints": []
            },
            "новичок": {
                "name": "Новичок",
                "role": "начинающий специалист",
                "expertise_level": "низкий",
                "preferred_style": "простой",
                "format_preference": "список",
                "constraints": ["Избегайте сложных терминов", "Давайте примеры"]
            },
            "менеджер": {
                "name": "Менеджер",
                "role": "руководитель проекта",
                "expertise_level": "средний",
                "preferred_style": "лаконичный",
                "format_preference": "маркированный список",
                "constraints": ["Акцент на сроках и бюджете", "Минимум технических деталей"]
            }
        }
        if preset_name not in presets:
            print(f"Доступные пресеты: {', '.join(presets.keys())}")
            return
        self.long_term.profile.update(presets[preset_name])
        self.save_memory()
        print(f"Загружен профиль: {preset_name}")

    def load_memory(self):
        if not os.path.exists(self.history_file):
            return
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.current_strategy_id = data.get("strategy_id", 1)
            self.window_size = data.get("window_size", 10)
            self.short_term.load_dict(data.get("short_term", {}))
            self.working.load_dict(data.get("working", {}))
            self.long_term.load_dict(data.get("long_term", {}))
            strategy_state = data.get("strategy_state", {})
            self.strategy = self.strategies[self.current_strategy_id]
            self.strategy.load_state(strategy_state)
            if isinstance(self.strategy, BranchingStrategy):
                # Уже загружено через strategy.load_state
                pass
        except Exception as e:
            print(f"⚠️ Ошибка загрузки состояния: {e}")

    def save_memory(self):
        data = {
            "strategy_id": self.current_strategy_id,
            "window_size": self.window_size,
            "short_term": self.short_term.to_dict(),
            "working": self.working.to_dict(),
            "long_term": self.long_term.to_dict(),
            "strategy_state": self.strategy.save_state()
        }
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def set_strategy(self, strategy_id: int):
        if strategy_id not in self.strategies:
            print("Неверный ID стратегии.")
            return
        self.save_memory()
        self.current_strategy_id = strategy_id
        self.strategy = self.strategies[strategy_id]
        self.strategy.reset()
        if isinstance(self.strategy, BranchingStrategy):
            self.strategy.branches = {"main": self.short_term.messages.copy()}
            self.strategy.current_branch = "main"
            self.short_term.messages = self.strategy.branches["main"]
        self.save_memory()
        print(f"Стратегия изменена на {self.get_strategy_name()}")

    def get_strategy_name(self) -> str:
        names = {1: "Sliding Window", 2: "Sticky Facts", 3: "Branching"}
        return names.get(self.current_strategy_id, "Unknown")

    def clear_history(self):
        if isinstance(self.strategy, BranchingStrategy):
            self.strategy.branches[self.strategy.current_branch] = []
            self.short_term.messages = []
        else:
            self.short_term.clear()
            if isinstance(self.strategy, StickyFactsStrategy):
                self.strategy.facts = {}
        self.save_memory()
        print("История очищена.")

    def save_to_working(self, key: str, value: str):
        """Сохранить информацию в рабочую память."""
        self.working.set(key, value)
        self.save_memory()
        print(f"✅ Сохранено в рабочую память: {key} = {value}")

    def save_to_longterm(self, fact_type: str, content: str):
        """Сохранить факт в долговременную память."""
        self.long_term.add_fact(fact_type, content)
        self.save_memory()
        print(f"✅ Сохранено в долговременную память: {fact_type} -> {content}")

    def show_memory(self):
        """Показать содержимое всех трёх слоёв памяти."""
        print("\n=== КРАТКОСРОЧНАЯ ПАМЯТЬ (последние сообщения) ===")
        for msg in self.short_term.get_recent():
            print(f"{msg['role']}: {msg['content'][:80]}...")
        print("\n=== РАБОЧАЯ ПАМЯТЬ (текущая задача) ===")
        print(self.working.format_for_prompt())
        print("\n=== ДОЛГОВРЕМЕННАЯ ПАМЯТЬ ===")
        print(self.long_term.format_for_prompt())

    def ask(self, user_input: str) -> str:
        # Формируем контекст с учётом профиля
        base_context = self.strategy.prepare_context(user_input)
        # Вставляем профиль как системное сообщение после основной инструкции
        profile_text = self.long_term.format_for_prompt()  # включает и факты, и профиль
        if profile_text and profile_text != "Нет долговременной информации.":
            # Находим позицию после системной инструкции (если есть)
            insert_index = 1 if base_context and base_context[0]["role"] == "system" else 0
            base_context.insert(insert_index, {"role": "system", "content": f"Персонализация:\n{profile_text}"})

        try:
            response = self.client.chat.completions.create(
                model=f"gpt://{self.folder_id}/{self.model}",
                messages=cast(List[ChatCompletionMessageParam], base_context),
                temperature=0.5,
                max_tokens=1000
            )
            answer = response.choices[0].message.content or "⚠️ Пустой ответ от модели."

            if response.usage:
                pt = getattr(response.usage, 'prompt_tokens', 0) or 0
                ct = getattr(response.usage, 'completion_tokens', 0) or 0
                tt = getattr(response.usage, 'total_tokens', 0) or 0
                self.total_prompt_tokens += pt
                self.total_completion_tokens += ct
                self.total_tokens += tt
                self.last_stats = (pt, ct, tt)

            # Обновляем краткосрочную память
            self.short_term.add({"role": "user", "content": user_input})
            self.short_term.add({"role": "assistant", "content": answer})

            # Уведомляем стратегию об обновлении (для фактов)
            self.strategy.update_memory(user_input, answer)
            # Сохраняем состояние
            self.save_memory()
            return answer

        except openai.BadRequestError as e:
            error_msg = str(e)
            if "context length" in error_msg.lower():
                return "❌ Ошибка: контекст слишком длинный. Попробуйте очистить историю (/clear) или уменьшить окно (/window)."
            else:
                return f"❌ Ошибка API: {error_msg}"
        except Exception as e:
            return f"❌ Ошибка: {e}"