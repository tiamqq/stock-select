import pandas as pd
import numpy as np
import os


# ============================================================
# 低位震荡蓄势策略
#
# 目标：
# 寻找处于相对低位、长期横盘、波动收缩、
# 成交量萎缩、底部稳定、等待可能突破的股票
#
# 输入：
#   tickflow_3_day.csv
#
# 输出：
#   low_base_result.csv
#   low_base_top30.csv
#
# 当前测试周期：
#   100 个交易日
#
# 说明：
#   本策略不判断短线涨跌
#   主要寻找中期低位蓄势股票
# ============================================================


INPUT_FILE = "tickflow_3_day.csv"

OUTPUT_ALL = "low_base_result.csv"

OUTPUT_TOP30 = "low_base_top30.csv"


# ============================================================
# 参数
# ============================================================

LOOKBACK = 100

# 只考虑当前股价 <= 30 元
MAX_PRICE = 30.0

# 最近20日不能出现过于明显的大涨
MAX_20D_RETURN = 20.0

# 最近20日不能持续大跌
MIN_20D_RETURN = -20.0


# ============================================================
# 读取数据
# ============================================================

print("========================================")
print("开始运行低位震荡蓄势策略")
print("========================================")


if not os.path.exists(INPUT_FILE):

    raise FileNotFoundError(
        f"找不到数据文件：{INPUT_FILE}"
    )


df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig"
)


# ============================================================
# 基础处理
# ============================================================

df["trade_date"] = pd.to_datetime(
    df["trade_date"]
)


df = df.sort_values(
    ["symbol", "trade_date"]
).reset_index(
    drop=True
)


# 删除 ST / 退市
df = df[
    ~df["name"].astype(str).str.contains(
        "ST|退",
        na=False
    )
].copy()


# 删除关键数据为空
df = df.dropna(
    subset=[
        "close",
        "high",
        "low",
        "volume"
    ]
)


# ============================================================
# 保存每只股票的结果
# ============================================================

results = []


# ============================================================
# 遍历股票
# ============================================================

