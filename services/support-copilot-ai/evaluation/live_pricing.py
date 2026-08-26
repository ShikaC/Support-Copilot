from pathlib import Path

from evaluation.live_dataset import file_sha256
from evaluation.live_models import CostRecord, LiveCaseResult, PricingConfig


class PricingConfigError(Exception):
    pass


def apply_pricing(
    cases: tuple[LiveCaseResult, ...],
    pricing_path: Path | None,
    chat_model: str,
) -> tuple[LiveCaseResult, ...]:
    if pricing_path is None:
        return cases
    pricing = PricingConfig.model_validate_json(pricing_path.read_text(encoding="utf-8"))
    if pricing.chat_model != chat_model:
        raise PricingConfigError("pricing model does not match active chat model")
    checksum = file_sha256(pricing_path)
    priced: list[LiveCaseResult] = []
    for case in cases:
        usage = case.usage
        if usage.availability == "unavailable" or usage.input_tokens is None or usage.output_tokens is None:
            priced.append(case)
            continue
        amount = (
            usage.input_tokens * pricing.input_per_million_tokens
            + usage.output_tokens * pricing.output_per_million_tokens
        ) / 1_000_000
        priced.append(case.model_copy(update={"cost": CostRecord(
            amount=round(amount, 8),
            currency=pricing.currency,
            pricing_source=pricing.pricing_source,
            pricing_source_checksum=checksum,
        )}))
    return tuple(priced)
