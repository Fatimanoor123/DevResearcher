# Metrics Calculator

`metrics.py` calculates precision, recall, and F1 score from true positives
(`TP`), false positives (`FP`), and false negatives (`FN`).

## Formulas

- **Precision** = `TP / (TP + FP)`
- **Recall** = `TP / (TP + FN)`
- **F1 score** = `2 × (Precision × Recall) / (Precision + Recall)`

If a denominator is zero, the program reports the corresponding metric as
`0.0000` instead of raising a division-by-zero error.

## Usage

From the `capability_test` directory, run:

```text
python metrics.py --tp 80 --fp 10 --fn 10
```

The program prints each metric to four decimal places.