for symbol, group in df.groupby("symbol"):

    g = group.sort_values(
        "trade_date"
    ).reset_index(
        drop=True
    )


    # --------------------------------------------------------
    # 必须至少有100个交易日
    # --------------------------------------------------------

    if len(g) < LOOKBACK:
        continue


    # 只使用最近100个交易日
    g = g.tail(
        LOOKBACK
    ).reset_index(
        drop=True
    )


    # --------------------------------------------------------
    # 最新数据
    # --------------------------------------------------------

    latest = g.iloc[-1]

    current_price = float(
        latest["close"]
    )


    # 当前价格必须 <= 30
    if current_price > MAX_PRICE:
        continue


    if current_price <= 0:
        continue


    # ========================================================
    # 1. 100日价格位置
    #
    # 0%  = 100日最低
    # 100% = 100日最高
    #
    # 越低越好
    # ========================================================

    high_100 = float(
        g["high"].max()
    )

    low_100 = float(
        g["low"].min()
    )


    price_position = (
        (current_price - low_100)
        /
        (high_100 - low_100)
        * 100
        if high_100 > low_100
        else 50
    )


    # ========================================================
    # 低位评分 20分
    # ========================================================

    if price_position <= 25:

        low_score = 20

    elif price_position <= 35:

        low_score = 17

    elif price_position <= 45:

        low_score = 13

    elif price_position <= 55:

        low_score = 8

    else:

        low_score = 0


    # ========================================================
    # 2. 最近20日涨跌幅
    #
    # 目的：
    # 排除已经明显启动的股票
    #
    # 同时排除还在猛烈下跌的股票
    # ========================================================

    close_20_ago = float(
        g.iloc[-21]["close"]
    )


    return_20d = (
        current_price
        /
        close_20_ago
        - 1
    ) * 100


    # 太强：可能已经启动
    if return_20d > MAX_20D_RETURN:
        continue


    # 太弱：可能仍然在下跌
    if return_20d < MIN_20D_RETURN:
        continue


    # ========================================================
    # 3. 横盘评分 20分
    #
    # 使用最近30日：
    #
    # (最高价 - 最低价) / 平均价格
    #
    # 越小代表震荡越集中
    # ========================================================

    last30 = g.tail(30)


    high_30 = float(
        last30["high"].max()
    )

    low_30 = float(
        last30["low"].min()
    )

    mean_30 = float(
        last30["close"].mean()
    )


    range_30_pct = (
        (high_30 - low_30)
        /
        mean_30
        * 100
        if mean_30 > 0
        else 999
    )


    if range_30_pct <= 15:

        sideways_score = 20

    elif range_30_pct <= 20:

        sideways_score = 17

    elif range_30_pct <= 25:

        sideways_score = 13

    elif range_30_pct <= 30:

        sideways_score = 8

    elif range_30_pct <= 40:

        sideways_score = 4

    else:

        sideways_score = 0


    # ========================================================
    # 4. 波动率收缩 15分
    #
    # 比较：
    #
    # 最近20日收益率标准差
    #
    # 与
    #
    # 最近60日收益率标准差
    #
    # 最近波动明显下降 -> 蓄势特征
    # ========================================================

    pct = g["close"].pct_change() * 100


    volatility_20 = float(
        pct.tail(20).std()
    )


    volatility_60 = float(
        pct.tail(60).std()
    )


    if volatility_60 > 0:

        volatility_ratio = (
            volatility_20
            /
            volatility_60
        )

    else:

        volatility_ratio = 1


    if volatility_ratio <= 0.60:

        volatility_score = 15

    elif volatility_ratio <= 0.70:

        volatility_score = 13

    elif volatility_ratio <= 0.80:

        volatility_score = 10

    elif volatility_ratio <= 0.90:

        volatility_score = 6

    else:

        volatility_score = 0


    # ========================================================
    # 5. 成交量收缩 15分
    #
    # 最近10日平均成交量
    #
    # VS
    #
    # 最近30日平均成交量
    #
    # 缩量横盘 -> 加分
    # ========================================================

    volume_10 = float(
        g["volume"].tail(10).mean()
    )


    volume_30 = float(
        g["volume"].tail(30).mean()
    )


    if volume_30 > 0:

        volume_ratio = (
            volume_10
            /
            volume_30
        )

    else:

        volume_ratio = 1


    if volume_ratio <= 0.60:

        volume_score = 15

    elif volume_ratio <= 0.70:

        volume_score = 13

    elif volume_ratio <= 0.80:

        volume_score = 10

    elif volume_ratio <= 0.90:

        volume_score = 6

    else:

        volume_score = 0


    # ========================================================
    # 6. MA60 走平评分 10分
    #
    # 比较：
    #
    # 当前MA60
    # VS
    # 20日前MA60
    #
    # 我们希望：
    #
    # MA60 不再明显下降
    # ========================================================

    g["ma60"] = (
        g["close"]
        .rolling(60)
        .mean()
    )


    ma60_current = g.iloc[-1]["ma60"]

    ma60_20ago = g.iloc[-21]["ma60"]


    if (
        pd.isna(ma60_current)
        or
        pd.isna(ma60_20ago)
        or
        ma60_20ago == 0
    ):

        ma60_change_pct = 999

    else:

        ma60_change_pct = (
            ma60_current
            /
            ma60_20ago
            - 1
        ) * 100


    # MA60轻微下降到走平，仍然给分
    if -1.0 <= ma60_change_pct <= 1.0:

        ma60_score = 10

    elif -2.0 <= ma60_change_pct <= 2.0:

        ma60_score = 7

    elif -4.0 <= ma60_change_pct <= 4.0:

        ma60_score = 4

    else:

        ma60_score = 0


    # ========================================================
    # 7. 底部稳定评分 10分
    #
    # 最近20日最低价
    # VS
    # 100日最低价
    #
    # 如果最近20日没有再次跌到100日最低点附近
    # 说明底部可能正在稳定
    # ========================================================

    low_20 = float(
        g["low"].tail(20).min()
    )


    if low_100 > 0:

        low_distance_pct = (
            low_20
            /
            low_100
            - 1
        ) * 100

    else:

        low_distance_pct = 0


    if low_distance_pct >= 8:

        bottom_score = 10

    elif low_distance_pct >= 5:

        bottom_score = 8

    elif low_distance_pct >= 3:

        bottom_score = 6

    elif low_distance_pct >= 1:

        bottom_score = 3

    else:

        bottom_score = 0


    # ========================================================
    # 8. 接近箱体上沿评分 10分
    #
    # 当前价格越接近30日箱体顶部越好
    #
    # 但不能已经突破太多
    # ========================================================

    if high_30 > low_30:

        box_position = (
            (current_price - low_30)
            /
            (high_30 - low_30)
            * 100
        )

    else:

        box_position = 50


    if 75 <= box_position <= 95:

        breakout_score = 10

    elif 65 <= box_position < 75:

        breakout_score = 8

    elif 55 <= box_position < 65:

        breakout_score = 5

    elif 45 <= box_position < 55:

        breakout_score = 3

    else:

        breakout_score = 0


    # ========================================================
    # 总评分
    #
    # 满分100
    # ========================================================

    total_score = (
        low_score
        +
        sideways_score
        +
        volatility_score
        +
        volume_score
        +
        ma60_score
        +
        bottom_score
        +
        breakout_score
    )


    # ========================================================
    # 保存结果
    # ========================================================

    results.append({

        "symbol": symbol,

        "name": latest["name"],

        "trade_date": latest["trade_date"],

        "close": current_price,

        "score": total_score,

        # ----------------------------
        # 各项评分
        # ----------------------------

        "low_score": low_score,

        "sideways_score": sideways_score,

        "volatility_score": volatility_score,

        "volume_score": volume_score,

        "ma60_score": ma60_score,

        "bottom_score": bottom_score,

        "breakout_score": breakout_score,

        # ----------------------------
        # 核心指标
        # ----------------------------

        "price_position_100d": round(
            price_position,
            2
        ),

        "range_30d_pct": round(
            range_30_pct,
            2
        ),

        "return_20d_pct": round(
            return_20d,
            2
        ),

        "volatility_ratio": round(
            volatility_ratio,
            3
        ),

        "volume_ratio": round(
            volume_ratio,
            3
        ),

        "ma60_change_pct": round(
            ma60_change_pct,
            2
        ),

        "low_distance_20d_pct": round(
            low_distance_pct,
            2
        ),

        "box_position_pct": round(
            box_position,
            2
        ),

        # ----------------------------
        # 100日高低点
        # ----------------------------

        "high_100d": round(
            high_100,
            2
        ),

        "low_100d": round(
            low_100,
            2
        ),

        "high_30d": round(
            high_30,
            2
        ),

        "low_30d": round(
            low_30,
            2
        ),

        # ----------------------------
        # 成交量
        # ----------------------------

        "volume_10d_avg": round(
            volume_10,
            0
        ),

        "volume_30d_avg": round(
            volume_30,
            0
        ),

        # ----------------------------
        # MA60
        # ----------------------------

        "ma60": round(
            float(ma60_current),
            2
        )

    })


