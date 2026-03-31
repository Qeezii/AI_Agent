#!/usr/bin/env python3
import sys
from agent import Agent, StickyFactsStrategy, BranchingStrategy
from agent.utils import load_env

def main():
    folder_id, api_key, model = load_env()
    if not folder_id or not api_key:
        print("Ошибка: не указаны YANDEX_CLOUD_FOLDER и/или YANDEX_CLOUD_API_KEY в .env")
        sys.exit(1)

    system_instruction = (
        "Ты — опытный аналитик по сбору требований и разработке цифровых двойников промышленных объектов на Anylogic. "
        "Твоя задача — задавать короткие уточняющие вопросы, чтобы собрать полное техническое задание. "
        "Не давай длинных объяснений, только вопросы и краткие подтверждения."
    )
    agent = Agent(folder_id, api_key, model, system_instruction=system_instruction)

    print("\n🤖 Агент запущен. Команды:")
    print("/switch N — сменить стратегию (1=Sliding Window, 2=Sticky Facts, 3=Branching)")
    print("/window N — установить размер окна (для стратегий 1 и 2)")
    print("/facts — показать текущие факты (стратегия 2)")
    print("/branch name — создать новую ветку (стратегия 3)")
    print("/branches — список веток (стратегия 3)")
    print("/switch_branch name — переключиться на ветку (стратегия 3)")
    print("/clear — очистить историю (для текущей стратегии)")
    print("/exit — выход")
    print(f"Текущая стратегия: {agent.get_strategy_name()}, окно: {agent.window_size}")

    while True:
        user_input = input("\nВы: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("/exit", "quit", "exit"):
            print("До свидания!")
            break

        # 1. Команды для стратегии 3 (ветвления) – самые специфичные сначала
        if user_input.startswith("/switch_branch") and isinstance(agent.strategy, BranchingStrategy):
            parts = user_input.split()
            if len(parts) < 2:
                print("Используйте: /switch_branch имя_ветки")
                continue
            name = parts[1]
            if agent.strategy.switch_branch(name):
                print(f"Переключились на ветку {name}")
            continue

        # Проверяем точное совпадение для /branches, чтобы не путать с /branch
        if user_input == "/branches" and isinstance(agent.strategy, BranchingStrategy):
            print("Ветки:", ", ".join(agent.strategy.branches.keys()))
            print(f"Текущая: {agent.strategy.current_branch}")
            continue

        if user_input.startswith("/branch") and isinstance(agent.strategy, BranchingStrategy):
            parts = user_input.split()
            if len(parts) < 2:
                print("Используйте: /branch имя_ветки")
                continue
            name = parts[1]
            if agent.strategy.create_branch(name):
                print(f"Ветка {name} создана (копия текущей).")
            continue

        # 2. Остальные команды
        if user_input.startswith("/switch"):
            try:
                sid = int(user_input.split()[1])
                agent.set_strategy(sid)
                print(f"Текущая стратегия: {agent.get_strategy_name()}")
            except:
                print("Используйте: /switch 1|2|3")
            continue

        if user_input.startswith("/window"):
            try:
                new_size = int(user_input.split()[1])
                agent.window_size = new_size
                agent.save_memory()
                print(f"Размер окна установлен: {agent.window_size}")
            except:
                print("Используйте: /window N")
            continue

        if user_input == "/facts" and isinstance(agent.strategy, StickyFactsStrategy):
            if agent.strategy.facts:
                print("Текущие факты:")
                for k, v in agent.strategy.facts.items():
                    print(f"  {k}: {v}")
            else:
                print("Факты отсутствуют.")
            continue

        if user_input == "/clear":
            agent.clear_history()
            continue

        # 3. Обычный запрос
        answer = agent.ask(user_input)
        print(f"\n🤖 Агент: {answer}")
        pt, ct, tt = agent.last_stats
        print(f"📊 Токены: prompt={pt}, completion={ct}, total={tt}")
        print(f"📈 Всего за сессию: {agent.total_tokens}")

if __name__ == "__main__":
    main()