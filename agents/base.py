import httpx

class BaseAgent:
    def __init__(self, key):
        self.key = key
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    async def _call(self, model, messages):
        async with httpx.AsyncClient() as c:
            try:
                r = await c.post(self.url, json={"model": model, "messages": messages}, 
                                 headers={"Authorization": f"Bearer {self.key}"}, timeout=30)
                return r.json()['choices'][0]['message']['content']
            except:
                if model != "deepseek/deepseek-v3": # Fallback
                    return await self._call("deepseek/deepseek-v3", messages)
                return "Service unavailable"

class Planner(BaseAgent):
    async def process(self, task, history):
        messages = history + [{"role": "user", "content": task}]
        return await self._call("qwen/qwen-2.5-coder-32b-instruct:free", messages)

class Verifier(BaseAgent):
    async def process(self, text):
        return await self._call("google/gemma-2-9b-it:free", [{"role": "user", "content": text}])
