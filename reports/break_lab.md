# Break lab (100 synthetic pairs per scenario)

## Detection

| scenario    | type     | false_alarm_rate   | caught_within_6m   | median_delay_days   |
|:------------|:---------|:-------------------|:-------------------|:--------------------|
| stable      | no break | 8%                 | —                  | —                   |
| temp_shock  | no break | 31%                | —                  | —                   |
| drift_break | break    | 3%                 | 5%                 | 229                 |
| death       | break    | 3%                 | 82%                | 78                  |
| beta_shift  | break    | 3%                 | 96%                | 34                  |

A break is *caught* if flagged BROKEN within 126 trading days. False alarm = BROKEN before the break (or at any time for pairs that never break; for temporary shocks, flagging the shock itself counts as a false alarm — a missed opportunity).

## P&L of the same pairs strategy under three risk settings

Total return after the warm-up; worst_5pct = mean of the worst 5% of paths (CVaR).

| scenario    | variant   | mean   | median   | worst_5pct   |
|:------------|:----------|:-------|:---------|:-------------|
| stable      | naive     | +24.9% | +21.0%   | -0.8%        |
| stable      | z_stop_4  | +24.7% | +20.7%   | -0.8%        |
| stable      | monitor   | +24.6% | +20.4%   | -0.8%        |
| temp_shock  | naive     | +28.3% | +22.2%   | +1.2%        |
| temp_shock  | z_stop_4  | +24.6% | +19.7%   | -1.3%        |
| temp_shock  | monitor   | +23.7% | +19.6%   | -1.3%        |
| drift_break | naive     | +20.0% | +16.7%   | -4.4%        |
| drift_break | z_stop_4  | +19.8% | +16.6%   | -4.4%        |
| drift_break | monitor   | +19.0% | +15.7%   | -5.0%        |
| death       | naive     | +7.5%  | +0.1%    | -56.6%       |
| death       | z_stop_4  | +7.0%  | +0.1%    | -56.8%       |
| death       | monitor   | +11.6% | +11.2%   | -17.4%       |
| beta_shift  | naive     | +4.0%  | -0.1%    | -19.9%       |
| beta_shift  | z_stop_4  | +4.3%  | +0.9%    | -19.4%       |
| beta_shift  | monitor   | +8.4%  | +5.3%    | -10.9%       |

## Detectors present in the first BROKEN vote

| fired          |   times_in_first_break_vote |
|:---------------|----------------------------:|
| df_tstat       |                         258 |
| corr_drop      |                         258 |
| divergence     |                         258 |
| idio_vol_spike |                         258 |
| trend_tstat    |                         258 |
| cusum          |                         246 |
| z_persistence  |                         225 |
