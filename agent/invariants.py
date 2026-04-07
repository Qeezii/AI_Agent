"""
Модуль для управления инвариантами ассистента.

Инварианты — это правила, которые ассистент не имеет права нарушать:
- выбранная архитектура
- принятые технические решения
- ограничения по стеку
- бизнес-правила
"""
import json
import os
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum


class InvariantCategory(Enum):
    """Категории инвариантов."""
    ARCHITECTURE = "architecture"
    TECHNICAL_DECISIONS = "technical_decisions"
    STACK_CONSTRAINTS = "stack_constraints"
    BUSINESS_RULES = "business_rules"
    OTHER = "other"


class Invariant:
    """Один инвариант."""
    
    def __init__(self, 
                 id: str,
                 category: InvariantCategory,
                 description: str,
                 rationale: str = "",
                 severity: str = "high"):  # high, medium, low
        self.id = id
        self.category = category
        self.description = description
        self.rationale = rationale
        self.severity = severity
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "description": self.description,
            "rationale": self.rationale,
            "severity": self.severity
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Invariant':
        return cls(
            id=data["id"],
            category=InvariantCategory(data["category"]),
            description=data["description"],
            rationale=data.get("rationale", ""),
            severity=data.get("severity", "high")
        )
    
    def __str__(self) -> str:
        return f"[{self.category.value}] {self.description}"


