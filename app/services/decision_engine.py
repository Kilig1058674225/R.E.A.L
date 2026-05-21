from __future__ import annotations

from app.models import (
    ActionType,
    EvaluationRequest,
    EvaluationResponse,
    OptionEvaluationInput,
    OptionEvaluationResult,
)


HIGH_STAKES_TERMS = [
    "辞职",
    "换工作",
    "跳槽",
    "转行",
    "创业",
    "贷款",
    "借钱",
    "投资",
    "结婚",
    "离婚",
    "搬家",
    "移民",
    "合同",
    "手术",
    "治疗",
    "加入组织",
]

SEARCH_TERMS = [
    "联网",
    "搜索",
    "搜",
    "实时",
    "网页",
    "浏览",
    "查",
    "核验",
    "证据",
    "价格",
    "政策",
    "法律",
    "法规",
    "公司",
    "机构",
    "产品",
    "最新",
    "新闻",
    "收益",
    "风险",
    "医生",
    "药",
    "投资",
]

RUIN_FLAGS = {
    "health",
    "mental_health",
    "cashflow",
    "debt",
    "legal",
    "credit",
    "freedom",
    "family",
    "judgment",
}


def classify_problem(text: str) -> dict[str, object]:
    normalized = text.lower()
    high_stakes = any(term in text for term in HIGH_STAKES_TERMS)
    search_required = any(term in text for term in SEARCH_TERMS)
    urgent = any(term in text for term in ["今天", "马上", "立刻", "紧急", "deadline", "urgent"])

    if urgent and high_stakes:
        classification = "chaotic_or_high_pressure"
    elif high_stakes and search_required:
        classification = "complex_analyzable"
    elif high_stakes:
        classification = "complex_uncertain"
    elif "买" in text or "选择" in text or "哪个" in text or "which" in normalized:
        classification = "analyzable"
    else:
        classification = "clarify_first"

    return {
        "classification": classification,
        "urgency": "high" if urgent else "normal",
        "stakes": "high" if high_stakes else "medium",
        "search_required": search_required or high_stakes,
    }


def expected_value(option: OptionEvaluationInput) -> float | None:
    if not option.outcomes:
        return None
    total_probability = sum(outcome.probability for outcome in option.outcomes)
    if total_probability <= 0:
        return None
    return sum(outcome.probability * outcome.utility for outcome in option.outcomes) / total_probability


def mcda_scores(request: EvaluationRequest) -> dict[str, float]:
    if not request.criteria:
        return {}

    total_weight = sum(criterion.weight for criterion in request.criteria)
    if total_weight <= 0:
        return {}

    scores: dict[str, float] = {}
    for criterion in request.criteria:
        weight = criterion.weight / total_weight
        for label, score in criterion.scores.items():
            scores[label] = scores.get(label, 0.0) + weight * max(0.0, min(10.0, score))
    return scores


def risk_level(option: OptionEvaluationInput) -> str:
    has_ruin = bool(RUIN_FLAGS.intersection(set(option.ruin_flags)))
    if has_ruin and (option.control_cost >= 0.6 or option.reversibility <= 0.3):
        return "ruin"
    if has_ruin or option.control_cost >= 0.7 or option.reversibility <= 0.2:
        return "high"
    if option.control_cost >= 0.4 or option.reversibility <= 0.5:
        return "medium"
    return "low"


def recommend(option: OptionEvaluationInput, ev: float | None, mcda: float | None) -> tuple[ActionType, list[str]]:
    notes: list[str] = []
    level = risk_level(option)

    if level == "ruin":
        notes.append("Anti-ruin gate triggered: downside can affect the basic base.")
        return "reject", notes

    if level == "high":
        notes.append("High downside or low reversibility: avoid heavy commitment.")
        if option.information_value >= 0.5:
            return "small_experiment", notes
        return "observe", notes

    if ev is not None and ev < -1:
        notes.append("Expected value is negative enough to avoid commitment.")
        return "observe", notes

    if option.information_value >= 0.65:
        notes.append("Information value is high: buy information before deciding.")
        return "small_experiment", notes

    if (ev is not None and ev >= 2) or (mcda is not None and mcda >= 7):
        notes.append("Upside looks meaningful and risk is not high.")
        return "stage_gated_increase", notes

    notes.append("Default to low-commitment observation until evidence improves.")
    return "observe", notes


def evaluate(request: EvaluationRequest) -> EvaluationResponse:
    mcda_by_label = mcda_scores(request)
    results: list[OptionEvaluationResult] = []

    for option in request.options:
        ev = expected_value(option)
        mcda = mcda_by_label.get(option.option_label)
        action, notes = recommend(option, ev, mcda)
        results.append(
            OptionEvaluationResult(
                option_label=option.option_label,
                expected_value=ev,
                mcda_score=mcda,
                risk_level=risk_level(option),
                recommendation=action,
                notes=notes,
            )
        )

    best_action = choose_best_action(results)
    summary = summarize(results, best_action)
    return EvaluationResponse(results=results, best_action=best_action, summary=summary)


def choose_best_action(results: list[OptionEvaluationResult]) -> ActionType:
    priority: dict[ActionType, int] = {
        "reject": 0,
        "observe": 1,
        "small_experiment": 2,
        "stage_gated_increase": 3,
    }
    if not results:
        return "observe"
    if any(result.risk_level == "ruin" for result in results):
        return "reject"
    return max((result.recommendation for result in results), key=lambda item: priority[item])


def summarize(results: list[OptionEvaluationResult], best_action: ActionType) -> str:
    if not results:
        return "No options were evaluated yet."
    if best_action == "reject":
        return "At least one option triggers an anti-ruin concern. Do not commit before lowering downside."
    if best_action == "small_experiment":
        return "The best next move is to buy information through a small, reversible experiment."
    if best_action == "stage_gated_increase":
        return "A staged increase is reasonable if stop conditions are explicit."
    return "Keep observing until evidence, reversibility, or upside improves."
