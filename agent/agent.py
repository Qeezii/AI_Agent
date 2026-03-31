import os
import json
import openai
from typing import List, Dict, cast
from openai.types.chat import ChatCompletionMessageParam
from .strategies import (
    Strategy, SlidingWindowStrategy, StickyFactsStrategy, BranchingStrategy
)

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
        # Статистика токенов
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.last_stats = (0, 0, 0)

        # Доступные стратегии
        self.strategies: Dict[int, Strategy] = {
            1: SlidingWindowStrategy(self),
            2: StickyFactsStrategy(self),
            3: BranchingStrategy(self)
        }
        self.current_strategy_id: int = 1
        self.strategy: Strategy = self.strategies[self.current_strategy_id]

        # Основной список сообщений (для SlidingWindow и StickyFacts это полная история,
        # для Branching – текущая ветка)
        self.messages: List[Dict[str, str]] = []

        # Загружаем состояние
        self.load_memory()

    def load_memory(self):
        """Загружает сохранённое состояние из JSON."""
        if not os.path.exists(self.history_file):
            return
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.current_strategy_id = data.get("strategy_id", 1)
            self.strategy = self.strategies[self.current_strategy_id]
            self.window_size = data.get("window_size", 10)
            self.messages = data.get("messages", [])
            # Загружаем специфичное состояние стратегии
            strategy_state = data.get("strategy_state", {})
            self.strategy.load_state(strategy_state)
            # Для стратегии Branching: messages уже могут быть установлены внутри load_state,
            # но мы перезаписали self.messages. Поэтому если это Branching, нужно синхронизировать.
            if isinstance(self.strategy, BranchingStrategy):
                # Переопределяем messages из текущей ветки
                if self.strategy.current_branch in self.strategy.branches:
                    self.messages = self.strategy.branches[self.strategy.current_branch]
        except Exception as e:
            print(f"⚠️ Ошибка загрузки состояния: {e}")

    def save_memory(self):
        """Сохраняет текущее состояние в JSON."""
        data = {
            "strategy_id": self.current_strategy_id,
            "window_size": self.window_size,
            "messages": self.messages,
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
            self.strategy.branches = {"main": self.messages.copy()}
            self.strategy.current_branch = "main"
            self.messages = self.strategy.branches["main"]

        self.save_memory()
        print(f"Стратегия изменена на {self.get_strategy_name()}")

    def get_strategy_name(self) -> str:
        names = {1: "Sliding Window", 2: "Sticky Facts", 3: "Branching"}
        return names.get(self.current_strategy_id, "Unknown")

    def clear_history(self):
        """Очищает историю (для текущей стратегии)."""
        if isinstance(self.strategy, BranchingStrategy):
            # Очищаем текущую ветку
            self.strategy.branches[self.strategy.current_branch] = []
            self.messages = []
        else:
            self.messages = []
            if isinstance(self.strategy, StickyFactsStrategy):
                self.strategy.facts = {}
        self.save_memory()
        print("История очищена.")

    def ask(self, user_input: str) -> str:
        # Формируем контекст через текущую стратегию
        context = self.strategy.prepare_context(user_input)

        try:
            response = self.client.chat.completions.create(
                model=f"gpt://{self.folder_id}/{self.model}",
                messages=cast(List[ChatCompletionMessageParam], context),
                temperature=0.5,
                max_tokens=500
            )
            answer = response.choices[0].message.content or "⚠️ Пустой ответ от модели."
            # Статистика токенов
            if response.usage:
                pt = getattr(response.usage, 'prompt_tokens', 0) or 0
                ct = getattr(response.usage, 'completion_tokens', 0) or 0
                tt = getattr(response.usage, 'total_tokens', 0) or 0
                self.total_prompt_tokens += pt
                self.total_completion_tokens += ct
                self.total_tokens += tt
                self.last_stats = (pt, ct, tt)

            # Обновляем историю
            if isinstance(self.strategy, BranchingStrategy):
                # Добавляем в текущую ветку
                self.strategy.branches[self.strategy.current_branch].append({"role": "user", "content": user_input})
                self.strategy.branches[self.strategy.current_branch].append({"role": "assistant", "content": answer})
                self.messages = self.strategy.branches[self.strategy.current_branch]
            else:
                self.messages.append({"role": "user", "content": user_input})
                self.messages.append({"role": "assistant", "content": answer})
                # Для Sliding Window: ограничиваем количество сообщений, если установлено окно
                if self.current_strategy_id == 1 and self.window_size > 0:
                    # Ограничиваем до window_size сообщений (не пар)
                    if len(self.messages) > self.window_size:
                        self.messages = self.messages[-self.window_size:]

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