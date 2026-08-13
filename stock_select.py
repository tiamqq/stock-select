from tickflow import TickFlow
import pandas as pd
from tqdm import tqdm
import requests
import json
import os
import time
import smtplib

from email.message import EmailMessage
from datetime import datetime


# ============================================================
# 从 GitHub Actions Secrets 获取敏感信息
# ============================================================

# TickFlow API Key
API_KEY = os.environ["TICKFLOW_API_KEY"]

# 邮箱信息
SENDER_EMAIL = os.environ["SMTP_USER"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
RECEIVER_EMAIL = os.environ["MAIL_TO"]


# ============================================================
# QQ 邮箱 SMTP
# ============================================================

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 587


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
# 9. 生成邮件正文
# ============================================================

today = datetime.now().strftime(
    "%Y-%m-%d"
)


if hit_symbols:

    # 获取最新交易日
    latest_date = df[
        "trade_date"
    ].max()


    # 获取当天选中的股票
    latest_selected = df[
        (df["symbol"].isin(hit_symbols))
        &
        (df["trade_date"] == latest_date)
    ].copy()


    latest_selected = latest_selected.sort_values(
        "symbol"
    )


    stock_lines = []


    for _, row in latest_selected.iterrows():

        symbol = row["symbol"]

        name = row["name"]

        close = row["close"]

        pct = row["pct_change"]


        stock_lines.append(
            f"{symbol}  "
            f"{name}  "
            f"收盘价：{close:.2f}  "
            f"涨跌幅：{pct:.2f}%"
        )


    stock_text = "\n".join(
        stock_lines
    )


    body = f"""\
A股今日选股完成。

日期：{today}

符合条件股票：{len(hit_symbols)} 只

今日选股结果：

{stock_text}

详细 K 线数据请查看附件：

{output_file}

--------------------------------

选股条件：

1. 近8日内有单日跌幅 <= -9.5%
2. 近3日没有跌幅 <= -5%
3. 最新收盘价 < 30 元
4. 排除 ST / 退市股票
5. 排除北交所
6. 排除 688、689 开头股票

此邮件由 GitHub Actions 自动发送。
"""


else:

    body = f"""\
A股今日选股完成。

日期：{today}

今天没有符合条件的股票。

附件：

{output_file}

--------------------------------

选股条件：

1. 近8日内有单日跌幅 <= -9.5%
2. 近3日没有跌幅 <= -5%
3. 最新收盘价 < 30 元
4. 排除 ST / 退市股票
5. 排除北交所
6. 排除 688、689 开头股票

此邮件由 GitHub Actions 自动发送。
"""


# ============================================================
# 10. 创建邮件
# ============================================================

msg = EmailMessage()


if hit_symbols:

    msg["Subject"] = (
        f"【A股选股】{today} "
        f"共 {len(hit_symbols)} 只"
    )

else:

    msg["Subject"] = (
        f"【A股选股】{today} "
        f"无符合条件股票"
    )


msg["From"] = SENDER_EMAIL

msg["To"] = RECEIVER_EMAIL


msg.set_content(
    body
)


# ============================================================
# 11. 添加所有 CSV 附件
# ============================================================

csv_files = [
    "tickflow_3_day.csv",
    "tickflow_4_final.csv"
]


for csv_file in csv_files:

    if not os.path.exists(csv_file):
        print(
            f"警告：文件不存在，跳过附件：{csv_file}"
        )
        continue


    with open(
        csv_file,
        "rb"
    ) as f:

        file_data = f.read()


    msg.add_attachment(
        file_data,
        maintype="text",
        subtype="csv",
        filename=csv_file
    )


    print(
        f"已添加附件：{csv_file}"
    )

# ============================================================
# 12. QQ SMTP 发送邮件
# ============================================================

print("正在发送邮件...")


with smtplib.SMTP(
    SMTP_SERVER,
    SMTP_PORT,
    timeout=60
) as server:

    # STARTTLS
    server.starttls()

    # 登录 QQ 邮箱
    server.login(
        SENDER_EMAIL,
        SMTP_PASSWORD
    )

    # 发送邮件
    server.send_message(
        msg
    )


print("==============================")
print("邮件发送成功")
print("==============================")
