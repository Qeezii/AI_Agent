import os
from dotenv import load_dotenv

def load_env():
    """Загружает переменные окружения из .env и возвращает folder_id, api_key, model."""
    load_dotenv()
    folder_id = os.getenv("YANDEX_CLOUD_FOLDER")
    api_key = os.getenv("YANDEX_CLOUD_API_KEY")
    model = os.getenv("YANDEX_CLOUD_MODEL", "yandexgpt/latest")
    return folder_id, api_key, model