# Reproducible AI/ML Research Protocol

This protocol defines a rigorous workflow for planning, conducting, evaluating,
and reporting AI/ML research. Its purpose is to make research traceable,
reproducible, evidence-based, and honest about uncertainty.

## 1. Research Question Formulation

1. State the problem, context, target population or task, and practical or
   scientific motivation.
2. Define the primary research question and, where useful, secondary questions.
3. Specify the hypotheses, expected relationships, constraints, and scope.
4. Define terminology, outcome variables, comparison conditions, and the date
   boundary for relevant evidence.
5. Convert the question into measurable objectives and acceptance criteria.

A strong question should be specific enough to test, feasible with available
resources, and meaningful in relation to prior work.

## 2. Literature Search

1. Create search terms from the key concepts, synonyms, acronyms, methods,
   datasets, and application domains.
2. Search appropriate scholarly indexes, publisher sites, official project
   repositories, standards bodies, and technical documentation.
3. Record each query, database or source, date searched, filters, and result
   counts when available.
4. Use backward citation searching, forward citation searching, and related-work
   discovery for important papers.
5. Prefer primary sources: original papers, official documentation, dataset or
   model cards, standards, and source repositories.

Do not treat a search-result snippet, abstract alone, blog post, or copied
summary as equivalent to reviewing the underlying source.

## 3. Source Evaluation

Evaluate each source for:

- Authority: authors, venue, organization, and provenance.
- Relevance: direct relationship to the research question.
- Currency: publication, revision, and access dates.
- Methodological quality: design, data, controls, and analysis.
- Reproducibility: availability of code, data, configuration, and details.
- Limitations, conflicts of interest, and possible incentives.
- Whether the claim is primary evidence or a secondary interpretation.

For consequential claims, corroborate with independent reputable sources when
possible. Record uncertainty when a source is inaccessible, ambiguous,
unverified, or contradicted by other evidence.

## 4. Paper Selection

Define inclusion and exclusion criteria before final selection. Criteria may
include topic, population, task, date range, language, publication type,
methodological quality, and availability of sufficient evidence.

Record screened, included, and excluded papers, including an exclusion reason.
Avoid selecting papers solely because their results support the preferred
hypothesis.

## 5. Evidence Extraction

Extract evidence systematically using a fixed form. Capture the exact claim,
source location, research question, method, dataset, sample or split, baseline,
metrics, main result, uncertainty, limitations, and relevance to the current
study.

Distinguish clearly between:

- **FACT:** directly supported by an inspected source or observed output.
- **INFERENCE:** a reasoned conclusion drawn from evidence.
- **ASSUMPTION:** a condition accepted for the study.
- **HYPOTHESIS:** a proposition to be tested.
- **UNVERIFIED:** information not yet checked against adequate evidence.

## 6. Literature Matrix

Maintain a matrix with at least these columns:

| Paper | Citation verified | Question | Task/domain | Dataset | Method | Baseline | Metrics | Main findings | Limitations | Reproducibility | Relevance |
|---|---|---|---|---|---|---|---|---|---|---|---|

Use stable identifiers such as DOI, publisher URL, arXiv ID, or repository URL.
Keep the matrix synchronized with the references used in the manuscript and
record when entries were last verified.

## 7. Research-Gap Identification

Identify gaps by comparing the matrix, not by asserting that no prior work
exists. Possible gaps include an untested population, missing baseline,
inconsistent evaluation, limited reproducibility, unresolved conflicting
results, data limitations, deployment constraints, or an unexplored method.

For each proposed gap, provide the supporting papers and explain why the gap is
material. Do not claim novelty unless the search scope and evidence justify the
claim; use narrower language when coverage is incomplete.

## 8. Hypothesis Formation

State each hypothesis in testable form, including:

- Independent variable or intervention.
- Dependent outcome and measurement.
- Population, dataset, or task.
- Baseline or control.
- Expected direction or effect where justified.
- Conditions under which the hypothesis may fail.

