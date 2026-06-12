"""Agentic layer: LLM client, narration, tools, and the investigator loop."""

from .investigator import investigate
from .llm import llm_available
from .narrator import narrate

__all__ = ["narrate", "investigate", "llm_available"]
