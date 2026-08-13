import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime


# ============================================================
# 邮箱配置
# ============================================================

SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
MAIL_TO = os.environ.get("MAIL_TO")

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 587


# ============================================================
# 检查环境变量
# ============================================================

if not SMTP_USER:
    raise RuntimeError("缺少环境变量：SMTP_USER")

if not SMTP_PASSWORD:
    raise RuntimeError("缺少环境变量：SMTP_PASSWORD")

if not MAIL_TO:
    raise RuntimeError("缺少环境变量：MAIL_TO")


# ============================================================
# 邮件附件
# ============================================================

attachments = [
    "tickflow_4_final.csv",
    "trend_result.csv",
    "trend_top30.csv",
]


# ============================================================
# 创建邮件
# ============================================================

today = datetime.now().strftime("%Y-%m-%d")

msg = EmailMessage()

msg["Subject"] = f"A股自动选股结果 - {today}"

msg["From"] = SMTP_USER

msg["To"] = MAIL_TO


# ============================================================
# 邮件正文
# ============================================================

body = f"""
A股自动选股结果

日期：{today}

本次运行包含两个独立策略：

【策略1】
原有短线选股策略
附件：tickflow_4_final.csv

【策略2】
趋势评分策略
附件：trend_result.csv

【策略2重点观察】
趋势评分最高30只股票
附件：trend_top30.csv

请人工进一步筛选。

此邮件由 GitHub Actions 自动发送。
"""

msg.set_content(body)


# ============================================================
# 添加附件
# ============================================================

for file_name in attachments:

    file_path = Path(file_name)

    if not file_path.exists():

        print(
            f"警告：文件不存在，跳过附件：{file_name}"
        )

        continue

    with open(
        file_path,
        "rb"
    ) as f:

        file_data = f.read()

    msg.add_attachment(
        file_data,
        maintype="text",
        subtype="csv",
        filename=file_path.name
    )

    print(
        f"已添加附件：{file_name}"
    )


# ============================================================
# 发送邮件
# ============================================================

print("正在连接 QQ SMTP...")

with smtplib.SMTP(
    SMTP_SERVER,
    SMTP_PORT
) as server:

    server.starttls()

    server.login(
        SMTP_USER,
        SMTP_PASSWORD
    )

    server.send_message(msg)


print("========================================")
print("邮件发送成功")
print("========================================")