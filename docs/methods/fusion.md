# Multi-view fusion

Implementation: `plate_reader/fusion.py`. Property tests: `tests/test_fusion.py`.
Comparison numbers below are rendered from `results/eval_views.json`; synthetic results are
not real-world accuracy.

## Setting

A car is photographed several times. Each view $v = 1, \dots, N$ (a photo, or a thresholding
variant of a crop) is read by a recogniser that returns grammar-valid hypotheses with
probabilities $p_v(s)$: for the CRNN, the constrained beam renormalised over its strings at
the calibrated temperature; for the EasyOCR baseline, normalised vote shares. A view may
abstain (no hypothesis), and then it contributes nothing.

## Probabilistic fusion

Candidates are the grammar-valid strings any view proposed,

$$
C = \bigcup_{v} \{\, s : p_v(s) > 0 \,\}, \qquad C \subseteq L,
$$

where $L$ is the language of the plate automaton. Each view's distribution is renormalised
over $C$, with a floor $\varepsilon$ for strings the view did not propose (so that one view
cannot veto a candidate outright):

$$
\tilde p_v(s) = \frac{\max\big(p_v(s), \varepsilon\big)}{\sum_{s' \in C} \max\big(p_v(s'), \varepsilon\big)} .
$$

The fused score and posterior are

$$
S(s) = \sum_{v} w_v \log \tilde p_v(s), \qquad
\pi(s) = \frac{\exp S(s)}{\sum_{s' \in C} \exp S(s')}, \qquad
\hat s = \arg\max_{s \in C} \pi(s),
$$

with ties broken by token order. The reported confidence is $\pi(\hat s)$.

**Why a product.** If the views are conditionally independent given the plate, Bayes' rule
gives $p(s \mid x_1, \dots, x_N) \propto p(s)^{1-N} \prod_v p(s \mid x_v)$. Under a uniform
prior over the candidates the prior factor is constant, so with all weights equal to one
$\pi(s) \propto \prod_v \tilde p_v(s)$: the fused posterior is the normalised product of the
per-view posteriors. Weights $w_v \le 1$ temper the evidence of unreliable views
(logarithmic opinion pooling).

**Weights.** $w_v = c_v \, \frac{\sigma_v}{\sigma_v + \sigma_{1/2}}$, where $c_v$ is the
detector's confidence for the view, $\sigma_v$ the variance of the Laplacian of the crop (a
label-free sharpness measure) and $\sigma_{1/2}$ the sharpness at which the quality term is
one half (`SHARPNESS_HALF` in `fusion.py`). Crops without a detector use $c_v = 1$.

## Per-position character posteriors

Every candidate is aligned to the winner by a minimum-cost Levenshtein alignment
$A(\hat s, s)$ (ties prefer substitution, then deletion, then insertion, which makes the
alignment a function of its inputs). For each position $i$ of the winner and each symbol
$a$ (or the gap $\varnothing$ when the candidate has nothing there),

$$
P_i(a) = \frac{\sum_{v} \sum_{s \in C} w_v \, \tilde p_v(s) \, [A(\hat s, s)_i = a]}
              {\sum_{v} \sum_{s \in C} w_v \, \tilde p_v(s) \, [A(\hat s, s)_i \neq \text{none}]} .
$$

$P_i(\hat s_i)$ is the confidence of the $i$-th character, which the dashboard draws as the
character heatmap.

## Properties (tested with hypothesis)

- **Permutation invariance.** Sums use `math.fsum` (exactly rounded) and ties break on the
  token string, so reordering the views changes nothing, bit for bit.
- **Single-view consistency.** With one view the winner is that view's argmax for any
  positive weight, and with weight one $\pi = \tilde p_1$.
- **Monotonicity in weights.** For $c = \arg\max_s \tilde p_v(s)$,
  $\frac{\partial \log \pi(c)}{\partial w_v} = \log \tilde p_v(c) - \mathbb{E}_{\pi}\big[\log \tilde p_v\big] \ge 0$,
  so giving a view more weight never lowers the posterior of what that view believes.
- Abstaining views change nothing; a view repeated twice equals that view at weight two.

## Prediction sets for fused reads

A conformal threshold is only valid for the kind of read it was calibrated on, so each
number of views $K$ has its own threshold $\hat q_K$, fitted on separate synthetic multi-view
calibration sets by fusing the first $K$ views exactly as the service does; the service picks
the largest calibrated $K$ not above the number of photos that proposed a plate (a photo that
proposes nothing contributes nothing to the fusion). An empty set is a signal,
not a bug: it means no plate can be certified at the stated level, so the service sends such
reads to human review by default.

<!-- BEGIN RENDER fused-calibration -->
**Synthetic results are not real-world accuracy.** Model `5348143705d4`; thresholds fitted on 1000 synthetic multi-view calibration sets (seed 1008), coverage measured on 200 separate sets with a joint bootstrap; real multi-photo data must refit them.

