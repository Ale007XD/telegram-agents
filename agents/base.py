import httpx
import logging
import asyncio
import json

class BaseAgent:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Цепочка БЕСПЛАТНЫХ моделей (от самой умной к самой простой)
        self.fallback_chain = [
            "meta-llama/llama-3.3-70b-instruct:free",   # Умная (Smartest)
            "mistralai/mistral-nemo:free",              # Стабильная (Stable)
            "google/gemma-2-9b-it:free",                # Резерв 1
            "microsoft/phi-3-medium-128k-instruct:free" # Резерв 2
        ]

    async def _call(self, model: str, messages: list, attempt: int = 0) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/skillsllm/bot",
            "X-Title": "SkillsLLM Bot"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1500
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                logging.info(f"🧠 Trying AI model: {model}...")
                response = await client.post(self.url, json=payload, headers=headers)
                
                # Обработка ошибок API
                if response.status_code in [404, 429, 500, 502, 503]:
                    logging.warning(f"⚠️ Model {model} unavailable (Status: {response.status_code})")
                    raise ValueError("Model unavailable")
                
                response.raise_for_status()
                data = response.json()
                
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content']
                else:
                    raise ValueError(f"Empty response: {data}")

            except Exception as e:
                # Логика переключения (Fallback)
                next_attempt = attempt + 1
                if next_attempt < len(self.fallback_chain):
                    next_model = self.fallback_chain[next_attempt]
                    logging.info(f"🔄 Switching to fallback model: {next_model}")
                    return await self._call(next_model, messages, next_attempt)
                
                logging.error(f"❌ All AI models failed. Last error: {e}")
                return "😔 Извините, все AI-сервисы сейчас перегружены. Попробуйте через минуту."

class Planner(BaseAgent):
    async def process(self, task: str, history: list) -> str:
        # Фильтрация истории
        valid_history = [m for m in history if isinstance(m, dict) and m.get('content')]
        
        system_msg = {
            "role": "system", 
            "content": "Ты опытный ассистент. Твоя цель - помочь пользователю, составив четкий план или дав точный ответ. Используй Markdown."
        }
        
        messages = [system_msg] + valid_history + [{"role": "user", "content": task}]
        return await self._call(self.fallback_chain[0], messages)

class Verifier(BaseAgent):
    async def process(self, text: str) -> str:
        messages = [
            {"role": "system", "content": "Ты критик. Проверь текст на фактические и логические ошибки. Если все хорошо - напиши 'Ошибок нет'."},
            {"role": "user", "content": f"Текст для проверки:\n{text}"}
        ]
        return await self._call(self.fallback_chain[0], messages)
