from langchain_gigachat.chat_models import GigaChat
from config import GIGACHAT_CREDENTIALS, GIGACHAT_SCOPE, GIGACHAT_MODEL


def get_llm(temperature: float = 0.1) -> GigaChat:
    """
    Возвращает настроенный экземпляр GigaChat.
    Temperature=0.1 — низкая, чтобы решения были стабильными.
    """
    return GigaChat(
        credentials=GIGACHAT_CREDENTIALS,
        scope=GIGACHAT_SCOPE,
        model=GIGACHAT_MODEL,
        temperature=temperature,
        verify_ssl_certs=False,
        timeout=60,
    )