class InvariantManager:
    """Менеджер инвариантов: загрузка, проверка, управление."""
    
    DEFAULT_INVARIANTS_FILE = "data/invariants.json"
    
    def __init__(self, invariants_file: Optional[str] = None):
        self.invariants_file = invariants_file or self.DEFAULT_INVARIANTS_FILE
        self.invariants: List[Invariant] = []
        self.load()
    
    def load(self) -> None:
        """Загрузить инварианты из файла."""
        if not os.path.exists(self.invariants_file):
            self.invariants = self._get_default_invariants()
            self.save()
            return
        
        try:
            with open(self.invariants_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.invariants = []
            for item in data.get("invariants", []):
                self.invariants.append(Invariant.from_dict(item))
        except Exception as e:
            print(f"Ошибка загрузки инвариантов: {e}")
            self.invariants = self._get_default_invariants()
    
    def save(self) -> None:
        """Сохранить инварианты в файл."""
        os.makedirs(os.path.dirname(self.invariants_file), exist_ok=True)
        data = {
            "invariants": [inv.to_dict() for inv in self.invariants]
        }
        with open(self.invariants_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _get_default_invariants(self) -> List[Invariant]:
        """Возвращает список инвариантов по умолчанию."""
        return [
            Invariant(
                id="arch-1",
                category=InvariantCategory.ARCHITECTURE,
                description="Ассистент использует трёхслойную память: краткосрочную, рабочую и долговременную",
                rationale="Архитектура определена в проекте и не должна меняться"
            ),
            Invariant(
                id="arch-2",
                category=InvariantCategory.ARCHITECTURE,
                description="Ассистент поддерживает три стратегии управления контекстом: Sliding Window, Sticky Facts, Branching",
                rationale="Стратегии реализованы и должны оставаться доступными"
            ),
            Invariant(
                id="tech-1",
                category=InvariantCategory.TECHNICAL_DECISIONS,
                description="Используется Yandex Cloud LLM API, а не OpenAI или другие провайдеры",
                rationale="Решение принято из-за требований к локализации и стоимости"
            ),
            Invariant(
                id="stack-1",
                category=InvariantCategory.STACK_CONSTRAINTS,
                description="Проект написан на Python 3.9+, без использования других языков",
                rationale="Ограничение стека для упрощения поддержки"
            ),
            Invariant(
                id="stack-2",
                category=InvariantCategory.STACK_CONSTRAINTS,
                description="Не использовать сторонние библиотеки без согласования",
                rationale="Минимизация зависимостей"
            ),
            Invariant(
                id="business-1",
                category=InvariantCategory.BUSINESS_RULES,
                description="Ассистент специализируется на создании цифровых двойников промышленных объектов",
                rationale="Бизнес-фокус проекта"
            ),
            Invariant(
                id="business-2",
                category=InvariantCategory.BUSINESS_RULES,
                description="Все ответы должны быть профессиональными и технически точными",
                rationale="Требования к качеству контента"
            )
        ]
    
    def add(self, invariant: Invariant) -> None:
        """Добавить новый инвариант."""
        self.invariants.append(invariant)
        self.save()
    
    def remove(self, invariant_id: str) -> bool:
        """Удалить инвариант по ID."""
        for i, inv in enumerate(self.invariants):
            if inv.id == invariant_id:
                del self.invariants[i]
                self.save()
                return True
        return False
    
    def get_all(self) -> List[Invariant]:
        """Получить все инварианты."""
        return self.invariants
    
    def get_by_category(self, category: InvariantCategory) -> List[Invariant]:
        """Получить инварианты по категории."""
        return [inv for inv in self.invariants if inv.category == category]
    
    def check_violations(self, text: str) -> List[Tuple[Invariant, str]]:
        """
        Проверить текст на нарушение инвариантов.
        
        Возвращает список пар (инвариант, объяснение нарушения).
        """
        violations = []
        text_lower = text.lower()
        
        # Простые ключевые слова для демонстрации
        # В реальной системе можно использовать более сложный анализ
        for inv in self.invariants:
            violation_reason = self._check_single_invariant(inv, text_lower)
            if violation_reason:
                violations.append((inv, violation_reason))
        
        return violations
    
    def _check_single_invariant(self, invariant: Invariant, text_lower: str) -> Optional[str]:
        """Проверить один инвариант, вернуть причину нарушения или None."""
        # Демонстрационная логика проверки
        # В реальном проекте можно использовать LLM для семантической проверки
        if invariant.id == "arch-1":
            if "четырехслойную" in text_lower or "двухслойную" in text_lower:
                return "Предлагается изменить трёхслойную архитектуру памяти"
            if "убрать память" in text_lower and ("краткосрочную" in text_lower or "рабочую" in text_lower):
                return "Предлагается удалить слой памяти"
        
        elif invariant.id == "tech-1":
            if "openai" in text_lower or "gpt" in text_lower or "anthropic" in text_lower:
                return "Предлагается использовать другого провайдера LLM вместо Yandex Cloud"
        
        elif invariant.id == "stack-1":
            if "javascript" in text_lower or "java" in text_lower or "go" in text_lower or "rust" in text_lower:
                return "Предлагается использовать другой язык программирования вместо Python"
        
        elif invariant.id == "stack-2":
            if "установить библиотеку" in text_lower or "pip install" in text_lower:
                # Но не все установки запрещены, нужно контекст
                pass
        
        elif invariant.id == "business-1":
            if "медицинск" in text_lower or "финанс" in text_lower or "розничн" in text_lower:
                return "Предлагается сменить специализацию с цифровых двойников промышленных объектов"
        
        return None
    
    def format_for_prompt(self) -> str:
        """Форматировать инварианты для включения в промпт."""
        if not self.invariants:
            return "Нет активных инвариантов."
        
        lines = ["# ИНВАРИАНТЫ (правила, которые нельзя нарушать):"]
        for inv in self.invariants:
            lines.append(f"- [{inv.category.value}] {inv.description}")
            if inv.rationale:
                lines.append(f"  Обоснование: {inv.rationale}")
        return "\n".join(lines)
    
    def explain_violations(self, violations: List[Tuple[Invariant, str]]) -> str:
        """Сформировать объяснение нарушений для пользователя."""
        if not violations:
            return ""
        
        lines = ["⚠️ Запрос нарушает следующие инварианты:"]
        for inv, reason in violations:
            lines.append(f"  • {inv.description}")
            lines.append(f"    Нарушение: {reason}")
            lines.append(f"    Категория: {inv.category.value}")
            if inv.rationale:
                lines.append(f"    Обоснование: {inv.rationale}")
            lines.append("")
        
        lines.append("Пожалуйста, измените запрос или обсудите возможность изменения инвариантов.")
        return "\n".join(lines)