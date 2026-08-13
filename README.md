# A股多策略自动选股系统

基于 **Python + TickFlow + GitHub Actions**，自动获取 A 股日线数据，并运行 3 个独立选股策略，最后通过邮件统一发送 CSV 结果。

> **免责声明：本项目仅用于量化研究、策略测试和数据分析，不构成任何投资建议。策略结果不代表未来一定上涨，也不保证收益或胜率。**

## 一、三个策略

### 策略1：短线超跌反弹

文件：`stock_select.py`

输出：`tickflow_4_final.csv`

寻找近期明显超跌、但最近几天没有继续大幅下跌的股票。

当前主要条件：

- 最近 8 个交易日内存在单日跌幅 `<= -9.5%`
- 最近 3 个交易日跌幅均 `> -5%`
- 最新收盘价 `< 30 元`
- 排除 ST、退市、北交所、688/689 开头股票

定位：

```text
明显下跌 → 超跌 → 跌势减缓 → 观察短线反弹
```

---

### 策略2：趋势评分

文件：`trend_strategy.py`

输出：

- `trend_result.csv`
- `trend_top30.csv`

通过价格趋势、均线、动量、成交量等因素进行综合评分。

```text
价格趋势
+ 均线趋势
+ 动量
+ 成交量
+ 技术形态
        ↓
综合评分
        ↓
排名
        ↓
TOP30
```

定位：

> 寻找已经开始形成或延续趋势的股票，偏中短期趋势观察。

---

### 策略3：低位震荡蓄势

文件：`low_base_strategy.py`

输出：

- `low_base_result.csv`
- `low_base_top30.csv`

使用最近 **100 个交易日**，寻找：

> 处于相对低位、经过横盘整理、波动率和成交量收缩、底部趋稳，并逐渐接近箱体上沿的股票。

基本逻辑：

```text
下跌
 ↓
低位
 ↓
横盘整理
 ↓
波动收缩
 ↓
成交量收缩
 ↓
底部稳定
 ↓
接近箱体上沿
 ↓
等待可能突破
```

评分满分 100：

| 指标 | 分值 |
|---|---:|
| 100日低位程度 | 20 |
| 横盘程度 | 20 |
| 波动率收缩 | 15 |
| 成交量收缩 | 15 |
| MA60走平 | 10 |
| 底部稳定 | 10 |
| 接近箱体上沿 | 10 |
| **总分** | **100** |

---

## 二、三个策略的区别

| 策略 | 主要寻找 | 时间方向 | 核心特点 |
|---|---|---|---|
| 策略1 | 超跌反弹 | 短线 | 跌过、止跌 |
| 策略2 | 趋势 | 中短期 | 趋势形成/延续 |
| 策略3 | 低位蓄势 | 中期 | 横盘、缩量、等待突破 |

简单理解：

```text
策略1：最近跌得比较狠，现在可能跌不动了
策略2：已经开始往上走，趋势条件较好
策略3：还没明显启动，但可能正在低位蓄势
```

三个策略相互独立，目的不是得到完全相同的股票，而是从不同市场阶段寻找不同类型的机会。

---

## 三、项目文件

```text
.
├── stock_select.py
├── trend_strategy.py
├── low_base_strategy.py
├── send_email.py
├── requirements.txt
│
└── .github/
    └── workflows/
        └── stock.yml
```

| 文件 | 作用 |
|---|---|
| `stock_select.py` | 获取数据、计算涨跌幅、执行策略1 |
| `trend_strategy.py` | 执行策略2 |
| `low_base_strategy.py` | 执行策略3 |
| `send_email.py` | 统一发送邮件 |
| `requirements.txt` | Python 依赖 |
| `.github/workflows/stock.yml` | GitHub Actions 配置 |

---

## 四、数据流程

当前使用最近 **100 个交易日**：

```text
TickFlow
   ↓
100个交易日
   ↓
tickflow_2_all_day.csv
   ↓
计算涨跌幅
   ↓
tickflow_3_day.csv
   │
   ├── 策略1
   ├── 策略2
   └── 策略3
```

