# Survivorship-bias study (2010–2024)

Strategy: monthly cross-sectional momentum, lookback 60d, top 20, costs 10 bps.

| universe                               |   tickers | total_return   | cagr   |   sharpe | max_drawdown   |   delisting_events |
|:---------------------------------------|----------:|:---------------|:-------|---------:|:---------------|-------------------:|
| A. Today's S&P 500 (biased)            |       503 | 2615.8%        | 25.1%  |     1.09 | -35.5%         |                  0 |
| A2. Ever-members, no date filter       |       592 | 6050.7%        | 32.3%  |     1.07 | -44.9%         |                  0 |
| B. Point-in-time, delisting=last_price |       592 | 314.0%         | 10.1%  |     0.55 | -40.2%         |                  0 |
| B. Point-in-time, delisting=shumway    |       592 | 314.0%         | 10.1%  |     0.55 | -40.2%         |                  0 |
| B. Point-in-time, delisting=total_loss |       592 | 314.0%         | 10.1%  |     0.55 | -40.2%         |                  0 |
| SPY buy & hold                         |         1 | 557.4%         | 13.6%  |     0.83 | -33.7%         |                  0 |

## Where the biased edge comes from

Stocks the biased universe (A) held *before* they joined the S&P 500 — bought because we already know they will become large caps:

|      |   months_held | joined_index   |   held_while_not_member |
|:-----|--------------:|:---------------|------------------------:|
| TPL  |            45 | 2024-11-26     |                      44 |
| CVNA |            40 | 2025-12-22     |                      40 |
| DXCM |            44 | 2020-05-12     |                      37 |
| TSLA |            46 | 2020-12-21     |                      34 |
| SMCI |            35 | 2024-03-18     |                      33 |
| AXON |            38 | 2023-05-04     |                      33 |
| TTD  |            32 | 2025-07-18     |                      32 |
| BLDR |            34 | 2023-12-18     |                      31 |
| LULU |            31 | 2023-10-18     |                      30 |
| COHR |            25 | 2026-03-23     |                      25 |
| TKO  |            25 | 2025-03-24     |                      25 |
| GNRC |            30 | 2021-03-22     |                      25 |
| XYZ  |            25 | 2025-07-23     |                      25 |
| PODD |            27 | 2023-03-15     |                      25 |
| FIX  |            23 | 2025-12-22     |                      23 |

## Data coverage of point-in-time members

- Members at any point: 813; with no Yahoo prices: 221 (27%)
- Coverage at rebalance dates: mean 80.0%, min 64.7%

|      | coverage   |
|-----:|:-----------|
| 2010 | 65.8%      |
| 2011 | 66.7%      |
| 2012 | 68.7%      |
| 2013 | 70.7%      |
| 2014 | 71.7%      |
| 2015 | 73.7%      |
| 2016 | 76.8%      |
| 2017 | 79.8%      |
| 2018 | 81.6%      |
| 2019 | 84.4%      |
| 2020 | 87.4%      |
| 2021 | 89.3%      |
| 2022 | 92.2%      |
| 2023 | 94.7%      |
| 2024 | 96.2%      |
