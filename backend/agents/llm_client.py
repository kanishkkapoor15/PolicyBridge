"""Shared LLM client for all agents — OpenAI SDK pointed at Tensorix API."""

import json
import logging
import time
from pathlib import Path

from openai import OpenAI

from config import TENSORIX_API_KEY, TENSORIX_BASE_URL, REASONING_MODEL, CHAT_MODEL, BASE_DIR

logger = logging.getLogger(__name__)

# Ensure logs directory exists
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
USAGE_LOG = LOGS_DIR / "usage.log"

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=TENSORIX_BASE_URL, api_key=TENSORIX_API_KEY)
    return _client


def _log_usage(model: str, prompt_tokens: int, completion_tokens: int, agent: str):
    """Append token usage to the usage log file."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "agent": agent,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    with open(USAGE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    agent_name: str = "unknown",
    max_retries: int = 3,
    temperature: float = 0.2,
) -> str:
    """Call the LLM with exponential backoff retry. Returns the response text."""
    client = get_client()
    model = model or CHAT_MODEL

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            text = response.choices[0].message.content or ""
            usage = response.usage
            if usage:
                _log_usage(model, usage.prompt_tokens, usage.completion_tokens, agent_name)
            return text
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"[{agent_name}] LLM call failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"[{agent_name}] LLM call failed after {max_retries} retries")


def parse_json_response(text: str) -> dict | list:
    """Extract and parse JSON from an LLM response, handling markdown fences and thinking tags."""
    cleaned = text.strip()

    # Strip <think>...</think> tags (DeepSeek R1 reasoning)
    import re
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding JSON object/array in the text
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = cleaned.find(start_char)
        if start != -1:
            # Find matching closing bracket
            depth = 0
            for i in range(start, len(cleaned)):
                if cleaned[i] == start_char:
                    depth += 1
                elif cleaned[i] == end_char:
                    depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[start:i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"Could not parse JSON from LLM response: {cleaned[:200]}...")