Define primary and secondary hypotheses before inspecting final results when
possible. Separate exploratory analyses from confirmatory analyses.

## 9. Dataset Selection

Document the dataset source, version, license, access date, task definition,
population, collection process, label provenance, known biases, missingness,
class balance, and ethical or privacy considerations.

Define train, validation, and test partitions before model comparison. Prevent
test-set leakage, duplicate contamination, temporal leakage, and overlap with
pretraining or external resources where relevant. Justify why the dataset is
appropriate and state limits to generalization.

## 10. Preprocessing

Specify every preprocessing step, including cleaning, filtering, labeling,
tokenization, resizing, normalization, augmentation, feature construction,
sampling, and missing-value handling.

Fit preprocessing parameters only on permitted training data. Version scripts
and configuration, record random seeds, preserve input/output counts, and
document exclusions. Ensure preprocessing is identical across baselines and
comparisons unless the difference is an explicit experimental variable.

## 11. Baseline Selection

Select baselines that are relevant, competitive, reproducible, and appropriate
to the task. Include a simple sanity baseline where useful, such as majority
class, random, heuristic, or linear performance.

Document baseline implementation, source, version, hyperparameters, training
budget, preprocessing, and evaluation protocol. Do not compare methods using
different data splits, metrics, or resource budgets without explaining the
impact.

## 12. Experiment Design

Before execution, write an experiment plan containing:

- Hypothesis and primary outcome.
- Baselines, controls, and comparison groups.
- Dataset versions and fixed splits.
- Model, algorithm, features, and hyperparameters.
- Variables changed and variables held constant.
- Compute, hardware, software, and time budget.
- Random seeds and number of independent runs.
- Ablations, sensitivity analyses, and failure analyses.
- Early-stopping, checkpoint, and model-selection rules.
- Predefined metrics and statistical analysis.

Change one meaningful factor at a time when causal interpretation is required.
Use a written plan or preregistration when appropriate, and record deviations
with their reason and impact.

## 13. Metrics

Choose metrics that match the task, decision, class balance, and error costs.
Define every metric mathematically or cite its authoritative definition.

For classification, consider appropriate per-class and aggregate measures;
for regression, report suitable error and calibration measures; for ranking,
generation, or retrieval, define the evaluation protocol and known limitations.
Report confidence intervals or dispersion where feasible, not only a single
point estimate. Do not select metrics after seeing results merely to improve
the apparent outcome.

## 14. Reproducibility

Preserve:

- Source code, commit or version identifier, and environment specification.
- Dataset names, versions, hashes or immutable references where permitted.
- Configuration files, hyperparameters, seeds, and split definitions.
- Hardware, operating system, library, driver, and runtime versions.
- Commands, logs, checkpoints, artifacts, and output locations.
- Randomness controls and known nondeterminism.
- Data access, licensing, privacy, and unavailable-artifact constraints.

Use deterministic settings where practical, but document when exact
determinism is impossible. A result is reproducible only to the extent that the
recorded artifacts and access conditions allow it.

## 15. Statistical Evaluation

Choose the statistical method before analyzing final results when possible.
Define the unit of analysis, independent observations, aggregation method,
confidence level, effect size, uncertainty interval, and multiple-comparison
policy. Check assumptions and use suitable alternatives when they fail.

Report practical significance as well as statistical significance. Avoid
overclaiming from small samples, repeated tuning on the test set, p-values
alone, or non-independent runs. Preserve raw results and analysis scripts.

## 16. Result Interpretation

Interpret results against the predefined hypothesis, baseline, metric, and
uncertainty. Distinguish observed results from explanations and speculation.
Discuss effect size, variance, failure cases, subgroup behavior, robustness,
compute or cost tradeoffs, and whether conclusions generalize beyond the test
conditions.

Do not treat correlation as causation without an appropriate design. Do not
claim superiority when comparisons are not equivalent or uncertainty overlaps
meaningfully. Report negative, null, unexpected, and contradictory findings.

