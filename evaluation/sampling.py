from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Iterable


CONTEXT_PATTERN = re.compile(
    r"Contact\s+Person|Director|Company\s+Secretary|Compliance\s+Officer|"
    r"Registered\s+Office|Corporate\s+Office|Address|Telephone|E-mail|Email|"
    r"Private\s+Limited|Limited|Ltd\.?|LLP",
    re.IGNORECASE,
)
HARD_NEGATIVE_PATTERN = re.compile(
    r"CIN|DIN|SEBI|Regulation|Section|₹|million|shares|Fiscal|dated|"
    r"Risk Factors|Audit Committee|Board of Directors|Government of India|"
    r"Registrar of Companies|\b\d{1,3}\.\d{1,2}%\b|\b[1-9]\d{2}\s?\d{3}\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SamplePlan:
    block_ids: list[str]
    seed: int
    target_size: int


def select_evaluation_sample(blocks: Iterable, seed: int = 42, target_size: int = 150) -> SamplePlan:
    block_list = [block for block in blocks if block.text.strip()]
    by_source: dict[str, list] = {"BODY": [], "TABLE": [], "HEADER": [], "FOOTER": []}
    for block in block_list:
        by_source.setdefault(block.source_type.value, []).append(block)

    selected: dict[str, object] = {}

    def add(items: list, count: int, *, randomize: bool = False) -> None:
        candidates = list(items)
        if randomize:
            random.Random(seed + len(selected)).shuffle(candidates)
        for block in candidates:
            if len(selected) >= target_size:
                return
            if block.block_id not in selected:
                selected[block.block_id] = block
                if sum(1 for _ in selected) >= target_size:
                    return
                count -= 1
                if count == 0:
                    return

    body = by_source.get("BODY", [])
    table = by_source.get("TABLE", [])
    headers = by_source.get("HEADER", [])
    footers = by_source.get("FOOTER", [])
    context_blocks = [b for b in block_list if CONTEXT_PATTERN.search(b.text)]
    hard_negative_blocks = [b for b in block_list if HARD_NEGATIVE_PATTERN.search(b.text)]

    add([b for b in context_blocks if b.source_type.value == "BODY"], 24)
    add([b for b in context_blocks if b.source_type.value == "TABLE"], 36)
    add(hard_negative_blocks, 24)
    add(headers, 5)
    add(footers, 5)
    add(body, 40, randomize=True)
    add(table, 45, randomize=True)
    add(block_list, target_size - len(selected), randomize=True)

    return SamplePlan(block_ids=list(selected), seed=seed, target_size=target_size)
