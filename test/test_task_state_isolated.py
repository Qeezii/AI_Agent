#!/usr/bin/env python3
"""
Изолированное тестирование TaskStateMachine без зависимостей.
"""

import sys
import os
import importlib.util

# Загружаем модуль task_state напрямую, минуя __init__.py
spec = importlib.util.spec_from_file_location(
    "task_state", 
    os.path.join(os.path.dirname(__file__), "agent", "task_state.py")
)
task_state_module = importlib.util.module_from_spec(spec)
sys.modules["task_state"] = task_state_module
spec.loader.exec_module(task_state_module)

TaskStateMachine = task_state_module.TaskStateMachine
TaskStage = task_state_module.TaskStage

def test_basic():
    print("=== Тест базовой функциональности ===")
    ts = TaskStateMachine(task_id="test_1")
    print(f"Начальный этап: {ts.stage.value}")
    print(f"Ожидаемое действие: {ts.expected_action}")
    
    # Переходы
    assert ts.can_transition_to(TaskStage.EXECUTION) == True
    assert ts.can_transition_to(TaskStage.DONE) == False
    
    # Переход в execution
    success = ts.transition_to(TaskStage.EXECUTION, "Начало реализации", "Написать код")
    assert success == True
    print(f"После перехода в execution: этап={ts.stage.value}, шаг={ts.current_step}")
    
    # Пауза
    success = ts.pause("нужен перерыв")
    assert success == True
    print(f"После паузы: этап={ts.stage.value}, paused_at={ts.paused_at}")
    
    # Возобновление
    success = ts.resume()
    assert success == True
    print(f"После возобновления: этап={ts.stage.value}")
    
    # Завершение шага
    ts.complete_step("Код написан")
    print(f"Шагов в истории: {len(ts.steps_history)}")
    
    # Переход в validation
    ts.transition_to(TaskStage.VALIDATION, "Проверка кода", "Протестировать")
    print(f"Этап validation: {ts.current_step}")
    
    # Переход в done
    ts.transition_to(TaskStage.DONE, "Задача завершена", "Начать новую")
    print(f"Финальный этап: {ts.stage.value}")
    
    # Сохранение и загрузка
    data = ts.to_dict()
    ts2 = TaskStateMachine.from_dict(data)
    assert ts2.stage == ts.stage
    assert ts2.current_step == ts.current_step
    print("Сериализация/десериализация прошла успешно")
    
    print("PASS Все базовые тесты пройдены")

def test_transitions():
    print("\n=== Тест переходов ===")
    ts = TaskStateMachine()
    
    # Матрица переходов
    test_cases = [
        (TaskStage.PLANNING, TaskStage.EXECUTION, True),
        (TaskStage.PLANNING, TaskStage.PAUSED, True),
        (TaskStage.PLANNING, TaskStage.ERROR, True),
        (TaskStage.PLANNING, TaskStage.DONE, False),
        (TaskStage.EXECUTION, TaskStage.VALIDATION, True),
        (TaskStage.EXECUTION, TaskStage.PAUSED, True),
        (TaskStage.VALIDATION, TaskStage.DONE, True),
        (TaskStage.DONE, TaskStage.PLANNING, False),
        (TaskStage.PAUSED, TaskStage.EXECUTION, True),
        (TaskStage.ERROR, TaskStage.PAUSED, True),
    ]
    
    for from_stage, to_stage, expected in test_cases:
        ts.stage = from_stage
        result = ts.can_transition_to(to_stage)
        status = "PASS" if result == expected else "FAIL"
        print(f"{status} {from_stage.value} -> {to_stage.value}: ожидалось {expected}, получили {result}")
        assert result == expected
    
    print("PASS Все переходы корректны")

def test_pause_resume():
    print("\n=== Тест паузы и продолжения ===")
    ts = TaskStateMachine()
    
    # Пауза из planning
    ts.transition_to(TaskStage.PLANNING, "Планируем")
    assert ts.pause("тест") == True
    assert ts.stage == TaskStage.PAUSED
    
    # Продолжение без указания этапа (должен вернуться в planning)
    assert ts.resume() == True
    assert ts.stage == TaskStage.PLANNING
    
    # Пауза из execution с указанием этапа для возобновления
    ts.transition_to(TaskStage.EXECUTION, "Пишем код")
    ts.pause("кофе-брейк")
    assert ts.resume(TaskStage.VALIDATION) == True
    assert ts.stage == TaskStage.VALIDATION
    
    # Пауза из done не должна работать
    ts.transition_to(TaskStage.DONE, "Готово")
    assert ts.pause() == False
    assert ts.stage == TaskStage.DONE
    
    print("PASS Пауза и продолжение работают корректно")

if __name__ == "__main__":
    test_basic()
    test_transitions()
    test_pause_resume()
    print("\n🎉 Все тесты пройдены успешно!")