# ML entry filter for pairs trading (2016–2024 out-of-sample)

1334 entry episodes from quarterly-selected S&P 500 pairs; 50.4% profitable after 20 bps round-trip costs. Walk-forward by calendar year, purged: each year's model sees only episodes that had closed before 1 January. A signal is taken when P(profit) exceeds the training base rate.

## Prediction quality (all test years pooled)

| model               |   test_episodes |   auc | base_hit_rate   | accepted_share   | hit_rate_accepted   | mean_pnl_all   | mean_pnl_accepted   | mean_pnl_rejected   |
|:--------------------|----------------:|------:|:----------------|:-----------------|:--------------------|:---------------|:--------------------|:--------------------|
| logistic regression |            1044 | 0.532 | 51.6%           | 50.7%            | 52.9%               | +0.03%         | +0.56%              | -0.53%              |
| gradient boosting   |            1044 | 0.518 | 51.6%           | 56.7%            | 52.9%               | +0.03%         | +0.06%              | -0.02%              |

Placebo (labels shuffled within year, same pipeline): AUC **0.507**.

## Gradient boosting by test year

|      |   episodes |   auc | hit_all   | hit_accepted   | pnl_all   | pnl_accepted   |
|-----:|-----------:|------:|:----------|:---------------|:----------|:---------------|
| 2016 |        105 | 0.645 | 58.1%     | 70.0%          | -0.01%    | +0.80%         |
| 2017 |        115 | 0.544 | 46.1%     | 50.9%          | -0.19%    | +0.44%         |
| 2018 |         94 | 0.589 | 57.4%     | 61.4%          | +0.21%    | +0.26%         |
| 2019 |        142 | 0.514 | 57.7%     | 57.1%          | +0.19%    | +0.19%         |
| 2020 |        182 | 0.529 | 59.9%     | 60.3%          | +0.56%    | +0.71%         |
| 2021 |         93 | 0.576 | 45.2%     | 51.1%          | +0.25%    | -0.10%         |
| 2022 |        107 | 0.339 | 38.3%     | 32.5%          | -0.61%    | -0.90%         |
| 2023 |        101 | 0.395 | 60.4%     | 48.5%          | +0.60%    | -0.24%         |
| 2024 |        105 | 0.476 | 34.3%     | 36.0%          | -1.12%    | -1.55%         |

## Portfolio impact

| portfolio   |   sharpe_before_costs | total_return   | cagr   | volatility   |   sharpe | max_drawdown   | avg_gross_exposure   |
|:------------|----------------------:|:---------------|:-------|:-------------|---------:|:---------------|:---------------------|
| all signals |                  0.27 | 1.0%           | 0.1%   | 2.5%         |     0.06 | -6.7%          | 34.3%                |
| ML-filtered |                  0.27 | 1.6%           | 0.2%   | 1.9%         |     0.1  | -5.7%          | 22.1%                |

|   Date | all signals   | ML-filtered   |
|-------:|:--------------|:--------------|
|   2016 | +0.8%         | +0.3%         |
|   2017 | -2.0%         | -0.3%         |
|   2018 | -0.1%         | +0.2%         |
|   2019 | +0.7%         | +0.3%         |
|   2020 | +6.7%         | +5.4%         |
|   2021 | -0.8%         | +0.4%         |
|   2022 | -1.9%         | -2.1%         |
|   2023 | +1.1%         | -0.4%         |
|   2024 | -3.2%         | -2.1%         |

## Permutation importance (mean drop in test AUC)

|                  |   importance |
|:-----------------|-------------:|
| days_into_period |       0.0179 |
| pvalue           |       0.0121 |
| spread_std       |       0.0113 |
| trend_tstat      |       0.0079 |
| vol_ratio_b      |       0.0061 |
| roll_half_life   |       0.0044 |
| move_share_a     |       0.0044 |
| z_max_20d        |       0.002  |
| days_left        |       0.0015 |
| vol_ratio_a      |       0.0013 |
| df_tstat         |       0.0007 |
| corr_drop        |       0.0006 |
| z_persistence    |       0.0004 |
| mkt_ret_20d      |       0.0004 |
| mkt_vol_20d      |       0.0003 |
| ret_5d_cheap_leg |      -0.0004 |
| divergence       |      -0.0018 |
| idio_vol_spike   |      -0.0021 |
| z_jump_5d        |      -0.0024 |
| cusum            |      -0.0027 |
| half_life        |      -0.0034 |
| abs_z            |      -0.0034 |
| ret_5d_rich_leg  |      -0.0063 |
| abs_beta         |      -0.0087 |
| formation_corr   |      -0.0197 |

## Robustness: 4298 episodes from every cointegrated pair

Training on ~3x more episodes (top 100 pairs per period) is the real test of whether the small-sample signal above is genuine.

| model               |   test_episodes |   auc | base_hit_rate   | accepted_share   | hit_rate_accepted   | mean_pnl_all   | mean_pnl_accepted   | mean_pnl_rejected   |
|:--------------------|----------------:|------:|:----------------|:-----------------|:--------------------|:---------------|:--------------------|:--------------------|
| logistic regression |            3587 | 0.486 | 48.9%           | 59.5%            | 48.7%               | -0.08%         | -0.02%              | -0.16%              |
| gradient boosting   |            3587 | 0.494 | 48.9%           | 58.5%            | 48.0%               | -0.08%         | -0.21%              | +0.11%              |

## Conclusion

With these entry-time features, whether an individual pair trade ends in profit is essentially unpredictable: the modest AUC on the small dataset disappears on the larger one, and yearly AUC flips sign around the 2022 rate-regime change. The filter is not used by default.