| Views | Level | Threshold | Coverage | Mean set size | Empty sets |
|---|---|---|---|---|---|
| 1 | 90% | `1.58e-03` | 0.930 [0.875, 0.965] | 0.930 [0.875, 0.965] | 0.070 |
| 1 | 95% | `3.00e-03` | 0.945 [0.910, 0.975] | 0.945 [0.910, 0.975] | 0.055 |
| 3 | 90% | `1.82e-10` | 0.895 [0.845, 0.940] | 0.895 [0.845, 0.940] | 0.105 |
| 3 | 95% | `7.24e-10` | 0.945 [0.905, 0.975] | 0.945 [0.905, 0.975] | 0.055 |
| 5 | 90% | `2.69e-17` | 0.900 [0.855, 0.940] | 0.900 [0.855, 0.940] | 0.100 |
| 5 | 95% | `1.90e-16` | 0.940 [0.905, 0.970] | 0.940 [0.905, 0.970] | 0.060 |
<!-- END RENDER fused-calibration -->

## Baseline: the legacy vote

The original pipeline sums each reading's vote weights $u$ (EasyOCR confidences) times the
detector confidence, $V(s) = \sum_v \sum_{(s,u)} u \, c_v$, takes $\hat s = \arg\max V$, and
reports the share $V(\hat s) / \sum_s V(s)$. That share is relative support, not a
probability: two weak views outvote one confident view, which the product above does not.

## Results

<!-- BEGIN RENDER fusion-comparison -->
**Synthetic results are not real-world accuracy.** Multi-view synthetic sets: n = 200 plates with up to 5 views each (generator seed 1007); the first k views of every set are fused; values with bootstrap intervals over sets.

Multi-view sets (exact match of the fused read; n = 200 sets, bootstrap over sets):

| Recogniser | Fusion | 1 view(s) | 3 view(s) | 5 view(s) |
|---|---|---|---|---|
| easyocr | legacy_vote | 0.295 [0.235, 0.360] | 0.545 [0.475, 0.615] | 0.585 [0.515, 0.650] |
| easyocr | probabilistic | 0.295 [0.235, 0.360] | 0.465 [0.395, 0.530] | 0.520 [0.445, 0.590] |
| easyocr | probabilistic_weighted | 0.295 [0.235, 0.360] | 0.475 [0.405, 0.540] | 0.520 [0.445, 0.585] |
| crnn-greedy | legacy_vote | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-greedy | probabilistic | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-greedy | probabilistic_weighted | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam | legacy_vote | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam | probabilistic | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam | probabilistic_weighted | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |

Calibration and conformal sets of the fused read (each number of views has its own threshold, fitted on separate synthetic multi-view sets; see `results/calibration_fused.json`):

| Recogniser | Fusion | Views | ECE | Set coverage | Mean set size |
|---|---|---|---|---|---|
| easyocr | legacy_vote | 1 | 0.166 [0.120, 0.217] | n/a | n/a |
| easyocr | legacy_vote | 5 | 0.102 [0.072, 0.153] | n/a | n/a |
| easyocr | probabilistic | 1 | 0.166 [0.120, 0.217] | n/a | n/a |
| easyocr | probabilistic | 5 | 0.187 [0.139, 0.242] | n/a | n/a |
| easyocr | probabilistic_weighted | 1 | 0.160 [0.116, 0.211] | n/a | n/a |
| easyocr | probabilistic_weighted | 5 | 0.202 [0.153, 0.259] | n/a | n/a |
| crnn-greedy | legacy_vote | 1 | 0.010 [0.000, 0.025] | n/a | n/a |
| crnn-greedy | legacy_vote | 5 | 0.003 [0.001, 0.006] | n/a | n/a |
| crnn-greedy | probabilistic | 1 | 0.010 [0.000, 0.025] | n/a | n/a |
| crnn-greedy | probabilistic | 5 | 0.000 [0.000, 0.000] | n/a | n/a |
| crnn-greedy | probabilistic_weighted | 1 | 0.010 [0.000, 0.025] | n/a | n/a |
| crnn-greedy | probabilistic_weighted | 5 | 0.000 [0.000, 0.000] | n/a | n/a |
| crnn-beam | legacy_vote | 1 | 0.010 [0.000, 0.025] | n/a | n/a |
| crnn-beam | legacy_vote | 5 | 0.004 [0.001, 0.007] | n/a | n/a |
| crnn-beam | probabilistic | 1 | 0.010 [0.003, 0.018] | 0.930 [0.895, 0.960] | 0.930 [0.895, 0.960] |
| crnn-beam | probabilistic | 5 | 0.000 [0.000, 0.000] | 0.900 [0.855, 0.940] | 0.900 [0.855, 0.940] |
| crnn-beam | probabilistic_weighted | 1 | 0.033 [0.024, 0.051] | 0.335 [0.270, 0.400] | 0.335 [0.270, 0.400] |
| crnn-beam | probabilistic_weighted | 5 | 0.000 [0.000, 0.000] | 0.250 [0.190, 0.305] | 0.250 [0.190, 0.305] |
<!-- END RENDER fusion-comparison -->
