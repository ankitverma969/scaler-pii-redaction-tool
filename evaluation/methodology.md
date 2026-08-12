# Evaluation Methodology

Phase 12 evaluates detector output only. It does not evaluate synthetic replacement quality and it does not tune detectors from the evaluation labels.

The real-RHP evaluation uses a private, Git-ignored ground-truth JSONL file with exact `[start, end)` offsets over deterministic `TextBlock` logical text. Detector predictions are scored with strict exact span plus exact PII type matching.

The synthetic capability evaluation is public-safe and separate from the real-RHP metrics. It exists to demonstrate support for all nine required categories, including categories with no confirmed real-RHP positives.

Accuracy is reported as candidate-level accuracy over manually annotated positive PII spans plus explicit hard-negative candidate spans. Character or token accuracy is intentionally avoided because the overwhelming true-negative space would make it misleadingly high.