# ============================================================
# 没有结果
# ============================================================

if not results:

    print("没有找到符合条件的股票。")

    empty_columns = [
        "symbol",
        "name",
        "trade_date",
        "close",
        "score",
        "low_score",
        "sideways_score",
        "volatility_score",
        "volume_score",
        "ma60_score",
        "bottom_score",
        "breakout_score",
        "price_position_100d",
        "range_30d_pct",
        "return_20d_pct",
        "volatility_ratio",
        "volume_ratio",
        "ma60_change_pct",
        "low_distance_20d_pct",
        "box_position_pct",
        "high_100d",
        "low_100d",
        "high_30d",
        "low_30d",
        "volume_10d_avg",
        "volume_30d_avg",
        "ma60"
    ]

    pd.DataFrame(
        columns=empty_columns
    ).to_csv(
        OUTPUT_ALL,
        index=False,
        encoding="utf-8-sig"
    )

    pd.DataFrame(
        columns=empty_columns
    ).to_csv(
        OUTPUT_TOP30,
        index=False,
        encoding="utf-8-sig"
    )

    print("程序结束。")

    raise SystemExit


# ============================================================
# 生成结果 DataFrame
# ============================================================

result_df = pd.DataFrame(
    results
)


# ============================================================
# 按评分从高到低排序
# ============================================================

result_df = result_df.sort_values(
    [
        "score",
        "price_position_100d",
        "range_30d_pct"
    ],
    ascending=[
        False,
        True,
        True
    ]
).reset_index(
    drop=True
)


# ============================================================
# 添加排名
# ============================================================

result_df.insert(
    0,
    "rank",
    range(
        1,
        len(result_df) + 1
    )
)


# ============================================================
# 保存全部结果
# ============================================================

result_df.to_csv(
    OUTPUT_ALL,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# 保存评分最高30只
# ============================================================

top30_df = result_df.head(
    30
).copy()


top30_df.to_csv(
    OUTPUT_TOP30,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# 输出结果
# ============================================================

print()
print("========================================")
print("低位震荡蓄势策略完成")
print("========================================")

print(
    f"有效股票数量：{len(result_df)}"
)

print(
    f"TOP30 数量：{len(top30_df)}"
)

print(
    f"全部结果：{OUTPUT_ALL}"
)

print(
    f"TOP30结果：{OUTPUT_TOP30}"
)

print()
print("评分最高的股票：")
print()

print(
    top30_df[
        [
            "rank",
            "symbol",
            "name",
            "close",
            "score",
            "price_position_100d",
            "range_30d_pct",
            "return_20d_pct",
            "volatility_ratio",
            "volume_ratio",
            "ma60_change_pct",
            "box_position_pct"
        ]
    ].head(10).to_string(
        index=False
    )
)

print()
print("========================================")
print("程序运行结束")
print("========================================")