# Structured Inventory System

用于将鞋店手写库存图片解析为结构化 JSON，并写入飞书多维表格。

## 当前实现
- FastAPI 后端接口
- 可视化前端网页（批量上传、结果总览、明细表格）
- 规则校验（按你们对齐的业务规则）
- 标准任务结果输出（summary + valid_records + review_records + error_summary）
- 火山引擎大模型客户端（可切换 `mock/volcengine`）
- 飞书多维表格写入客户端

## 业务规则（V1）
- 下角标表示数量；无下角标默认 1
- 简写尺码 `6/7/8/9/0 -> 36/37/38/39/40`
- `X/斜杠` 标记尺码作废
- 男鞋尺码范围 `38-48`，女鞋尺码范围 `35-43`
- 一条型号+颜色+多尺码，拆成多条记录

## 启动
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动后访问：
- 前端页面: `http://127.0.0.1:8000/`
- API 文档: `http://127.0.0.1:8000/docs`

## 页面功能
- 批量上传图片
- `dry_run` 开关（仅解析不写飞书）
- 可选 `manual_records_json` 联调输入
- 展示任务状态、汇总卡片、有效记录、待复核记录、错误汇总

## 接口
### 1) 健康检查
`GET /api/v1/inventory/health`

### 2) 解析并写入
`POST /api/v1/inventory/parse-sync`

`multipart/form-data` 字段：
- `files`: 可多文件上传
- `dry_run`: `true/false`，`true` 时仅解析和校验，不写飞书
- `manual_records_json`: 可选，传入原始解析结果（JSON 字符串）用于联调

## 环境变量配置（.env）
```env
# 模型提供方: mock | volcengine
MULTIMODAL_PROVIDER=volcengine

# 火山引擎 Ark
VOLCENGINE_API_KEY=xxx
VOLCENGINE_MODEL=xxx
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
VOLCENGINE_TIMEOUT_SECONDS=60
PARSE_MAX_CONCURRENCY=5

# 飞书多维表格
FEISHU_APP_ID=xxx
FEISHU_APP_SECRET=xxx
FEISHU_BITABLE_APP_TOKEN=xxx
FEISHU_BITABLE_TABLE_ID=xxx
```

## 对接文档
模型和飞书对接字段、请求样例在：
- [integration.md](/Users/wangying/Documents/workplace/HMPX/Structured%20Inventory%20System/docs/integration.md)

## 说明
- 若 `MULTIMODAL_PROVIDER=volcengine` 但缺少 `VOLCENGINE_API_KEY` 或 `VOLCENGINE_MODEL`，接口会返回 500 配置错误。
- 若缺少飞书配置，解析仍会返回，但写入会失败并体现在 `debug.write_errors`。
