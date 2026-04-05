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
        "Ты — опытный аналитик по созданию цифровых двойников промышленных объектов."
    )
    agent = Agent(folder_id, api_key, model, system_instruction=system_instruction)

    print("\n🤖 Агент запущен. Команды:")
    print("/profile — показать текущий профиль")
    print("/set_profile поле=значение — изменить профиль (например, /set_profile preferred_style=технический)")
    print("/load_preset эксперт|новичок|менеджер — загрузить предустановленный профиль")
    print("/switch N — сменить стратегию (1=Sliding Window, 2=Sticky Facts, 3=Branching)")
    print("/window N — установить размер окна (для стратегий 1 и 2)")
    print("/facts — показать текущие факты (стратегия 2)")
    print("/branch name — создать новую ветку (стратегия 3)")
    print("/branches — список веток (стратегия 3)")
    print("/switch_branch name — переключиться на ветку (стратегия 3)")
    print("/clear — очистить краткосрочную историю (и факты для стратегии 2)")
    print("/save_working ключ: значение — сохранить в рабочую память")
    print("/save_longterm тип: содержание — сохранить в долговременную память")
    print("/show_memory — показать все три слоя памяти")
    print("/clear_memory — очистить рабочую и долговременную память")
    print("/exit — выход")
    print(f"Текущая стратегия: {agent.get_strategy_name()}, окно: {agent.window_size}")

    while True:
        user_input = input("\nВы: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("/exit", "quit", "exit"):
            print("До свидания!")
            break

        # Команды профиля
        if user_input == "/profile":
            prof = agent.get_profile()
            print("Текущий профиль пользователя:")
            for k, v in prof.items():
                print(f"  {k}: {v}")
            continue

        if user_input.startswith("/set_profile"):
            # Парсим ключ=значение
            cmd_rest = user_input[13:].strip()
            if "=" not in cmd_rest:
                print("Используйте: /set_profile поле=значение (например, /set_profile role=Специалист по цифровым двойникам)")
                continue
            # Разделяем по первому знаку =
            eq_index = cmd_rest.find("=")
            key = cmd_rest[:eq_index].strip()
            value = cmd_rest[eq_index+1:].strip()
            if key:
                agent.set_profile(**{key: value})
            else:
                print("Не указано поле")
            continue

        if user_input.startswith("/load_preset"):
            preset = user_input[13:].strip().lower()
            if preset:
                agent.load_profile_preset(preset)
            else:
                print("Используйте: /load_preset эксперт|новичок|менеджер")
            continue

        # Команды для стратегии 3 (ветвления)
        if user_input.startswith("/switch_branch") and isinstance(agent.strategy, BranchingStrategy):
            parts = user_input.split()
            if len(parts) < 2:
                print("Используйте: /switch_branch имя_ветки")
                continue
            name = parts[1]
            if agent.strategy.switch_branch(name):
                print(f"Переключились на ветку {name}")
            continue

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

        # Команды управления памятью
        if user_input.startswith("/save_working"):
            try:
                parts = user_input[13:].strip().split(":", 1)
                if len(parts) != 2:
                    print("Используйте: /save_working ключ: значение")
                    continue
                key = parts[0].strip()
                value = parts[1].strip()
                agent.save_to_working(key, value)
            except Exception as e:
                print(f"Ошибка: {e}")
            continue

        if user_input.startswith("/save_longterm"):
            try:
                parts = user_input[14:].strip().split(":", 1)
                if len(parts) != 2:
                    print("Используйте: /save_longterm тип: содержание")
                    continue
                fact_type = parts[0].strip()
                content = parts[1].strip()
                agent.save_to_longterm(fact_type, content)
            except Exception as e:
                print(f"Ошибка: {e}")
            continue

        if user_input == "/show_memory":
            agent.show_memory()
            continue

        if user_input == "/clear_memory":
            agent.working.clear()
            agent.long_term.clear()
            agent.save_memory()
            print("Рабочая и долговременная память очищены.")
            continue

        # Остальные команды
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
                agent.short_term.max_size = new_size * 2  # синхронизируем размер краткосрочной памяти
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

        # Обычный запрос
        answer = agent.ask(user_input)
        print(f"\n🤖 Агент: {answer}")
        pt, ct, tt = agent.last_stats
        print(f"📊 Токены: prompt={pt}, completion={ct}, total={tt}")
        print(f"📈 Всего за сессию: {agent.total_tokens}")

if __name__ == "__main__":
    main()