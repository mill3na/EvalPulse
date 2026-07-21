from typing import Protocol

from evalpulse.models import AgentResponse


class Agent(Protocol):
    name: str

    async def answer(self, prompt: str) -> AgentResponse: ...


class DemoFaqAgent:
    name = "demo-faq-agent"

    _answers = {
        "what is evalpulse?": "EvalPulse evaluates AI agents continuously.",
        "how do i run it?": "Run docker compose up.",
        "does it need kubernetes?": "No, Kubernetes is not required.",
    }

    async def answer(self, prompt: str) -> AgentResponse:
        content = self._answers.get(prompt.casefold().strip(), "I don't know yet.")
        return AgentResponse(content=content)