三个策略共用 `tickflow_3_day.csv`。

---

## 五、GitHub Actions

当前自动执行时间：

**周一至周五，北京时间 19:20**

GitHub Actions 使用 UTC，因此：

```yaml
- cron: "20 11 * * 1-5"
```

同时支持在 GitHub Actions 页面手动运行。

执行顺序：

```text
stock_select.py
      ↓
trend_strategy.py
      ↓
low_base_strategy.py
      ↓
send_email.py
```

---

## 六、GitHub Actions Secrets

为了避免 API Key、邮箱密码等敏感信息直接出现在代码中，需要在：

**GitHub → Repository → Settings → Secrets and variables → Actions**

创建以下 4 个 Repository secrets。

### 1. TICKFLOW_API_KEY

TickFlow API Key。

用于 `stock_select.py` 获取股票列表和日线数据。

```text
Name:
TICKFLOW_API_KEY

Secret:
你的 TickFlow API Key
```

---

### 2. SMTP_USER

QQ 发件邮箱地址。（其他邮箱可自查使用）

例如：

```text
Name:
SMTP_USER

Secret:
你的QQ邮箱地址
```

例如：

```text
000000000@qq.com
```

实际使用时填写自己的邮箱。

---

### 3. SMTP_PASSWORD

QQ 邮箱 SMTP 授权码。

**注意：这里不是 QQ 邮箱网页登录密码，而是 QQ 邮箱生成的 SMTP 授权码。**

```text
Name:
SMTP_PASSWORD

Secret:
你的QQ邮箱SMTP授权码
```

---

### 4. MAIL_TO

接收结果的邮箱地址。

例如：

```text
Name:
MAIL_TO

Secret:
11111111@outlook.com
```

实际使用时填写自己的收件邮箱。

---

## 七、Secrets 的使用方式

GitHub Actions：

```yaml
env:
  TICKFLOW_API_KEY: ${{ secrets.TICKFLOW_API_KEY }}
```

Python：

```python
API_KEY = os.environ["TICKFLOW_API_KEY"]
```

邮件：

```yaml
env:
  SMTP_USER: ${{ secrets.SMTP_USER }}
  SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
  MAIL_TO: ${{ secrets.MAIL_TO }}
```

Python：

```python
SENDER_EMAIL = os.environ["SMTP_USER"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
RECEIVER_EMAIL = os.environ["MAIL_TO"]
```

因此敏感信息不会直接写入代码。

---

## 八、邮件结果

执行完成后，`send_email.py` 统一发送：

```text
tickflow_4_final.csv
    ↓
策略1结果

trend_result.csv
    ↓
策略2完整结果

trend_top30.csv
    ↓
策略2重点观察30只

low_base_result.csv
    ↓
策略3完整结果

low_base_top30.csv
    ↓
策略3重点观察30只
```

---

## 九、人工筛选

本项目不是完全自动交易系统。

程序负责：

```text
全市场
 ↓
量化条件
 ↓
缩小范围
 ↓
评分排名
 ↓
TOP30
```

之后人工结合基本面、行业、公告、K线、成交量、市场环境等进行进一步筛选。

程序的目标是：

> **从大量股票中找出值得进一步研究的股票。**

而不是直接自动下单。

---

## 十、后续研究

项目目前处于策略测试阶段。

后续可以统计：

- 未来 1 日表现
- 未来 3 日表现
- 未来 5 日表现
- 未来 10 日表现
- 各策略实际胜率
- 平均收益
- 最大回撤
- TOP30 表现
- 不同评分区间表现
- 三个策略同时命中的股票
- 不同市场环境下的表现

通过历史数据不断验证和优化参数，而不是单纯追求理论上的经典策略。

---

## License

本项目仅用于个人量化研究、学习和策略测试。

使用者应自行承担基于本项目产生的投资决策风险。
