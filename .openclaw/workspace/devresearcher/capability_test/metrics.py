"""Calculate precision, recall, and F1 score from confusion-matrix counts."""

import argparse


def calculate_metrics(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Return precision, recall, and F1 score for the supplied counts."""
    if tp < 0 or fp < 0 or fn < 0:
        raise ValueError("TP, FP, and FN must be non-negative")

    precision_denominator = tp + fp
    recall_denominator = tp + fn

    precision = tp / precision_denominator if precision_denominator else 0.0
    recall = tp / recall_denominator if recall_denominator else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return precision, recall, f1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate precision, recall, and F1 score."
    )
    parser.add_argument("--tp", type=int, required=True, help="True positives")
    parser.add_argument("--fp", type=int, required=True, help="False positives")
    parser.add_argument("--fn", type=int, required=True, help="False negatives")
    args = parser.parse_args()

    precision, recall, f1 = calculate_metrics(args.tp, args.fp, args.fn)
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1 Score: {f1:.4f}")


if __name__ == "__main__":
    main()
