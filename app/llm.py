import re

import httpx

from .embeddings import tokenize

from .config import get_settings
from .db import get_runtime_config


SYSTEM_PROMPT = """你是企业知识库助手。只根据给定资料回答。
要求：
1. 资料不足时明确说“我不知道”，不要编造。
2. 回答要简洁、可执行。
3. 引用事实时用 [来源序号] 标注。
"""


async def generate_answer(question: str, contexts: list[dict], history: list[dict], provider: str, model: str) -> str:
    if provider == "openai_compatible":
        try:
            return await _openai_compatible_answer(question, contexts, history, model)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 402:
                return "模型服务调用失败：DeepSeek 返回 402，请检查账户余额或计费状态。"
            if status in {401, 403}:
                return "模型服务调用失败：接口密钥无效或没有权限，请检查 DeepSeek 接口密钥。"
            return f"模型服务调用失败：DeepSeek 接口返回 HTTP {status}。"
        except httpx.HTTPError as exc:
            return f"模型服务调用失败：无法连接 DeepSeek 接口（{exc.__class__.__name__}）。"
    return _local_answer(question, contexts)


def _local_answer(question: str, contexts: list[dict]) -> str:
    config = get_runtime_config()
    min_context_score = float(config["local_answer_min_score"])
    if not contexts or contexts[0]["score"] < min_context_score:
        return "我不知道。当前知识库没有检索到足够相关的资料。"
    min_score = max(min_context_score, contexts[0]["score"] * float(config["local_answer_relative_score"]))
    contexts = [item for item in contexts if item["score"] >= min_score]
    lines = ["根据知识库资料，可以参考以下内容："]
    for index, item in enumerate(contexts[: int(config["local_answer_max_contexts"])], start=1):
        text = _best_snippet(question, item["text"])
        snippet_length = int(config["local_answer_snippet_length"])
        if len(text) > snippet_length:
            text = text[:snippet_length].rstrip() + "..."
        lines.append(f"{index}. {text} [{index}]")
    lines.append("如果需要更精确结论，请补充更具体的问题或上传对应制度文件。")
    return "\n".join(lines)


def _best_snippet(question: str, text: str) -> str:
    query_terms = set(tokenize(question))
    sentences = [part.strip() for part in re.split(r"(?<=[。！？；.!?])\s+|\n+", text) if part.strip()]
    if not sentences:
        return text.replace("\n", " ").strip()
    ranked = []
    for sentence in sentences:
        terms = set(tokenize(sentence))
        ranked.append((len(query_terms & terms), sentence))
    ranked.sort(key=lambda item: item[0], reverse=True)
    chosen = [ranked[0][1]] if ranked[0][0] > 0 else []
    if not chosen:
        chosen = [sentences[0]]
    return " ".join(chosen).replace("\n", " ").strip()


async def _openai_compatible_answer(question: str, contexts: list[dict], history: list[dict], model: str) -> str:
    settings = get_settings()
    config = get_runtime_config()
    if not settings.openai_api_key:
        return "我不知道。当前未配置 OPENAI_API_KEY，无法调用模型生成答案。"
    context_text = "\n\n".join(
        f"[来源{idx}] 文件：{item['metadata'].get('filename')}，片段：\n{item['text']}"
        for idx, item in enumerate(contexts, start=1)
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history[-6:]:
        messages.append({"role": "user", "content": item["question"]})
        messages.append({"role": "assistant", "content": item["answer"]})
    messages.append(
        {
            "role": "user",
            "content": f"用户问题：{question}\n\n知识库资料：\n{context_text or '无'}",
        }
    )
    async with httpx.AsyncClient(timeout=int(config["llm_timeout_seconds"])) as client:
        response = await client.post(
            f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={"model": model, "messages": messages, "temperature": float(config["llm_temperature"])},
        )
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"].strip()
