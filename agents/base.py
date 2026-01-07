import httpx
import logging
import json

class BaseAgent:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Базовый URL OpenRouter
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    async def _call(self, model: str, messages: list) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # OpenRouter требует эти заголовки для рейтинга приложений
            "HTTP-Referer": "https://github.com/YourUser/YourRepo", 
            "X-Title": "SkillsLLM Bot"
        }
        
        # Формируем тело запроса
        payload = {
            "model": model,
            "messages": messages
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(self.url, json=payload, headers=headers)
                
                # Если ошибка 4xx или 5xx, выбрасываем исключение, чтобы попасть в except
                response.raise_for_status()
                
                data = response.json()
                
                # Проверяем, есть ли ответ в JSON
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content']
                else:
                    logging.error(f"Empty response from {model}: {data}")
                    raise ValueError("Empty response")

            except Exception as e:
                logging.error(f"Agent {model} failed: {e}")
                # Если модель не сработала, пробуем Fallback (резервную модель)
                # ВАЖНО: проверяем, чтобы не зациклить рекурсию
                if model != "deepseek/deepseek-chat": 
                    logging.info("Switching to fallback model: deepseek/deepseek-chat")
                    # Заменил deepseek-v3 на deepseek-chat (стандартное имя в OpenRouter)
                    return await self._call("deepseek/deepseek-chat", messages)
                
                return f"Ошибка генерации ({model}): {str(e)}"

class Planner(BaseAgent):
    async def process(self, task: str, history: list) -> str:
        # Убедимся, что история - это список словарей
        valid_history = [m for m in history if isinstance(m, dict) and 'role' in m and 'content' in m]
        messages = valid_history + [{"role": "user", "content": f"Задача: {task}"}]
        # Используем надежную бесплатную модель
        return await self._call("google/gemini-2.0-flash-exp:free", messages)

class Verifier(BaseAgent):
    async def process(self, text: str) -> str:
        messages = [{"role": "user", "content": f"Проверь текст на ошибки: {text}"}]
        return await self._call("google/gemini-2.0-flash-exp:free", messages)
