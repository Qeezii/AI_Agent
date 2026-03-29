import os
import json
import openai

class Agent:
    """
    Агент для взаимодействия с Yandex Cloud LLM через OpenAI-совместимый API.
    Инкапсулирует логику отправки запроса и получения ответа.
    Сохраняет историю диалога.
    Ведёт учёт токенов.
    Хранит последние N сообщений полностью, остальные сжимает в summary.
    """
    def __init__(self, folder_id: str, api_key: str, model: str,
                 history_file: str = "data/conversation_history.json",
                 max_history_messages: int = 10,
                 use_compression: bool = True):
        self.folder_id = folder_id
        self.model = model
        self.history_file = history_file
        self.max_history_messages = max_history_messages  # сколько последних сообщений хранить полностью
        self.use_compression = use_compression
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            project=folder_id
        )
        # Загружаем историю и summary
        self.messages, self.summary = self.load_history()
        # Статистика токенов за сессию
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        # Статистика последнего запроса
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0

    def load_history(self) -> tuple[list, str]:
        """Загружает историю и summary из JSON-файла."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    messages = data.get("messages", [])
                    summary = data.get("summary", "")
                    return messages, summary
            except (json.JSONDecodeError, IOError):
                print("⚠️ Ошибка чтения истории. Начинаем новую.")
        return [], ""
    
    def save_history(self):
        """Сохраняет историю и summary в JSON-файл."""
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        data = {
            "messages": self.messages,
            "summary": self.summary
        }
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def clear_history(self):
        """Очищает историю и summary."""
        self.messages = []
        self.summary = ""
        self.save_history()
        print("🧹 История и summary очищены. Статистика токенов сброшена.")
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0
    
    def generate_summary(self, old_messages: list) -> str:
        """Генерирует краткое резюме для списка сообщений через LLM."""
        if not old_messages:
            return ""
        # Формируем текст для сжатия
        conversation_text = "\n".join([f"{m['role']}: {m['content']}" for m in old_messages])
        prompt = f"Кратко изложи суть следующего диалога. Сохрани ключевые факты, вопросы и ответы. Не добавляй лишнего.\n\n{conversation_text}"
        try:
            response = self.client.chat.completions.create(
                model=f"gpt://{self.folder_id}/{self.model}",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300
            )
            summary = response.choices[0].message.content or ""
            # Учитываем токены, потраченные на генерацию summary
            if response.usage:
                self.total_prompt_tokens += response.usage.prompt_tokens
                self.total_completion_tokens += response.usage.completion_tokens
                self.total_tokens += response.usage.total_tokens
            return summary.strip()
        except Exception as e:
            print(f"⚠️ Ошибка генерации summary: {e}")
            return ""
    
    def compress_history(self):
        """Сжимает старые сообщения (кроме последних max_history_messages) в summary."""
        if not self.use_compression:
            return
        # Определяем, какие сообщения нужно сжать
        total_msgs = len(self.messages)
        if total_msgs <= self.max_history_messages:
            return  # ещё не накопилось достаточно
        # Сообщения, которые пойдут в summary (все, кроме последних max_history_messages)
        to_compress = self.messages[:-self.max_history_messages]
        # Генерируем новый summary (объединяем со старым, если был)
        new_summary = self.generate_summary(to_compress)
        if new_summary:
            # Если уже был summary, объединяем
            if self.summary:
                combined = f"Предыдущий контекст: {self.summary}\nДополнительно: {new_summary}"
            else:
                combined = new_summary
            self.summary = combined
        # Оставляем только последние max_history_messages сообщений
        self.messages = self.messages[-self.max_history_messages:]
        self.save_history()

    def build_context(self) -> list:
        """Формирует список сообщений для отправки в LLM с учётом summary."""
        if not self.use_compression or not self.summary:
            # Без сжатия или без summary – отдаём всю историю
            return self.messages
        # Со сжатием: сначала идёт системное сообщение с summary, затем последние сообщения
        context = [{"role": "system", "content": f"Краткое содержание предыдущего диалога: {self.summary}"}]
        context.extend(self.messages)
        return context

    def ask(self, prompt: str) -> str:
        """Отправляет запрос с полной историей, получает ответ и обновляет историю."""
        # Добавляем сообщение пользователя в историю
        self.messages.append({"role": "user", "content": prompt})

        # Сжимаем историю, если нужно
        self.compress_history()

        # Формируем контекст для запроса
        context = self.build_context()
        print(f"\n📨 Сообщений в контексте: {len(context)} (из них сжатых: {1 if self.summary else 0})")
        
        try:
            response = self.client.chat.completions.create(
                model=f"gpt://{self.folder_id}/{self.model}",
                messages=context,
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

            # Добавляем ответ ассистента в историю (полную, не сжатую)
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