# Edge search with pre-registered parameters

- **A. Avellaneda-Lee (2010)** residual reversion: 60-day regression on the stock's SPDR sector ETF, OU fit of cumulative residuals, open |s| > 1.25, close long s > −0.5 / short s < 0.75, κ > 252/30; 2% of capital per position; point-in-time S&P 500. Parameters from the paper, untouched. (XLRE/XLC are spliced with SPY returns before their launch.)
- **B. ETF pairs**: the quarterly-reselected pair portfolio on 58 liquid ETFs, pairs only within asset groups, top 10.
- **C. Stock pairs**: reference from reports/pair_portfolio.md.

| strategy                   | period    |   sharpe_gross |   sharpe_net | cagr_net   | vol   | max_dd   |   beta_spy | gross_exposure   |
|:---------------------------|:----------|---------------:|-------------:|:-----------|:------|:---------|-----------:|:-----------------|
| A. Avellaneda-Lee (5 bps)  | 2013–2024 |           0.49 |        -0.16 | -3.6%      | 15.7% | -53.3%   |       0.25 | 352.6%           |
| A. Avellaneda-Lee (5 bps)  | 2013–2018 |           1.22 |        -0.13 | -1.0%      | 6.6%  | -17.8%   |       0.12 | 305.1%           |
| A. Avellaneda-Lee (5 bps)  | 2019–2024 |           0.34 |        -0.19 | -6.1%      | 21.2% | -53.3%   |       0.31 | 400.2%           |
| A. Avellaneda-Lee (10 bps) | 2013–2024 |           0.49 |        -0.81 | -12.9%     | 15.7% | -82.3%   |       0.25 | 352.6%           |
| A. Avellaneda-Lee (10 bps) | 2013–2018 |           1.22 |        -1.47 | -9.5%      | 6.6%  | -46.3%   |       0.12 | 305.1%           |
| A. Avellaneda-Lee (10 bps) | 2019–2024 |           0.34 |        -0.73 | -16.2%     | 21.1% | -68.1%   |       0.31 | 400.2%           |
| B. ETF pairs (5 bps)       | 2013–2024 |          -0.25 |        -0.32 | -1.1%      | 3.3%  | -16.5%   |       0.08 | 31.4%            |
| B. ETF pairs (5 bps)       | 2013–2018 |          -0.33 |        -0.4  | -1.2%      | 2.9%  | -8.5%    |       0.06 | 33.0%            |
| B. ETF pairs (5 bps)       | 2019–2024 |          -0.2  |        -0.26 | -1.0%      | 3.6%  | -10.9%   |       0.09 | 29.8%            |
| B. ETF pairs (10 bps)      | 2013–2024 |          -0.25 |        -0.39 | -1.3%      | 3.3%  | -18.4%   |       0.08 | 31.4%            |
| B. ETF pairs (10 bps)      | 2013–2018 |          -0.33 |        -0.47 | -1.4%      | 2.9%  | -9.4%    |       0.06 | 33.0%            |
| B. ETF pairs (10 bps)      | 2019–2024 |          -0.2  |        -0.32 | -1.2%      | 3.6%  | -11.6%   |       0.09 | 29.8%            |
| C. Stock pairs (10 bps)    | 2013–2024 |           0.16 |        -0.05 | -0.1%      | 2.3%  | -7.8%    |       0.03 | 33.7%            |
| C. Stock pairs (10 bps)    | 2013–2018 |          -0.16 |        -0.45 | -0.7%      | 1.5%  | -5.5%    |      -0.01 | 31.2%            |
| C. Stock pairs (10 bps)    | 2019–2024 |           0.35 |         0.15 | 0.4%       | 2.9%  | -5.4%    |       0.05 | 36.3%            |

## Most frequently selected ETF pairs

| pair     |   quarters |
|:---------|-----------:|
| GDX/GLD  |         14 |
| EWC/EWT  |         11 |
| EWA/EWC  |         11 |
| LQD/TIP  |         10 |
| AGG/SHY  |         10 |
| MUB/TIP  |          9 |
| GDXJ/GLD |          9 |
| GDXJ/SLV |          9 |
| HYG/SHY  |          8 |
| EWA/EWZ  |          8 |