## 17. Limitations and Ethics

Describe limitations in data, sampling, labels, measurement, model scope,
compute, reproducibility, statistical power, external validity, and evaluation.
Address privacy, consent, fairness, safety, misuse, environmental cost,
licensing, and affected stakeholders where applicable.

State what the study does not establish. Recommend future work only when it
follows from the documented evidence or limitation.

## 18. Reporting

Report the research question, related work, gap, hypothesis, method, data,
preprocessing, baselines, experiment plan, metrics, results, uncertainty,
limitations, ethical considerations, and conclusion in a traceable order.

Every material claim must have supporting evidence or an explicit uncertainty
label. References must be complete, consistently formatted, and retrievable.
Tables and figures must match the underlying data, include units and sample
sizes where relevant, and identify whether values are measured, derived,
simulated, illustrative, or reported by another source.

## 19. Integrity Rules

- Never fabricate citations, DOIs, URLs, quotations, papers, datasets, or source
  metadata.
- Never fabricate experimental results, benchmarks, metrics, plots, tables,
  statistical tests, or implementation details.
- Never present an expected, simulated, illustrative, or user-provided value as
  a measured result.
- Never make a material claim without evidence, a citation, or an explicit
  statement that it is an assumption or hypothesis.
- Never claim that an experiment, tool, search, code execution, or verification
  occurred unless it was actually performed and the output was observed.
- If evidence is missing, say: “I don't have enough information to verify
  that.” Then state the missing evidence and the next check required.
- Preserve negative results, failed runs, exclusions, and protocol deviations.
- Report inaccessible sources, unavailable tools, incomplete runs, and known
  threats to validity.

## 20. Standard Research Record Template

Copy this template for each study or experiment.

```text
# Research Record

Record ID:
Title:
Researcher:
Created:
Last updated:
Status: Planned | In progress | Completed | Blocked

## Research question

Primary question:
Secondary questions:
Motivation and intended decision:
Scope and date boundary:

## Literature and evidence

Search sources/databases:
Search queries:
Search dates:
Inclusion criteria:
Exclusion criteria and reasons:
Selected papers:
Literature matrix location:
Evidence summary:
Known source conflicts or gaps:

## Hypotheses

Primary hypothesis:
Secondary hypotheses:
Independent variables:
Dependent outcomes:
Baseline/control:
Predefined failure conditions:

## Dataset

Name and version:
Source and license:
Access date:
Task and population:
Label provenance:
Known bias, privacy, or ethics issues:
Train/validation/test split:
Leakage checks:

## Preprocessing

Steps:
Fitted parameters and fit split:
Filtering and exclusions:
Code/configuration version:
Random seeds:

## Experiment design

Models/methods:
Baselines:
Variables changed:
Variables held constant:
Hyperparameters:
Compute and time budget:
Number of runs:
Ablations/sensitivity analyses:
Stopping and model-selection rules:
Protocol deviations and reasons:

## Metrics and statistics

Primary metric and definition:
Secondary metrics and definitions:
Confidence level/interval method:
Effect-size method:
Multiple-comparison policy:
Statistical assumptions/checks:

## Reproducibility

Repository and commit:
Environment specification:
Hardware/OS/runtime:
Commands:
Dataset hashes or immutable references:
Logs/checkpoints/artifacts:
Known nondeterminism:

## Results

Execution status:
Runs actually completed:
Raw results location:
Summary statistics:
Uncertainty/variance:
Failure cases:
Measured vs derived vs illustrative values:

## Interpretation

Findings relative to hypotheses:
Alternative explanations:
Generalization limits:

## Limitations and ethics

Limitations:
Privacy/fairness/safety considerations:
Threats to validity:
Future work justified by evidence:

## Reporting and verification

Draft/report location:
References verified:
Claims with unresolved evidence:
Tests/checks performed:
Verification result:
Open issues:
Final reviewer or review date:
```
