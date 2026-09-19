# Carpool Fare Splitter

拼车行程费用分摊 API（Python + FastAPI）。行程被建模为若干**顺序路段**，每个路段有整数分费用；
乘客给出上车站点与下车站点，系统逐段找出在车乘客并均摊费用，输出逐人总额与逐路段明细。

## 启动（单条命令）

```bash
docker compose up --build
```

依赖安装与服务启动命令均已纳入镜像，无需任何额外初始化步骤。

## 默认访问地址

| 用途 | 地址 |
| --- | --- |
| API 服务 | http://localhost:8000 |
| 交互式文档 (Swagger UI) | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/healthz |

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `8000` | 宿主机映射端口，如 `PORT=9000 docker compose up --build` 后访问 http://localhost:9000 |

容器内服务固定监听 8000 端口；无其他必需配置。

## API

### POST /split

**请求体**

```json
{
  "segments": [100, 101, 100],
  "passengers": [
    {"id": "alice", "board": 0, "alight": 3},
    {"id": "bob",   "board": 0, "alight": 2},
    {"id": "carol", "board": 2, "alight": 3}
  ]
}
```

- `segments`：按顺序排列的各路段费用（整数，单位：分）。路段 `i` 连接站点 `i` 与站点 `i+1`，
  `n` 个路段对应站点 `0..n`。
- `passengers[].board` / `alight`：乘客上/下车站点索引（0 起），乘客在车区间为路段 `board .. alight-1`。

**响应 200**

```json
{
  "total_cents": 301,
  "passenger_totals": {"alice": 151, "bob": 100, "carol": 50},
  "segments": [
    {"index": 0, "cost_cents": 100, "passengers": ["alice", "bob"],   "shares": {"alice": 50, "bob": 50}},
    {"index": 1, "cost_cents": 101, "passengers": ["alice", "bob"],   "shares": {"alice": 51, "bob": 50}},
    {"index": 2, "cost_cents": 100, "passengers": ["alice", "carol"], "shares": {"alice": 50, "carol": 50}}
  ]
}
```

**响应 422**（请求非法，返回明确错误明细）

- 空载收费路段：某路段费用 > 0 但无乘客在车；
- 非法区间：`alight <= board`，或站点索引超出 `0..len(segments)` 范围；
- 乘客 ID 重复、路段费用为负、路段列表为空等。

示例：

```bash
curl -X POST http://localhost:8000/split \
  -H 'Content-Type: application/json' \
  -d '{"segments": [100, 50], "passengers": [{"id": "alice", "board": 0, "alight": 1}]}'
# => 422, "segment 1 costs 50 cent(s) but has no passengers on board"
```

## 分摊算法

1. 逐段处理：找出该路段所有在车乘客，费用均摊，每人先分得 `cost // n` 分。
2. 余数分配：无法整除时，余下 `cost % n` 个 1 分逐个补给**欠额最大**的在车乘客。
   欠额 = 该乘客累计理论份额（精确分数，用 `fractions.Fraction` 计算）− 已分金额。
3. 并列兜底：欠额相同时按乘客 ID 字典序分配，ID 仅用于打破平局。

由此保证：

- **总额守恒**：每段分摊之和等于该段费用，逐人总额之和等于全部路段费用之和；
- **换序不变**：乘客输入顺序任意排列，响应结果完全一致（理论份额为精确分数，平局由 ID 决定）。

## 本地开发

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest            # 运行测试
uvicorn app.main:app --reload   # 本地起服务，默认 http://127.0.0.1:8000
```

## 项目结构

```
app/
  main.py       # FastAPI 应用与 /split 端点
  models.py     # 请求/响应模型与 422 校验
  splitter.py   # 分摊核心算法（欠额法）
tests/
  test_split.py # 单元与接口测试
Dockerfile          # 依赖与启动命令均固化在镜像内
docker-compose.yml  # 单条命令启动
```
