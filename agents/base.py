import httpx
import logging

class BaseAgent:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    async def _call(self, model: str, messages: list) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                response = await client.post(self.url, json={"model": model, "messages": messages}, headers=headers)
                response.raise_for_status()
                return response.json()['choices'][0]['message']['content']
            except Exception as e:
                logging.error(f"Agent {model} failed: {e}")
                if model != "deepseek/deepseek-v3":
                    return await self._call("deepseek/deepseek-v3", messages)
                return "Ошибка генерации. Попробуйте позже."

class Planner(BaseAgent):
    async def process(self, task: str, history: list) -> str:
        messages = history + [{"role": "user", "content": f"Создай план решения: {task}"}]
        return await self._call("qwen/qwen-2.5-coder-32b-instruct:free", messages)

class Verifier(BaseAgent):
    async def process(self, text: str) -> str:
        messages = [{"role": "user", "content": f"Проверь на ошибки: {text}"}]
        return await self._call("google/gemma-2-9b-it:free", messages)
