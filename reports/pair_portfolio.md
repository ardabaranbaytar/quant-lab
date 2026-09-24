# Multi-pair stat-arb on the point-in-time S&P 500 (2010–2024)

Quarterly re-selection: same GICS sub-industry, Engle-Granger p < 0.05 on 756 days of log prices, half-life 5–60 days, top 20 pairs (≤ 2 per stock), each 1/20 of capital; entry |z| > 2, exit z = 0; 10 bps costs. Universe: 497 tickers classified by today's GICS (removed companies can't be grouped — residual survivorship bias).

| variant                             | sharpe_before_costs   | total_return   | cagr   | volatility   |   sharpe | max_drawdown   |   beta_to_spy |   corr_to_spy | avg_gross_exposure   | annual_turnover   | risk_exits   |
|:------------------------------------|:----------------------|:---------------|:-------|:-------------|---------:|:---------------|--------------:|--------------:|:---------------------|:------------------|:-------------|
| no risk layer                       | 0.16                  | -1.7%          | -0.1%  | 2.3%         |    -0.05 | -7.8%          |          0.03 |          0.23 | 33.7%                | 4.91              | 0            |
| z-stop 4                            | 0.18                  | -2.6%          | -0.2%  | 1.6%         |    -0.13 | -4.9%          |          0.01 |          0.09 | 28.1%                | 5.07              | 0            |
| monitor (synthetic calibration)     | 0.09                  | -3.0%          | -0.3%  | 1.6%         |    -0.15 | -5.6%          |          0.02 |          0.16 | 25.7%                | 3.92              | 22           |
| monitor (real calibration, 2 votes) | 0.05                  | -4.5%          | -0.4%  | 2.0%         |    -0.18 | -6.6%          |          0.03 |          0.23 | 31.5%                | 4.64              | 15           |
| SPY buy & hold                      | —                     | 399.7%         | 14.4%  | 16.7%        |     0.89 | -33.7%         |          1    |          1    | —                    | —                 | —            |

## Calendar-year returns

|   Date | no risk layer   | z-stop 4   | monitor (synthetic calibration)   | monitor (real calibration, 2 votes)   | SPY    |
|-------:|:----------------|:-----------|:----------------------------------|:--------------------------------------|:-------|
|   2013 | -1.3%           | -0.9%      | -0.9%                             | -1.3%                                 | +29.3% |
|   2014 | +0.0%           | -0.5%      | +0.6%                             | -0.0%                                 | +13.5% |
|   2015 | -1.4%           | -2.7%      | -2.4%                             | -1.4%                                 | +1.2%  |
|   2016 | +0.8%           | +0.8%      | +0.6%                             | +0.8%                                 | +12.0% |
|   2017 | -2.0%           | -0.7%      | -0.0%                             | -0.4%                                 | +21.7% |
|   2018 | -0.1%           | +0.3%      | -1.0%                             | -0.3%                                 | -4.6%  |
|   2019 | +0.7%           | +0.7%      | +0.3%                             | +0.5%                                 | +31.2% |
|   2020 | +6.7%           | +4.0%      | +5.0%                             | +2.0%                                 | +18.3% |
|   2021 | -0.8%           | -1.4%      | -0.8%                             | -0.8%                                 | +28.7% |
|   2022 | -1.9%           | -0.8%      | -2.0%                             | -1.9%                                 | -18.2% |
|   2023 | +1.1%           | +2.0%      | +0.8%                             | +1.4%                                 | +26.2% |
|   2024 | -3.2%           | -3.3%      | -3.1%                             | -3.1%                                 | +25.3% |

## Selection statistics

- Periods: 48; pairs selected per period: mean 20.0
- Most frequent sub-industries:

| group                                        |   pair-periods |
|:---------------------------------------------|---------------:|
| Multi-Utilities                              |            131 |
| Health Care Equipment                        |             97 |
| Electric Utilities                           |             95 |
| Semiconductors                               |             36 |
| Transaction & Payment Processing Services    |             36 |
| Regional Banks                               |             35 |
| Industrial Machinery & Supplies & Components |             35 |
| Asset Management & Custody Banks             |             27 |
| Oil & Gas Exploration & Production           |             25 |
| Financial Exchanges & Data                   |             24 |
