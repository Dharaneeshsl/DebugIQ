import os
from typing import Dict, List

try:
    # OpenAI-compatible clients (OpenAI / Azure / third-party gateway)
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    # Groq-compatible OpenAI client
    from openai import OpenAI as GroqClient
except Exception:  # pragma: no cover
    GroqClient = None

import shap
import numpy as np

def _build_retrieval_corpus() -> List[Dict[str, str]]:
    """
    Lightweight retrieval corpus for RAG grounding.
    In production this can be backed by vector DB + incident docs.
    """
    return [
        {
            "category": "uvm_fatal",
            "content": "UVM fatal errors usually stop the test; inspect fatal calls, phase objections, and termination conditions.",
        },
        {
            "category": "uvm_scoreboard_mismatch",
            "content": "Scoreboard mismatches indicate divergence between expected and actual transactions; validate predictors and compare hooks.",
        },
        {
            "category": "uvm_phase_error",
            "content": "Phase errors often come from incorrect build/connect/run ordering or missing objection handling.",
        },
        {
            "category": "uvm_sequence_error",
            "content": "Sequence errors often involve sequencer arbitration or invalid sequence item constraints.",
        },
        {
            "category": "sva_assertion_failure",
            "content": "SVA assertion failures point to violated temporal properties; inspect antecedent signal stability and timing windows.",
        },
        {
            "category": "protocol_violation",
            "content": "Protocol sequencing issues usually start from invalid FSM transition, dropped ready/valid handshake, or stale transaction IDs.",
        },
        {
            "category": "timeout_error",
            "content": "Timeouts are often caused by blocked downstream dependency, backpressure deadlock, or clock-domain synchronization bug.",
        },
        {
            "category": "data_mismatch",
            "content": "Data mismatch typically comes from pipeline register corruption, byte-lane masking bugs, or incorrect endianness handling.",
        },
        {
            "category": "memory_error",
            "content": "Memory errors are frequently tied to ECC decode faults, address decoder overlap, or stale cache line metadata.",
        },
    ]


