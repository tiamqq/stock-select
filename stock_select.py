from tickflow import TickFlow
import pandas as pd
from tqdm import tqdm
import requests
import json
import os
import time


# ============================================================
# 从 GitHub Actions Secrets 获取敏感信息
# ============================================================

# TickFlow API Key
API_KEY = os.environ["TICKFLOW_API_KEY"]


# ============================================================
# TickFlow
# ============================================================

tf = TickFlow(
    api_key=API_KEY
)

tf_free = TickFlow.free()


# ============================================================
# 1. TickFlow 获取全量 A 股数据
# ============================================================

print("开始获取 A 股股票列表...")


url = "https://api.tickflow.org/v1/universes/batch"


payload = {
    "ids": ["CN_Equity_A"]
}


headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}


resp = requests.post(
    url,
    json=payload,
    headers=headers,
    timeout=60
)


resp.raise_for_status()


data = resp.json()


symbols = data["data"]["CN_Equity_A"]["symbols"]


df = pd.DataFrame({
    "symbol": symbols
})


# ============================================================
# 2. 过滤股票
#
# 1. 删除 .BJ（北交所）
# 2. 删除 688、689 开头
# ============================================================

df = df[
    ~df["symbol"].str.endswith(".BJ")
    & ~df["symbol"].str.startswith(("688", "689"))
].copy()


df.to_csv(
    "tickflow_filtered_symbol.csv",
    index=False,
    encoding="utf-8-sig"
)


print(
    f"过滤后剩余 {len(df)} 条股票"
)


# ============================================================
# 3. 读取股票列表
# ============================================================

df_symbol = pd.read_csv(
    "tickflow_filtered_symbol.csv"
)


symbol_list = df_symbol[
    "symbol"
].tolist()


print("股票列表读取完成")
print("开始获取数据...")


# ============================================================
# 4. 批量获取最近 66 根日线
# ============================================================

all_data = []

batch_size = 100


for i in range(
    0,
    len(symbol_list),
    batch_size
):

    batch_sym = symbol_list[
        i:i + batch_size
    ]


    print(
        f"正在处理 "
        f"{i + 1} ~ "
        f"{i + len(batch_sym)} / "
        f"{len(symbol_list)}"
    )


    try:

        dfs = tf_free.klines.batch(
            batch_sym,
            period="1d",
            count=66,
            as_dataframe=True,
            show_progress=True
        )


        for sym, df_k in dfs.items():

            if df_k is None:
                continue


            if len(df_k) == 0:
                continue


            df_k = df_k.copy()


            df_k["symbol"] = sym


            all_data.append(
                df_k
            )


    except Exception as e:

        print(
            f"这一批获取失败："
            f"{i + 1} ~ "
            f"{i + len(batch_sym)}"
        )

        print(
            f"错误：{e}"
        )


    # 避免接口限流
    time.sleep(1.3)


# ============================================================
# 5. 保存全部日线数据
# ============================================================

if not all_data:

    raise RuntimeError(
        "没有获取到任何股票日线数据，程序终止。"
    )


big_df = pd.concat(
    all_data,
    axis=0,
    ignore_index=True
)


big_df.to_csv(
    "tickflow_2_all_day.csv",
    index=False,
    encoding="utf-8-sig"
)


print(
    f"日线数据获取完成，"
    f"总行数：{len(big_df)}"
)


# ============================================================
# 6. 计算涨跌幅
# ============================================================

df = pd.read_csv(
    "tickflow_2_all_day.csv"
)


df["trade_date"] = pd.to_datetime(
    df["trade_date"]
)


df = df.sort_values(
    by=[
        "symbol",
        "trade_date"
    ]
).reset_index(
    drop=True
)


# 前一天收盘价
df["prev_close"] = (
    df.groupby("symbol")[
        "close"
    ].shift(1)
)


# 涨跌幅
df["pct_change"] = (
    df["close"]
    / df["prev_close"]
    - 1
) * 100


# 删除辅助列
df.drop(
    columns=["prev_close"],
    inplace=True
)


# 调整列顺序
cols = [
    "symbol",
    "name",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "pct_change",
    "volume",
    "amount"
]


df = df[cols]


df.to_csv(
    "tickflow_3_day.csv",
    index=False,
    encoding="utf-8-sig"
)


print("涨跌幅计算完成")


# ============================================================
# 7. 选股
# ============================================================

df = pd.read_csv(
    "tickflow_3_day.csv",
    encoding="utf-8-sig"
)


df["trade_date"] = pd.to_datetime(
    df["trade_date"]
)


df = df.sort_values(
    by=[
        "symbol",
        "trade_date"
    ],
    ascending=True
).reset_index(
    drop=True
)


# 删除没有涨跌幅的数据
df = df.dropna(
    subset=["pct_change"]
)


# ============================================================
# 排除 ST / 退市
# ============================================================

df = df[
    ~df["name"].str.contains(
        "ST|退",
        na=False
    )
].copy()


# ============================================================
# 选股条件
#
# 条件1：
# 近8日内有单日跌幅 <= -9.5%
#
# 条件2：
# 近3日没有跌幅 <= -5%
#
# 条件3：
# 最新收盘价 < 30 元
# ============================================================

hit_symbols = set()


for symbol, group in df.groupby(
    "symbol"
):

    g = group.sort_values(
        "trade_date"
    ).reset_index(
        drop=True
    )


    if len(g) < 8:
        continue


    last8 = g.tail(8)

    last3 = g.tail(3)

    latest_row = g.iloc[-1]

    prev_row = g.iloc[-2]


    # 条件1
    has_big_drop_8d = (
        last8["pct_change"] <= -9.5
    ).any()


    # 条件2
    no_big_drop_3d = (
        last3["pct_change"] > -5.0
    ).all()


    # 条件3
    price_ok = (
        latest_row["close"] < 30
    )


    if (
        has_big_drop_8d
        and no_big_drop_3d
        and price_ok
    ):

        hit_symbols.add(
            symbol
        )


# ============================================================
# 8. 生成最终 CSV
# ============================================================

output_file = "tickflow_4_final.csv"


if hit_symbols:

    out_df = df[
        df["symbol"].isin(
            hit_symbols
        )
    ].copy()


    cols = [
        "symbol",
        "name",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "pct_change",
        "volume",
        "amount"
    ]


    out_df = out_df[cols]


    out_df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )


    print(
        f"一共筛选 "
        f"{len(hit_symbols)} 只股票，"
        f"总输出 {len(out_df)} 行 K 线记录"
    )


else:

    # 没有符合条件股票
    # 仍然生成空 CSV

    out_df = pd.DataFrame(
        columns=[
            "symbol",
            "name",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "pct_change",
            "volume",
            "amount"
        ]
    )


    out_df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )


    print(
        "没有符合条件股票"
    )


# ============================================================
# 程序结束
# ============================================================

print("==============================")
print("原策略选股完成")
print("==============================")
print(f"数据文件：tickflow_3_day.csv")
print(f"选股结果：{output_file}")
print("邮件将在后续 send_email.py 中统一发送")