# 集成文档（火山引擎 + 飞书多维表格）

## 1. 火山引擎大模型接口

代码位置：
- `/Users/wangying/Documents/workplace/HMPX/Structured Inventory System/app/services/multimodal_client.py`

当前实现：`VolcengineMultimodalClient`
- 请求地址：`{VOLCENGINE_BASE_URL}/chat/completions`
- 鉴权方式：`Authorization: Bearer {VOLCENGINE_API_KEY}`
- 请求体：OpenAI 兼容格式，`messages` 采用三段式：
  - `system`：角色与硬性规则
  - `user(text)`：本次任务指令 + JSON Schema
  - `user(image_url)`：图片（base64 data URI）

### 1.1 输入（发送给模型）
- 图片：上传文件转为 `data:{mime};base64,...`
- 提示词：固定规则提示，要求只返回 JSON 数组，字段为：
  - `品类`
  - `型号`
  - `颜色`
  - `尺码`
  - `数量`
  - `作废`
  - `性别`
- 关键规则：下角标数量、6/7/8/9/0 保持原样输出、X/斜杠作废、不可臆造记录

### 1.2 输出（模型返回）
期望为 JSON 数组，例如：
```json
[
  {
    "品类": "女休闲",
    "型号": "6872-66",
    "颜色": "米",
    "尺码": "9",
    "数量": 1,
    "作废": false,
    "性别": "女"
  }
]
```

系统会在规则层做二次校验与标准化（尺码展开、颜色标准化、范围校验）。

## 2. 飞书多维表格接口

代码位置：
- `/Users/wangying/Documents/workplace/HMPX/Structured Inventory System/app/services/feishu_client.py`

当前实现：
1. 获取 tenant_access_token
- `POST /open-apis/auth/v3/tenant_access_token/internal`

2. 批量写入记录
- `POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create`

### 2.1 写入字段映射
系统写入字段如下（你需要在多维表格中建立同名字段）：
- `品类` <- record.品类
- `型号` <- record.型号
- `颜色` <- record.颜色
- `尺码` <- record.尺码
- `数量` <- record.数量
- `任务ID` <- task_id

## 3. 环境变量
`.env` 示例：
```env
MULTIMODAL_PROVIDER=volcengine
VOLCENGINE_API_KEY=xxx
VOLCENGINE_MODEL=xxx
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
VOLCENGINE_TIMEOUT_SECONDS=60
PARSE_MAX_CONCURRENCY=5

FEISHU_APP_ID=xxx
FEISHU_APP_SECRET=xxx
FEISHU_BITABLE_APP_TOKEN=xxx
FEISHU_BITABLE_TABLE_ID=xxx
```

## 4. 处理流程（运行时）
1. 前端上传图片到 `/api/v1/inventory/parse-sync`
2. 后端调用火山引擎提取原始记录
3. 规则层校验并生成：
- `valid_records`
- `review_records`
- `error_summary`
4. `valid_records` 写入飞书
5. 返回任务级结果给前端展示

## 5. 常见问题
1. 返回 `Missing VOLCENGINE_API_KEY` / `Missing VOLCENGINE_MODEL`
- 检查 `.env` 与进程环境变量

2. 模型响应不是 JSON
- 优先检查模型是否支持图文输入与 JSON 指令
- 可在返回结果 `debug` 中补充原始返回内容（如需可扩展）

3. 飞书写入失败
- 检查 app_id/app_secret/app_token/table_id
- 检查字段名是否与表格一致
