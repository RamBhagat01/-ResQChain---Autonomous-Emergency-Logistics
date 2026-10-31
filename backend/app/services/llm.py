import json
import re
from typing import Dict, Any, Optional, List
from app.config import settings

# Rule-based fallback decision maker when Gemini API key is missing or unavailable
def rule_based_warehouse_selection(demand: Dict[str, Any], candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    best_candidate = None
    best_score = -999.0

    for c in candidates:
        has_stock = 1.0 if c["available_quantity"] >= demand["quantity"] else 0.0
        reliability = c.get("reliability", 0.8)
        dist_km = c.get("distance_km", 100.0)
        dist_penalty = min(dist_km, 300.0) / 300.0

        # Score formula: stock availability (50%), reliability (30%), proximity (20%)
        score = (has_stock * 0.5) + (reliability * 0.3) - (dist_penalty * 0.2)
        if score > best_score:
            best_score = score
            best_candidate = c

    if not best_candidate:
        best_candidate = candidates[0] if candidates else {"warehouse_id": 1, "name": "Default"}

    reasoning = (
        f"[Rule-based Heuristic] Selected {best_candidate['name']} (ID {best_candidate['warehouse_id']}): "
        f"stock={best_candidate['available_quantity']} units (demand requires {demand['quantity']}), "
        f"distance={best_candidate.get('distance_km', 0):.1f} km, "
        f"reliability rating={best_candidate.get('reliability', 0.9):.2f}."
    )

    return {
        "chosen_warehouse_id": best_candidate["warehouse_id"],
        "warehouse_name": best_candidate["name"],
        "reasoning": reasoning
    }

# Queries Gemini LLM with structured JSON output instructions, falling back to rule-based reasoning on failure
def ask_json(system_prompt: str, user_payload: Dict[str, Any]) -> Dict[str, Any]:
    # Check if Gemini API key is provided
    if not settings.GEMINI_API_KEY:
        if "candidates" in user_payload and "demand" in user_payload:
            return rule_based_warehouse_selection(user_payload["demand"], user_payload["candidates"])
        return {
            "status": "fallback",
            "reasoning": "[Fallback Mode] Gemini API key not configured. Operating under deterministic safety heuristics."
        }

    try:
        from google import genai

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = (
            f"{system_prompt}\n\n"
            f"Input Data:\n{json.dumps(user_payload, indent=2)}\n\n"
            "Return valid JSON only. Do not wrap in markdown code blocks or add text outside the JSON."
        )

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )

        text = response.text or ""
        # Strip code fences if present (```json ... ```)
        cleaned_text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text, flags=re.MULTILINE).strip()

        return json.loads(cleaned_text)

    except Exception as e:
        # Graceful fallback on rate limits or API network issues
        if "candidates" in user_payload and "demand" in user_payload:
            res = rule_based_warehouse_selection(user_payload["demand"], user_payload["candidates"])
            res["reasoning"] += f" (Gemini API fallback: {str(e)[:60]})"
            return res

        return {
            "status": "error_fallback",
            "reasoning": f"[Fallback] Swarm reasoning safely maintained via deterministic logic. ({str(e)[:60]})"
        }
