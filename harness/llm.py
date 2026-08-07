import os
from dotenv import load_dotenv
from langchain_core.rate_limiters import InMemoryRateLimiter
from harness import config

load_dotenv()
_rate = InMemoryRateLimiter(requests_per_second=0.5, check_every_n_seconds=0.1, max_bucket_size=2)

def _gemini():
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=config.GEMINI_MODEL,
                                  google_api_key=os.environ["GEMINI_API_KEY"],
                                  rate_limiter=_rate, max_retries=3,
                                  max_output_tokens=8000)   # room to emit whole files without truncation

def _groq():
    from langchain_groq import ChatGroq
    return ChatGroq(model=config.GROQ_MODEL, api_key=os.environ["GROQ_API_KEY"],
                    rate_limiter=_rate, max_retries=3,
                    max_tokens=8000)                          # room to emit whole files without truncation

def _anthropic():
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=config.ANTHROPIC_MODEL, api_key=os.environ["ANTHROPIC_API_KEY"],
                         rate_limiter=_rate, max_retries=3, max_tokens=8000)

def _deepseek():
    from langchain_deepseek import ChatDeepSeek
    return ChatDeepSeek(model=config.DEEPSEEK_MODEL, api_key=os.environ["DEEPSEEK_API_KEY"],
                        rate_limiter=_rate, max_retries=3, max_tokens=8000)

# provider registry — lazy imports, so a provider only needs its package installed when selected
_BUILDERS = {"gemini": _gemini, "groq": _groq, "anthropic": _anthropic, "deepseek": _deepseek}

def make_llm(provider: str | None = None):
    name = (provider or os.getenv("LLM_PROVIDER") or config.LLM_PROVIDER).lower()
    if name not in _BUILDERS:
        raise ValueError(f"Unknown provider '{name}'. Options: {list(_BUILDERS)}")
    return _BUILDERS[name]()
