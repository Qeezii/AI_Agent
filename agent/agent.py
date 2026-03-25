import os
import json
import openai

class Agent:
    """
    Агент для взаимодействия с Yandex Cloud LLM через OpenAI-совместимый API.
    Инкапсулирует логику отправки запроса и получения ответа.
    Сохраняет историю диалога.
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

    def ask(self, prompt: str) -> str:
        """Отправляет запрос с полной историей, получает ответ и обновляет историю."""
        # Добавляем сообщение пользователя в историю
        self.messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=f"gpt://{self.folder_id}/{self.model}",
                messages=self.messages,
                temperature=0.5,
                max_tokens=500
            )
            # Извлекаем ответ (content может быть None, но обычно это строка)
            answer = response.choices[0].message.content or "⚠️ Пустой ответ от модели."
            # Добавляем ответ ассистента в историю
            self.messages.append({"role": "assistant", "content": answer})
            self.save_history()  # сохраняем обновлённую историю
            return answer
        except Exception as e:
            error_msg = f"Ошибка при запросе к Yandex Cloud API: {e}"
            # В случае ошибки не добавляем ответ в историю, но сохранять не нужно
            return error_msg