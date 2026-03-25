import os
import json
import openai

class Agent:
    """
    Агент для взаимодействия с Yandex Cloud LLM через OpenAI-совместимый API.
    Инкапсулирует логику отправки запроса и получения ответа.
    Сохраняет историю диалога.
    Ведёт учёт токенов.
    """
    def __init__(self, folder_id: str, api_key: str, model: str, history_file: str = "data/conversation_history.json"):
        self.folder_id = folder_id
        self.model = model
        self.history_file = history_file
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            project=folder_id
        )
        self.messages = self.load_history()
        # Статистика токенов за сессию
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        # Статистика последнего запроса
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0

    def load_history(self) -> list:
        """Загружает историю из JSON-файла."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                print("⚠️ Ошибка чтения истории. Начинаем новую.")
        return []
    
    def save_history(self):
        """Сохраняет историю в JSON-файл."""
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)
    
    def clear_history(self):
        """Очищает историю диалога."""
        self.messages = []
        self.save_history()
        print("🧹 История очищена. Статистика токенов сброшена.")
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0

    def ask(self, prompt: str) -> str:
        """Отправляет запрос с полной историей, получает ответ и обновляет историю."""
        # Добавляем сообщение пользователя в историю
        self.messages.append({"role": "user", "content": prompt})

        # Перед запросом выводим количество сообщений в истории
        print(f"\n📨 Сообщений в истории: {len(self.messages)}")
        
        try:
            response = self.client.chat.completions.create(
                model=f"gpt://{self.folder_id}/{self.model}",
                messages=self.messages,
                temperature=0.5,
                max_tokens=500
            )
            # Извлекаем ответ (content может быть None, но обычно это строка)
            answer = response.choices[0].message.content or "⚠️ Пустой ответ от модели."

            # Статистика токенов
            usage = response.usage
            if usage:
                 # Извлекаем значения, заменяя None на 0
                prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
                completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
                total_tokens = getattr(usage, 'total_tokens', 0) or 0
                
                # Сохраняем последнюю статистику
                self.last_prompt_tokens = prompt_tokens
                self.last_completion_tokens = completion_tokens
                self.last_total_tokens = total_tokens
                
                # Обновляем суммарную статистику
                self.total_prompt_tokens += prompt_tokens
                self.total_completion_tokens += completion_tokens
                self.total_tokens += total_tokens
            else:
                self.last_prompt_tokens = 0
                self.last_completion_tokens = 0
                self.last_total_tokens = 0
                print("⚠️ Статистика токенов недоступна от API.")

            # Добавляем ответ ассистента в историю
            self.messages.append({"role": "assistant", "content": answer})
            self.save_history()  # сохраняем обновлённую историю
            return answer
        except openai.BadRequestError as e:
            # Обработка ошибки превышения лимита контекста
            error_msg = str(e)
            if "context length" in error_msg.lower() or "maximum context length" in error_msg.lower():
                print("\n❌ ОШИБКА: Длина истории превышает лимит модели!")
                print("   Рекомендация: очистите историю командой /clear и продолжите диалог.")
                # Удаляем только что добавленное пользовательское сообщение
                self.messages.pop()
                return "Невозможно обработать запрос из-за слишком длинной истории. Пожалуйста, очистите историю командой /clear и повторите вопрос."
            else:
                print(f"\n❌ Ошибка API: {error_msg}")
                self.messages.pop()  # убираем сообщение пользователя из истории
                return f"Ошибка при запросе к Yandex Cloud API: {error_msg}"
        except Exception as e:
            error_msg = f"Ошибка при запросе к Yandex Cloud API: {e}"
            print(f"\n❌ {error_msg}")
            self.messages.pop()  # убираем сообщение пользователя из истории
            return error_msg