#!/usr/bin/env python3
"""
Generate citations from multiple LLMs across 5 domains.
Handles: GPT-4.1-nano (OpenAI API), Gemini (AI Hub), Groq Llama 70B & 8B (AI Hub)
Claude is handled separately.
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

DOMAINS = {
    "cs_ml": "transformer-based models for natural language processing and their evaluation benchmarks",
    "finance": "machine learning applications in credit risk assessment and financial forecasting",
    "biomedicine": "deep learning methods for medical image analysis and clinical diagnosis",
    "engineering": "energy efficiency optimization in smart buildings using IoT and machine learning",
    "social_science": "ESG disclosure quality assessment and corporate sustainability reporting standards",
}

PROMPT_TEMPLATE = """You are an academic researcher writing a literature review on the topic: "{topic}". Please recommend 25 relevant scholarly references published between 2015 and 2025. For EACH reference, provide the following in a structured JSON array format:

[
  {{
    "authors": ["First Author", "Second Author"],
    "title": "Exact paper title",
    "journal": "Journal or Conference name",
    "year": 2023,
    "volume": "12",
    "issue": "3",
    "pages": "100-120",
    "doi": "10.xxxx/xxxxx"
  }}
]

Please provide only real, verifiable references. Do not fabricate any citations. Return ONLY the JSON array, no other text."""

AI_HUB_URL = os.environ.get("AI_HUB_URL", "")  # optional gateway; falls back to direct provider APIs

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def call_openai(prompt, model="gpt-4.1-nano"):
    """Call OpenAI API."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("OPENAI_API_KEY="):
                        api_key = line.strip().split("=", 1)[1]
        if not api_key:
            # Try project .env
            env_path2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
            if os.path.exists(env_path2):
                with open(env_path2) as f:
                    for line in f:
                        if line.startswith("OPENAI_API_KEY="):
                            api_key = line.strip().split("=", 1)[1]

    if not api_key:
        return {"error": "No OPENAI_API_KEY found"}

    url = "https://api.openai.com/v1/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 4096,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return {"content": data["choices"][0]["message"]["content"], "model": model}
    except Exception as e:
        return {"error": str(e)}


def call_aihub(prompt, provider="gemini", model=None):
    """Call AI Hub LLM chat."""
    payload = {"prompt": prompt, "provider": provider}
    if model:
        payload["model"] = model

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(AI_HUB_URL, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read())
            return {"content": result.get("content", ""), "provider": result.get("provider_used", "")}
    except Exception as e:
        return {"error": str(e)}


def parse_citations(raw_text):
    """Extract JSON array of citations from LLM response."""
    if not raw_text:
        return []

    # Try to find JSON array in the response
    # Look for [...] pattern
    match = re.search(r'\[[\s\S]*\]', raw_text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Try the whole thing
    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        pass

    return []


def generate_for_llm(llm_name, call_fn, domains, delay=2):
    """Generate citations for one LLM across all domains."""
    results = {}
    for domain_key, topic in domains.items():
        prompt = PROMPT_TEMPLATE.format(topic=topic)
        print(f"  [{llm_name}] Generating for {domain_key}...", file=sys.stderr)

        response = call_fn(prompt)
        if "error" in response:
            print(f"  [{llm_name}] ERROR in {domain_key}: {response['error']}", file=sys.stderr)
            results[domain_key] = {"raw": response, "citations": [], "count": 0}
        else:
            raw_content = response.get("content", "")
            citations = parse_citations(raw_content)
            results[domain_key] = {
                "raw_response": raw_content[:500] + "..." if len(raw_content) > 500 else raw_content,
                "citations": citations,
                "count": len(citations),
            }
            print(f"  [{llm_name}] {domain_key}: {len(citations)} citations parsed", file=sys.stderr)

        time.sleep(delay)

    # Save results
    output_path = os.path.join(OUTPUT_DIR, f"citations_{llm_name}.json")
    with open(output_path, "w") as f:
        json.dump({"llm": llm_name, "domains": results}, f, indent=2, ensure_ascii=False)

    total = sum(r["count"] for r in results.values())
    print(f"  [{llm_name}] DONE: {total} total citations → {output_path}", file=sys.stderr)
    return total


def main():
    print("=== Citation Generation Pipeline ===", file=sys.stderr)
    print(f"Domains: {list(DOMAINS.keys())}", file=sys.stderr)

    totals = {}

    # 1. GPT-4.1-nano
    print("\n[1/4] GPT-4.1-nano (OpenAI API)...", file=sys.stderr)
    totals["gpt-4.1-nano"] = generate_for_llm(
        "gpt-4.1-nano",
        lambda p: call_openai(p, "gpt-4.1-nano"),
        DOMAINS,
        delay=3
    )

    # 2. Gemini 3 Flash
    print("\n[2/4] Gemini 3 Flash (AI Hub)...", file=sys.stderr)
    totals["gemini"] = generate_for_llm(
        "gemini",
        lambda p: call_aihub(p, provider="gemini"),
        DOMAINS,
        delay=5
    )

    # 3. Llama 3.3 70B
    print("\n[3/4] Llama 3.3 70B (Groq via AI Hub)...", file=sys.stderr)
    totals["llama70b"] = generate_for_llm(
        "llama70b",
        lambda p: call_aihub(p, provider="groq_llm"),
        DOMAINS,
        delay=3
    )

    # 4. Llama 3.1 8B
    print("\n[4/4] Llama 3.1 8B (Groq via AI Hub)...", file=sys.stderr)
    totals["llama8b"] = generate_for_llm(
        "llama8b",
        lambda p: call_aihub(p, provider="groq_llm", model="llama-3.1-8b-instant"),
        DOMAINS,
        delay=3
    )

    print("\n=== SUMMARY ===", file=sys.stderr)
    for name, count in totals.items():
        print(f"  {name}: {count} citations", file=sys.stderr)
    print(f"  TOTAL: {sum(totals.values())} citations", file=sys.stderr)


if __name__ == "__main__":
    main()