def retrieve_context(failure_context: dict, k: int = 2) -> List[str]:
    category = str(failure_context.get("category", "")).lower()
    module = str(failure_context.get("module", "")).lower()
    message = str(failure_context.get("message", "")).lower()

    scored = []
    for doc in _build_retrieval_corpus():
        text = doc["content"].lower()
        score: int = 0
        if doc["category"] == category:
            score = score + 3
        if module and module.replace("_", " ") in text:
            score = score + 1
        for i, token in enumerate(message.split()):
            if i >= 8:
                break
            if token in text:
                score = score + 1
        scored.append((score, doc["content"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    
    res = []
    for i, (s, c) in enumerate(scored):
        if i >= k:
            break
        if s > 0:
            res.append(c)
    return res


def generate_llm_explanation(failure_context: dict) -> str:
    retrieved = retrieve_context(failure_context)
    retrieved_text = "\n".join(f"- {item}" for item in retrieved) or "- No matching retrieval snippets"

    prompt = f"""
Analyze the following system failure log and provide a concise root cause explanation and debugging steps.

Failure ID: {failure_context.get('id')}
Module: {failure_context.get('module')}
Severity: {failure_context.get('severity')}
Log Message: {failure_context.get('message')}
Category: {failure_context.get('category')}
Context: {failure_context.get('context')}

Retrieved Knowledge:
{retrieved_text}

Return:
1) Most likely root cause (1-2 sentences)
2) What changed or triggered it (if inferable)
3) 3-5 concrete debugging actions (ordered)
""".strip()

    has_provider_key = False
    last_error = None

    # 1) Groq (primary, if configured)
    groq_key = (os.environ.get("CHATBOT_API_KEY") or os.environ.get("GROQ_KEY") or "").strip()
    groq_base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    if groq_key and GroqClient is not None:
        has_provider_key = True
        try:
            groq_model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
            groq = GroqClient(api_key=groq_key, base_url=groq_base_url)
            resp = groq.chat.completions.create(
                model=groq_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a production-grade debugging assistant for chip verification logs.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            last_error = exc

    # 2) Fallback: OpenAI-compatible APIs (if configured)
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key and OpenAI is not None:
        has_provider_key = True
        try:
            base_url = os.environ.get("OPENAI_BASE_URL")
            client = OpenAI(api_key=openai_key, base_url=base_url) if base_url else OpenAI(api_key=openai_key)
            model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a production-grade debugging assistant for chip verification logs."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            last_error = exc

    # 3) Fallback: Gemini (if configured)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key and genai is not None:
        has_provider_key = True
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as exc:
            last_error = exc

    if not has_provider_key:
        raise RuntimeError(
            "No LLM provider key configured. Set one of: CHATBOT_API_KEY, GROQ_KEY, OPENAI_API_KEY, GEMINI_API_KEY."
        )
    raise RuntimeError(f"All configured LLM providers failed. Last error: {last_error}")


def generate_llm_chat(messages: List[Dict[str, str]]) -> str:
    """
    Multi-turn chat completion using the same provider stack as generate_llm_explanation.
    `messages` items must be dicts with keys role and content (OpenAI-style).
    """
    if not messages:
        raise ValueError("messages must be non-empty")

    has_provider_key = False
    last_error = None

    groq_key = (os.environ.get("CHATBOT_API_KEY") or os.environ.get("GROQ_KEY") or "").strip()
    groq_base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    if groq_key and GroqClient is not None:
        has_provider_key = True
        try:
            groq_model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
            groq = GroqClient(api_key=groq_key, base_url=groq_base_url)
            resp = groq.chat.completions.create(
                model=groq_model,
                messages=messages,
                temperature=0.2,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            last_error = exc

    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key and OpenAI is not None:
        has_provider_key = True
        try:
            base_url = os.environ.get("OPENAI_BASE_URL")
            client = OpenAI(api_key=openai_key, base_url=base_url) if base_url else OpenAI(api_key=openai_key)
            model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            last_error = exc

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key and genai is not None:
        has_provider_key = True
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = "\n".join(f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in messages)
            response = model.generate_content(prompt)
            return (response.text or "").strip()
        except Exception as exc:
            last_error = exc

    if not has_provider_key:
        raise RuntimeError(
            "No LLM provider key configured. Set one of: CHATBOT_API_KEY, GROQ_KEY, OPENAI_API_KEY, GEMINI_API_KEY."
        )
    raise RuntimeError(f"All configured LLM providers failed. Last error: {last_error}")


def compute_shap_importance(features_array: np.ndarray, feature_names: list, weights: dict) -> dict:
    """
    Simulate SHAP for linear scoring function since the exact weights and values 
    completely determine the importance mechanically.
    A true SHAP explainer is used here as requested.
    """
    if len(features_array) < 2:
        return {f: 0.33 for f in feature_names}
        
    # Prediction function mapping standard feature matrix to score
    # x is shape (N, 3): [sev_val, freq_val, mod_val]
    def model_predict(x):
        return x[:, 0] * weights["severity"] + x[:, 1] * weights["frequency"] + x[:, 2] * weights["module"]

    # Use LinearExplainer or KernelExplainer
    explainer = shap.KernelExplainer(model_predict, features_array[:10])
    
    # Explain the specific instance (index 0 implies we pass just the instance)
    instance = features_array[0:1]
    shap_vals = explainer.shap_values(instance)
    
    vals = np.abs(shap_vals[0])
    total = np.sum(vals)
    if total == 0:
        return {f: 1.0/len(feature_names) for f in feature_names}
        
    # Fix IDE round typing by using Python float parsing with format
    return {feature_names[i]: float(f"{float(vals[i]/total):.3f}") for i in range(len(feature_names))}
