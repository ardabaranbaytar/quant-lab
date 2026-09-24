# Break monitor on real pairs (2010–2024)

## Why two calibrations

Thresholds calibrated on synthetic stable pairs flag healthy real pairs for hundreds of days: real spreads are far less well-behaved than an Ornstein-Uhlenbeck process. Re-calibrating on 35 same-industry pairs that share no ticker with the test cases (99th percentile per detector) swings to the other extreme: real pairs diverge so often that 'normal' becomes very wide and nothing is flagged. Neither calibration alone is usable.

|                |   synthetic |   real |
|:---------------|------------:|-------:|
| df_tstat       |       0.021 |  2.295 |
| cusum          |      31.04  | 90.612 |
| z_persistence  |       0.35  |  0.75  |
| corr_drop      |       0.184 |  0.374 |
| divergence     |       3.97  |  5.247 |
| idio_vol_spike |       1.463 |  2.689 |
| trend_tstat    |       1.843 |  2.34  |

|                                 | synthetic   | real   |
|:--------------------------------|:------------|:-------|
| breaks flagged (of 6)           | 6           | 0      |
| false BROKEN days before events | 1852        | 0      |
| BROKEN days on controls         | 2580        | 121    |
| mean return on breaks: naive    | -24.3%      | -24.3% |
| mean return on breaks: monitor  | -17.1%      | -24.3% |

## Known breaks (real-data thresholds)

`delay_days`: trading days from the headline date to the first BROKEN flag (negative = flagged before the headline; flags up to 250 days early count). `rel_move_*`: change in log(A/B) from the event to the flag / to one year later — how much of the divergence had already happened when the monitor reacted.

| pair     | story                                              | event      | first_broken   | delay_days   | rel_move_to_flag   | rel_move_1y   |   false_broken_days_before | fired   | naive_return   | naive_maxdd   | monitor_return   | monitor_maxdd   |
|:---------|:---------------------------------------------------|:-----------|:---------------|:-------------|:-------------------|:--------------|---------------------------:|:--------|:---------------|:--------------|:-----------------|:----------------|
| GE/HON   | GE: earnings collapse, dividend cut                | 2017-10-20 | not flagged    |              | —                  | -70.1%        |                          0 |         | +1.1%          | -53.5%        | +1.1%            | -53.5%          |
| GE/MMM   | GE: earnings collapse, dividend cut                | 2017-10-20 | not flagged    |              | —                  | -55.1%        |                          0 |         | -63.4%         | -80.1%        | -63.4%           | -80.1%          |
| WFC/JPM  | Wells Fargo: fake-accounts scandal, 2018 asset cap | 2016-09-08 | not flagged    |              | —                  | -27.5%        |                          0 |         | -38.4%         | -59.4%        | -38.4%           | -59.4%          |
| BA/LMT   | Boeing: 737 MAX grounding                          | 2019-03-13 | not flagged    |              | —                  | -91.7%        |                          0 |         | -31.1%         | -52.3%        | -31.1%           | -52.3%          |
| INTC/TXN | Intel: 7nm delay, lost process lead                | 2020-07-23 | not flagged    |              | —                  | -50.6%        |                          0 |         | -17.5%         | -55.3%        | -17.5%           | -55.3%          |
| KEY/PNC  | KeyCorp: 2023 regional bank crisis                 | 2023-03-10 | not flagged    |              | —                  | -12.8%        |                          0 |         | +3.7%          | -26.7%        | +3.7%            | -26.7%          |

## Healthy controls (should not be flagged)

| pair    | story   |   broken_days |   warning_days | naive_return   | naive_maxdd   | monitor_return   | monitor_maxdd   |
|:--------|:--------|--------------:|---------------:|:---------------|:--------------|:-----------------|:----------------|
| KO/PEP  | control |             0 |              0 | -22.3%         | -35.8%        | -22.3%           | -35.8%          |
| XOM/CVX | control |             0 |             18 | -48.9%         | -53.2%        | -48.9%           | -53.2%          |
| V/MA    | control |             0 |              9 | +2.3%          | -16.6%        | +2.3%            | -16.6%          |
| HD/LOW  | control |           121 |             14 | -29.5%         | -33.7%        | -28.9%           | -33.2%          |
| JPM/BAC | control |             0 |             16 | -5.4%          | -36.2%        | -5.4%            | -36.2%          |

## For comparison: synthetic thresholds

| pair     | event      | first_broken   |   delay_days | rel_move_to_flag   | rel_move_1y   |   false_broken_days_before | fired                                                                        | naive_return   | naive_maxdd   | monitor_return   | monitor_maxdd   |
|:---------|:-----------|:---------------|-------------:|:-------------------|:--------------|---------------------------:|:-----------------------------------------------------------------------------|:---------------|:--------------|:-----------------|:----------------|
| GE/HON   | 2017-10-20 | 2017-02-16     |         -171 | +39.2%             | -70.1%        |                        212 | df_tstat,cusum,corr_drop,divergence,idio_vol_spike,trend_tstat               | +1.1%          | -53.5%        | -37.6%           | -50.4%          |
| GE/MMM   | 2017-10-20 | 2017-03-06     |         -160 | +38.2%             | -55.1%        |                        232 | df_tstat,cusum,corr_drop,divergence,idio_vol_spike,trend_tstat               | -63.4%         | -80.1%        | -36.6%           | -52.7%          |
| WFC/JPM  | 2016-09-08 | 2016-10-05     |           19 | -11.7%             | -27.5%        |                          0 | df_tstat,cusum,z_persistence,corr_drop,divergence,idio_vol_spike,trend_tstat | -38.4%         | -59.4%        | -1.2%            | -16.0%          |
| BA/LMT   | 2019-03-13 | 2018-03-14     |         -250 | -21.4%             | -91.7%        |                        543 | df_tstat,cusum,corr_drop,divergence,idio_vol_spike,trend_tstat               | -31.1%         | -52.3%        | -38.4%           | -42.7%          |
| INTC/TXN | 2020-07-23 | 2019-07-26     |         -250 | -14.5%             | -50.6%        |                        517 | df_tstat,cusum,corr_drop,divergence,idio_vol_spike,trend_tstat               | -17.5%         | -55.3%        | +15.8%           | -47.8%          |
| KEY/PNC  | 2023-03-10 | 2023-05-15     |           45 | -31.5%             | -12.8%        |                        348 | df_tstat,cusum,z_persistence,corr_drop,divergence,idio_vol_spike,trend_tstat | +3.7%          | -26.7%        | -4.5%            | -22.1%          |

| pair    |   broken_days |   warning_days | naive_return   | naive_maxdd   | monitor_return   | monitor_maxdd   |
|:--------|--------------:|---------------:|:---------------|:--------------|:-----------------|:----------------|
| KO/PEP  |           334 |            288 | -22.3%         | -35.8%        | -24.2%           | -37.3%          |
| XOM/CVX |           948 |            143 | -48.9%         | -53.2%        | -52.6%           | -54.9%          |
| V/MA    |           196 |            136 | +2.3%          | -16.6%        | +4.2%            | -16.3%          |
| HD/LOW  |           738 |            133 | -29.5%         | -33.7%        | -34.5%           | -38.1%          |
| JPM/BAC |           364 |            152 | -5.4%          | -36.2%        | -5.6%            | -36.1%          |

Pairs strategy: z-window 60, entry 2, exit 0, 3-year hedge ratio, 10 bps costs; returns after a 400-day warm-up.
