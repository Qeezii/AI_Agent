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

    # Создаём агента
    agent = Agent(folder_id, api_key, model)

    print("Чат с агентом запущен. Введите 'exit' или 'quit' для выхода.")
    while True:
        user_input = input("\nВы: ")
        if user_input.lower() in ("exit", "quit"):
            print("До свидания!")
            break
        if not user_input.strip():
            continue
        response = agent.ask(user_input)
        print(f"Агент: {response}")

if __name__ == "__main__":
    main()