import os
from dotenv import load_dotenv
from agent.agent import Agent

def main():
    # Загружаем переменные из .env
    load_dotenv()

    folder_id = os.getenv("YANDEX_CLOUD_FOLDER")
    api_key = os.getenv("YANDEX_CLOUD_API_KEY")
    model = os.getenv("YANDEX_CLOUD_MODEL", "aliceai-llm/latest")

    # Проверяем, что все необходимые данные есть
    if not folder_id or not api_key:
        print("Ошибка: не указаны YANDEX_CLOUD_FOLDER и/или YANDEX_CLOUD_API_KEY в .env файле.")
        return

    print("Выберите режим работы:")
    print("1. Без сжатия (храним всю историю)")
    print("2. Со сжатием (храним последние 10 сообщений, остальное в summary)")
    choice = input("Ваш выбор (1/2): ").strip()
    use_compression = (choice == "2")
    max_history = 10 # количество сообщений без сжатия

    # Создаём агента
    agent = Agent(folder_id, api_key, model,
                  use_compression=use_compression,
                  max_history_messages=max_history)

    print(f"\nРежим: {'Сжатие включено' if use_compression else 'Без сжатия'}")
    print(f"Загружено сообщений: {len(agent.messages)}")
    if agent.summary:
        print(f"Имеется summary: {agent.summary[:100]}...")
    print("Команды: /clear — очистить историю, /exit — выход\n")
    
    while True:
        user_input = input("\nВы: ").strip()
        if not user_input:
            continue
        # Команды выхода
        if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
            print("До свидания!")
            break
        # Команды очистки
        if user_input.lower() in ("/clear", "clear"):
            agent.clear_history()
            print("История очищена.")
            continue

        response = agent.ask(user_input)
        
        # Выводим ответ
        print(f"\n🤖 Агент: {response}")
        
        # Выводим статистику токенов последнего запроса и накопленную
        if agent.last_total_tokens > 0:
            print(f"\n📊 Токены текущего запроса:")
            print(f"   - prompt_tokens: {agent.last_prompt_tokens}")
            print(f"   - completion_tokens: {agent.last_completion_tokens}")
            print(f"   - total: {agent.last_total_tokens}")
            print(f"📈 Всего за сессию: prompt={agent.total_prompt_tokens}, "
                  f"completion={agent.total_completion_tokens}, total={agent.total_tokens}")
        print()  # пустая строка для разделения

if __name__ == "__main__":
    main()