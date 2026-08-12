class RecoverableAiError(Exception):
    """AI 外部依赖暂时不可用，但本地 fallback 仍可继续处理。"""


class ExternalAiServiceError(RecoverableAiError):
    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"External AI service failed during {operation}")


class InvalidModelResponseError(RecoverableAiError):
    def __init__(self) -> None:
        super().__init__("AI response did not contain the required structured output")
