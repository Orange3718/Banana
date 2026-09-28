# Upbit strategy validation and live update

Date: 2026-09-27 KST

## Decision

The Upbit worker remains live, but new entries now use only the two strategies
with positive realized evidence:

- `trend_confirmation`
- `trend_pullback`

New `volatility_breakout` and `mean_reversion` entries are disabled. Existing
positions keep the previously configured 2.5% stop, take-profit, trailing and
time-exit rules; this deployment did not liquidate or rewrite them.

## Evidence and method

The validation reconstructed the local execution ledger from
`upbit-auto-trader/trade_history.jsonl`. It used the executed trades and
`paid_fee` in each Upbit final order response, matched buys and sells by market
with FIFO lots, and evaluated the period from 2026-09-13 through 2026-09-27.

- Buy events: 222
- Sell events: 153
- Executed turnover: 11,286,356 KRW
- Paid fees: 5,643 KRW
- Matched exit cycles: 151
- Matched realized net: +6,377 KRW
- Exit-cycle win rate: 58.3%
- Profit factor: 1.154

Strategy-level matched lots:

| Entry strategy | Matched lots | Net PnL | Net return on matched cost | Winning lots |
| --- | ---: | ---: | ---: | ---: |
| Trend confirmation | 76 | +9,792 KRW | +0.436% | 55 |
| Trend pullback | 40 | +6,419 KRW | +0.713% | 30 |
| Volatility breakout | 123 | -10,536 KRW | -0.476% | 48 |
| Mean reversion | 5 | +702 KRW | +1.403% | 1 |

The retained trend-confirmation and pullback lots together produced +16,211
KRW, a 73.3% winning-lot rate and a 1.695 profit factor. This is a historical
subset comparison rather than a full counterfactual portfolio backtest:
removing a strategy changes later cash availability and candidate selection.
Mean reversion was disabled because four of five matched lots lost money and
one large winner dominated the net result.

The largest avoidable drag was the breakout rule. Its 60-minute time exits lost
6,293 KRW and its stop exits lost 11,576 KRW. Two high-turnover days placed 88
and 50 buys. Fees alone consumed about 1.25% of the approximately 450,000 KRW
account size during the observed period.

Upbit's order response exposes executed volume, paid fee and individual trade
funds, which are the fields used by this audit. Reference:
https://global-docs.upbit.com/reference/new-order

## Deployed settings

| Control | Before | Deployed |
| --- | ---: | ---: |
| Enabled entry strategies | 4 | trend confirmation, pullback |
| Maximum active positions | 287 | 5 |
| Maximum buys per KST day | 287 | 12 |
| Maximum value per coin | 500,000 KRW | 120,000 KRW |
| Cash reserve | 0 | max(30,000 KRW, 10% of equity) |
| Loss/profit re-entry cooldown | 0 / 0 min | 240 / 60 min |
| Consecutive-loss pause | effectively disabled | 3 losses, 60 min |
| Open-position risk budget | none | 1.5% of equity |

The 40,000 KRW base order, 2.5% stop, staged take profit and trailing exit are
unchanged. Estimated entry risk now includes the stop, 0.05% fee on both sides
and 0.05% slippage on both sides. A 40,000 KRW full-size order therefore carries
an estimated 1,080 KRW loss. The worker blocks an entry if that projected loss
would breach either the daily loss budget or the total open-risk budget. Market
buy sizing also reserves the estimated fee so a zero-reserve balance cannot
cause `insufficient_funds_bid`.

## Deployment verification

- Full `tests_next` suite: 43 passed.
- Python compilation and `git diff --check`: passed.
- LaunchAgent `com.orange3718.upbit-auto-trader.upbit-worker`: running after
  restart.
- Worker log confirmed `trend=True`, `pullback=True`, `breakout=False`,
  `mean_reversion=False`, five positions, twelve daily buys and 1.5% open risk.
- At verification, the account had five priced positions and 144,844 KRW cash.
  No position was sold by the deployment restart.

The sample covers about two weeks and several strategies traded the same market,
so the next review should use newly closed trades created only under this
configuration. The primary checks are net PnL after fees, profit factor, stop
frequency and whether the open-risk gate prevents another high-turnover day.
