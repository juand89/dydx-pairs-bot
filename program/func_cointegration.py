import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.regression.rolling import RollingOLS
from statsmodels.tsa.stattools import adfuller, coint
from constants import ZSCORE_THRESH

# Calculate Half Life
# https://www.pythonforfinance.net/2016/05/09/python-backtesting-mean-reversion-part-2/

# Turn off SettingWithCopyWarning
pd.set_option("mode.chained_assignment", None)


def calculate_half_life(spread):
    df_spread = pd.DataFrame(spread, columns=["spread"])
    spread_lag = df_spread.spread.shift(1)
    spread_lag.iloc[0] = spread_lag.iloc[1]
    spread_ret = df_spread.spread - spread_lag
    spread_ret.iloc[0] = spread_ret.iloc[1]
    spread_lag2 = sm.add_constant(spread_lag)
    model = sm.OLS(spread_ret, spread_lag2)
    res = model.fit()
    halflife = round(-np.log(2) / res.params[1], 0)

    return halflife


def test_for_stationarity(spread):
    is_stationary = False

    # Perform Dickey-Fuller test
    result = adfuller(spread)

    # Extract test statistics and critical values
    test_statistic = result[0]
    critical_values = result[4]

    # Compare test statistic to critical values
    if test_statistic < critical_values["1%"]:
        is_stationary = True

    return is_stationary


# Calculate ZScore
def calculate_zscore(spread, window):
    spread_series = pd.Series(spread)
    mean = spread_series.rolling(center=False, window=window).mean()
    std = spread_series.rolling(center=False, window=window).std()
    x = spread_series.rolling(center=False, window=1).mean()
    zscore = (x - mean) / std

    return zscore


# Calculate Cointegration
def calculate_cointegration(series_1, series_2):
    series_1 = np.array(series_1).astype(np.float)
    series_2 = np.array(series_2).astype(np.float)

    coint_flag = 0
    coint_res = coint(series_1, series_2)
    coint_t = coint_res[0]
    p_value = coint_res[1]
    critical_value = coint_res[2][1]
    t_check = coint_t < critical_value
    coint_flag = 1 if p_value < 0.05 and t_check else 0

    return coint_flag


# Calculate hedge ratio and spread
def calculate_hedge_ratio_and_spread(coint_pair_df, base_market, quote_market):
    df = coint_pair_df.copy()

    # Calculate hedge ratio
    df["hedge_ratio"] = (
        RollingOLS(
            df[base_market].astype(float),
            df[quote_market].astype(float),
            window=168,
        )
        .fit()
        .params.values
    )

    # Calculate spread
    df["spread"] = (
        df[base_market].astype(float)
        - df[quote_market].astype(float) * df["hedge_ratio"]
    )

    # Return only hedge_ration and spread columns
    return df[["hedge_ratio", "spread"]]


# Store Cointegration Results
def store_cointegration_results(df_market_prices):
    # Initialize
    markets = df_market_prices.columns.to_list()
    criteria_met_pairs = []

    # Find cointegrated pairs
    # Start with our base pair
    for index, base_market in enumerate(markets[:-1]):
        series_1 = df_market_prices[base_market].values.astype(float).tolist()

        # Get Quote Pair
        for quote_market in markets[index + 1 :]:
            series_2 = df_market_prices[quote_market].values.astype(float).tolist()

            # Check criteria
            coint_flag = calculate_cointegration(series_1, series_2)

            if coint_flag != 1:
                continue

            coint_pair_df = df_market_prices.loc[:, [base_market, quote_market]]

            # Calculate hedge ratio and spread
            hedge_ratio_and_spread_df = calculate_hedge_ratio_and_spread(
                coint_pair_df, base_market, quote_market
            )

            # Calculate hedge ratio
            coint_pair_df["hedge_ratio"] = hedge_ratio_and_spread_df["hedge_ratio"]
            coint_pair_df["spread"] = hedge_ratio_and_spread_df["spread"]

            # Stationary test
            coint_pair_df = coint_pair_df.dropna()
            stationary_flag = test_for_stationarity(coint_pair_df["spread"])

            if not stationary_flag:
                continue

            # Calculate halflife
            half_life = calculate_half_life(coint_pair_df["spread"])

            if half_life < 0 or half_life > 24:
                continue

            # Log pair
            criteria_met_pairs.append(
                {
                    "base_market": base_market,
                    "quote_market": quote_market,
                    "half_life": half_life,
                }
            )

    # Create and save DataFrame
    df_criteria_met = pd.DataFrame(criteria_met_pairs)
    df_criteria_met.sort_values(by="half_life", inplace=True)
    df_criteria_met.to_csv("cointegrated_pairs.csv")

    del df_criteria_met

    # Return result
    print("Cointegrated pairs successfully saved")
    return "saved"