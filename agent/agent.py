import openai

class Agent:
    """
    Агент для взаимодействия с Yandex Cloud LLM через OpenAI-совместимый API.
    Инкапсулирует логику отправки запроса и получения ответа.
    """
    def __init__(self, folder_id: str, api_key: str, model: str):
        self.folder_id = folder_id
        self.model = model
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            project=folder_id
        )

    def ask(self, prompt: str) -> str:
        """
        Отправляет запрос к модели YandexGPT и возвращает ответ.
        """
        try:
            response = self.client.responses.create(
                model=f"gpt://{self.folder_id}/{self.model}",
                temperature=0.5,
                instructions="",          # системная инструкция
                input=prompt,             # пользовательский запрос
                max_output_tokens=500
            )
            # output_text всегда строка в успешном ответе
            return response.output_text
        except Exception as e:
            return f"Ошибка при запросе к Yandex Cloud API: {e}"