"""
Конечный автомат состояния задачи.

Определяет этапы задачи, текущий шаг и ожидаемое действие.
Поддерживает паузу и продолжение без повторных объяснений.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
import json
import time


class TaskStage(Enum):
    """Этапы задачи."""
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"
    DONE = "done"
    PAUSED = "paused"
    ERROR = "error"


class TaskStateMachine:
    """
    Конечный автомат для управления состоянием задачи.
    
    Атрибуты:
        stage: текущий этап (TaskStage)
        current_step: строка, описывающая текущий шаг внутри этапа
        expected_action: ожидаемое действие от пользователя или системы
        steps_history: история выполненных шагов
        metadata: дополнительные данные задачи
        paused_at: время паузы (timestamp)
        created_at: время создания
        updated_at: время последнего обновления
    """
    
    def __init__(self, task_id: str = "", initial_stage: TaskStage = TaskStage.PLANNING):
        self.task_id = task_id or f"task_{int(time.time())}"
        self.stage = initial_stage
        self.current_step = ""
        self.expected_action = ""
        self.steps_history: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        self.paused_at: Optional[float] = None
        self.created_at = time.time()
        self.updated_at = self.created_at
        
        # Определяем допустимые переходы между этапами
        self.transitions: Dict[TaskStage, List[TaskStage]] = {
            TaskStage.PLANNING: [TaskStage.EXECUTION, TaskStage.PAUSED, TaskStage.ERROR],
            TaskStage.EXECUTION: [TaskStage.VALIDATION, TaskStage.PAUSED, TaskStage.ERROR, TaskStage.PLANNING],
            TaskStage.VALIDATION: [TaskStage.DONE, TaskStage.EXECUTION, TaskStage.PAUSED, TaskStage.ERROR],
            TaskStage.DONE: [TaskStage.PLANNING, TaskStage.PAUSED],
            TaskStage.PAUSED: [TaskStage.PLANNING, TaskStage.EXECUTION, TaskStage.VALIDATION, TaskStage.ERROR],
            TaskStage.ERROR: [TaskStage.PLANNING, TaskStage.EXECUTION, TaskStage.PAUSED],
        }
        
        # Инициализируем стандартные ожидаемые действия для этапов
        self._init_expected_actions()
    
    def _init_expected_actions(self):
        """Установить стандартные ожидаемые действия для каждого этапа."""
        self.expected_actions_map = {
            TaskStage.PLANNING: "Определить цели, требования и план задачи",
            TaskStage.EXECUTION: "Выполнить шаги плана, создавать код/документацию",
            TaskStage.VALIDATION: "Проверить результат, тестировать, получить обратную связь",
            TaskStage.DONE: "Задача завершена, можно начать новую",
            TaskStage.PAUSED: "Возобновить выполнение или изменить задачу",
            TaskStage.ERROR: "Проанализировать ошибку и исправить",
        }
        self.expected_action = self.expected_actions_map.get(self.stage, "")
    
    def can_transition_to(self, new_stage: TaskStage) -> bool:
        """Проверить, возможен ли переход из текущего этапа в новый."""
        allowed = self.transitions.get(self.stage, [])
        return new_stage in allowed
    
    def transition_to(self, new_stage: TaskStage, step_description: str = "", 
                      expected_action: str = "", metadata_update: Optional[Dict] = None) -> bool:
        """
        Перейти к новому этапу.
        
        Возвращает True если переход успешен, False если переход невозможен.
        """
        if not self.can_transition_to(new_stage):
            return False
        
        # Записываем завершение текущего шага в историю
        if self.current_step:
            self.steps_history.append({
                "stage": self.stage.value,
                "step": self.current_step,
                "timestamp": self.updated_at,
                "completed": True
            })
        
        # Обновляем состояние
        old_stage = self.stage
        self.stage = new_stage
        self.current_step = step_description or f"Начало этапа {new_stage.value}"
        self.expected_action = expected_action or self.expected_actions_map.get(new_stage, "")
        self.updated_at = time.time()
        
        # Если выходим из паузы - сбрасываем paused_at
        if old_stage == TaskStage.PAUSED and new_stage != TaskStage.PAUSED:
            self.paused_at = None
        
        # Если входим в паузу - записываем время паузы
        if new_stage == TaskStage.PAUSED:
            self.paused_at = self.updated_at
        
        # Обновляем метаданные
        if metadata_update:
            self.metadata.update(metadata_update)
        
        return True
    
    def update_step(self, step_description: str, expected_action: str = "", 
                    metadata_update: Optional[Dict] = None):
        """
        Обновить текущий шаг в рамках того же этапа.
        """
        self.current_step = step_description
        if expected_action:
            self.expected_action = expected_action
        if metadata_update:
            self.metadata.update(metadata_update)
        self.updated_at = time.time()
    
    def pause(self, reason: str = ""):
        """Поставить задачу на паузу."""
        if self.stage == TaskStage.DONE:
            return False
        
        step_desc = f"Пауза: {reason}" if reason else "Задача приостановлена"
        return self.transition_to(TaskStage.PAUSED, step_desc, "Возобновить выполнение")
    
    def resume(self, new_stage: Optional[TaskStage] = None):
        """
        Возобновить задачу после паузы.
        
        Если new_stage не указан, возвращаемся к предыдущему этапу (определяем логически).
        """
        if self.stage != TaskStage.PAUSED:
            return False
        
        # Определяем этап для возобновления
        if new_stage is None:
            # Логика определения: смотрим историю, чтобы понять, на каком этапе была пауза
            if self.steps_history:
                last_stage = self.steps_history[-1].get("stage")
                if last_stage == "planning":
                    new_stage = TaskStage.PLANNING
                elif last_stage == "execution":
                    new_stage = TaskStage.EXECUTION
                elif last_stage == "validation":
                    new_stage = TaskStage.VALIDATION
                else:
                    new_stage = TaskStage.PLANNING
            else:
                new_stage = TaskStage.PLANNING
        
        step_desc = f"Возобновление после паузы на этапе {new_stage.value}"
        return self.transition_to(new_stage, step_desc)
    
    def complete_step(self, result: str = "", metadata_update: Optional[Dict] = None):
        """Завершить текущий шаг и добавить в историю."""
        step_to_record = self.current_step if self.current_step else "Шаг без описания"
        self.steps_history.append({
            "stage": self.stage.value,
            "step": step_to_record,
            "result": result,
            "timestamp": time.time(),
            "completed": True
        })
        
        if metadata_update:
            self.metadata.update(metadata_update)
        
        self.current_step = ""
        self.updated_at = time.time()
    
    def get_status(self) -> Dict[str, Any]:
        """Получить текущий статус задачи в виде словаря."""
        return {
            "task_id": self.task_id,
            "stage": self.stage.value,
            "current_step": self.current_step,
            "expected_action": self.expected_action,
            "steps_count": len(self.steps_history),
            "paused": self.stage == TaskStage.PAUSED,
            "paused_at": self.paused_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализовать состояние в словарь для сохранения."""
        return {
            "task_id": self.task_id,
            "stage": self.stage.value,
            "current_step": self.current_step,
            "expected_action": self.expected_action,
            "steps_history": self.steps_history,
            "metadata": self.metadata,
            "paused_at": self.paused_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "transitions": {k.value: [v.value for v in vals] for k, vals in self.transitions.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskStateMachine':
        """Восстановить состояние из словаря."""
        task = cls(task_id=data.get("task_id", ""))
        
        # Восстанавливаем этап
        stage_str = data.get("stage", "planning")
        try:
            task.stage = TaskStage(stage_str)
        except ValueError:
            task.stage = TaskStage.PLANNING
        
        # Восстанавливаем остальные поля
        task.current_step = data.get("current_step", "")
        task.expected_action = data.get("expected_action", "")
        task.steps_history = data.get("steps_history", [])
        task.metadata = data.get("metadata", {})
        task.paused_at = data.get("paused_at")
        task.created_at = data.get("created_at", time.time())
        task.updated_at = data.get("updated_at", time.time())
        
        return task
    
    def save_to_file(self, filepath: str):
        """Сохранить состояние в файл JSON."""
        data = self.to_dict()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'TaskStateMachine':
        """Загрузить состояние из файла JSON."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def __str__(self) -> str:
        status = self.get_status()
        return (f"Task {self.task_id}: {status['stage']} | "
                f"Step: {status['current_step']} | "
                f"Expected: {status['expected_action']}")