import os
import json
import openai
from typing import List, Dict, cast
from openai.types.chat import ChatCompletionMessageParam
from .strategies import (
    Strategy, SlidingWindowStrategy, StickyFactsStrategy, BranchingStrategy
)
from .memory import ShortTermMemory, WorkingMemory, LongTermMemory
from .task_state import TaskStateMachine, TaskStage
from .invariants import InvariantManager

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

        # Состояние задачи как конечный автомат
        self.task_state = TaskStateMachine()

        # Менеджер инвариантов
        self.invariant_manager = InvariantManager()

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
            
            # Загрузка состояния задачи
            task_state_data = data.get("task_state")
            if task_state_data:
                self.task_state = TaskStateMachine.from_dict(task_state_data)
        except Exception as e:
            print(f"⚠️ Ошибка загрузки состояния: {e}")

    def save_memory(self):
        data = {
            "strategy_id": self.current_strategy_id,
            "window_size": self.window_size,
            "short_term": self.short_term.to_dict(),
            "working": self.working.to_dict(),
            "long_term": self.long_term.to_dict(),
            "strategy_state": self.strategy.save_state(),
            "task_state": self.task_state.to_dict()
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

    def show_task_state(self):
        """Показать текущее состояние задачи."""
        from datetime import datetime
        status = self.task_state.get_status()
        print("\n=== СОСТОЯНИЕ ЗАДАЧИ ===")
        print(f"ID: {status['task_id']}")
        print(f"Этап: {status['stage']}")
        print(f"Текущий шаг: {status['current_step']}")
        print(f"Ожидаемое действие: {status['expected_action']}")
        print(f"Шагов выполнено: {status['steps_count']}")
        print(f"Пауза: {'Да' if status['paused'] else 'Нет'}")
        if status['paused'] and status['paused_at']:
            dt = datetime.fromtimestamp(status['paused_at'])
            print(f"Пауза с: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Обновлено: {datetime.fromtimestamp(status['updated_at']).strftime('%Y-%m-%d %H:%M:%S')}")

    def update_task_stage(self, new_stage: str, step_description: str = "", expected_action: str = ""):
        """
        Обновить этап задачи.
        
        Аргументы:
            new_stage: planning, execution, validation, done, paused, error
            step_description: описание текущего шага
            expected_action: ожидаемое действие
        """
        from .task_state import TaskStage
        try:
            stage = TaskStage(new_stage)
        except ValueError:
            print(f"Неизвестный этап: {new_stage}. Допустимые: {[e.value for e in TaskStage]}")
            return False
        
        success = self.task_state.transition_to(stage, step_description, expected_action)
        if success:
            self.save_memory()
            print(f"✅ Этап задачи изменён на {new_stage}")
        else:
            print(f"❌ Невозможно перейти из {self.task_state.stage.value} в {new_stage}")
        return success

    def pause_task(self, reason: str = ""):
        """Поставить задачу на паузу."""
        success = self.task_state.pause(reason)
        if success:
            self.save_memory()
            print(f"✅ Задача поставлена на паузу. Причина: {reason if reason else 'не указана'}")
        else:
            print("❌ Не удалось поставить задачу на паузу (возможно, задача уже завершена)")
        return success

    def resume_task(self, new_stage: str = ""):
        """Возобновить задачу после паузы."""
        from .task_state import TaskStage
        stage = None
        if new_stage:
            try:
                stage = TaskStage(new_stage)
            except ValueError:
                print(f"Неизвестный этап: {new_stage}")
                return False
        
        success = self.task_state.resume(stage)
        if success:
            self.save_memory()
            print(f"✅ Задача возобновлена на этапе {self.task_state.stage.value}")
        else:
            print("❌ Не удалось возобновить задачу (возможно, задача не на паузе)")
        return success

    def complete_task_step(self, result: str = ""):
        """Завершить текущий шаг задачи."""
        self.task_state.complete_step(result)
        self.save_memory()
        print(f"✅ Шаг завершён: {result}")

    def _update_task_state_after_response(self, user_input: str, answer: str):
        """
        Обновить состояние задачи после ответа агента.
        
        Логика:
        1. Завершить текущий шаг с кратким описанием ответа.
        2. Если этап PLANNING и ответ содержит план (нумерованный список, слова "план", "шаг"),
           перейти в этап EXECUTION.
        3. Обновить текущий шаг на "Обработка ответа агента".
        """
        from .task_state import TaskStage
        
        # Завершаем текущий шаг
        result_preview = answer[:100] + ("..." if len(answer) > 100 else "")
        self.task_state.complete_step(f"Ответ агента: {result_preview}")
        
        # Проверяем, нужно ли перейти из PLANNING в EXECUTION
        if self.task_state.stage == TaskStage.PLANNING:
            # Простые эвристики для определения, что ответ содержит план
            plan_indicators = ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.",
                               "первый", "второй", "третий", "четвертый", "пятый",
                               "шаг", "этап", "план", "плана", "плану", "планы"]
            if any(indicator in answer.lower() for indicator in plan_indicators):
                self.task_state.transition_to(TaskStage.EXECUTION,
                                              step_description="Выполнение плана",
                                              expected_action="Выполнить шаги плана, создавать код/документацию")
        
        # Начинаем новый шаг для следующего взаимодействия
        self.task_state.update_step(f"Ожидание следующего запроса")

    def ask(self, user_input: str) -> str:
        # Обновляем состояние задачи перед обработкой запроса
        from .task_state import TaskStage
        
        # Проверка инвариантов пользовательского запроса
        violations = self.invariant_manager.check_violations(user_input)
        if violations:
            explanation = self.invariant_manager.explain_violations(violations)
            # Добавляем запрос в историю, но не генерируем ответ
            self.short_term.add({"role": "user", "content": user_input})
            self.short_term.add({"role": "assistant", "content": explanation})
            self.save_memory()
            return explanation
        
        # Если текущий шаг пуст, начинаем новый шаг
        if not self.task_state.current_step:
            self.task_state.update_step(f"Запрос пользователя: {user_input[:50]}...")
        
        # Формируем контекст с учётом профиля
        base_context = self.strategy.prepare_context(user_input)
        
        # Добавляем инварианты в системное сообщение
        invariants_text = self.invariant_manager.format_for_prompt()
        if invariants_text:
            # Находим позицию после системной инструкции (если есть)
            insert_index = 1 if base_context and base_context[0]["role"] == "system" else 0
            base_context.insert(insert_index, {"role": "system", "content": f"ИНВАРИАНТЫ (не нарушай):\n{invariants_text}"})
        
        # Вставляем профиль как системное сообщение после основной инструкции
        profile_text = self.long_term.format_for_prompt()  # включает и факты, и профиль
        if profile_text and profile_text != "Нет долговременной информации.":
            # Находим позицию после системной инструкции (если есть)
            # Уже есть инварианты, вставляем после них
            insert_index = 1 if base_context and base_context[0]["role"] == "system" else 0
            # Сдвигаем индекс, если уже вставили инварианты
            if invariants_text:
                insert_index += 1
            base_context.insert(insert_index, {"role": "system", "content": f"Персонализация:\n{profile_text}"})

        try:
            response = self.client.chat.completions.create(
                model=f"gpt://{self.folder_id}/{self.model}",
                messages=cast(List[ChatCompletionMessageParam], base_context),
                temperature=0.5,
                max_tokens=1000
            )
            answer = response.choices[0].message.content or "⚠️ Пустой ответ от модели."

            # Проверка ответа на нарушение инвариантов
            answer_violations = self.invariant_manager.check_violations(answer)
            if answer_violations:
                explanation = self.invariant_manager.explain_violations(answer_violations)
                error_msg = f"⚠️ Ответ нарушает инварианты и был отклонён.\n\n{explanation}\n\nПожалуйста, сформулируйте запрос иначе."
                # Добавляем запрос и сообщение об ошибке в историю
                self.short_term.add({"role": "user", "content": user_input})
                self.short_term.add({"role": "assistant", "content": error_msg})
                self.save_memory()
                return error_msg

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
            
            # Обновляем состояние задачи после ответа
            self._update_task_state_after_response(user_input, answer)
            
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