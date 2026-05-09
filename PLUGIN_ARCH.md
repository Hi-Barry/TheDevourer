# TheDevourer 插件架构设计

> 版本：v1.0 | 将单体架构重构为插件化架构，模块独立打包、动态加载、独立升级。

---

## 1. 模块分层

```
┌──────────────────────────────────────────────┐
│                  UI 层                         │
│  pet_window  content_browser  question_dialog  │
│  settings_dialog  tray_icon                   │
├──────────────────────────────────────────────┤
│              功能层（Functional）               │
│  feed_handler  file_classifier                 │
│  content_classifier  storage_manager           │
│  chroma_client  file_watcher  kb_qa            │
├──────────────────────────────────────────────┤
│             核心层（Core，内置不可拆分）          │
│  config.py  logger.py  db.py  signal_bus.py    │
│  manifest_validator.py  module_loader.py       │
├──────────────────────────────────────────────┤
│              Python + PySide6 运行时           │
└──────────────────────────────────────────────┘
```

### 分层原则

- **核心层**：内置在 `core/`，随主程序一起发布，不可单独升级。所有模块依赖核心层但不依赖彼此。
- **功能层**：每个模块在 `modules/` 下独立目录，通过 `manifest.json` 声明身份和依赖。通过 SignalBus 通信，不直接 import 其他功能/UI 模块。
- **UI 层**：同样在 `modules/` 下，依赖核心层和部分功能层信号。不直接 import 功能模块的逻辑。

---

## 2. manifest.json 标准格式

### 2.1 模板

```json
{
  "name": "feed_handler",
  "version": "1.0.0",
  "description": "投喂处理模块 — 拖拽/粘贴/URL 识别",
  "author": "TheDevourer",
  "min_core_version": "1.0.0",

  "dependencies": {
    "core": ["config", "logger", "signal_bus"],
    "modules": []
  },

  "entry_points": {
    "classes": ["FeedItem", "FeedSourceType", "FeedQueueWorker"],
    "functions": ["extract_urls", "is_url", "fetch_url_title", "compute_md5", "parse_mime_data"],
    "signals": {
      "publish": ["feed/received", "feed/started", "feed/done"],
      "subscribe": []
    }
  },

  "hooks": {
    "on_load": "plugin_load",
    "on_unload": "plugin_unload",
    "on_upgrade": "plugin_upgrade"
  },

  "resources": []
}
```

### 2.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 模块名，全局唯一，仅含小写字母和下划线 |
| `version` | string | ✅ | 语义化版本号 `x.y.z` |
| `description` | string | — | 简短说明 |
| `author` | string | — | 作者 |
| `min_core_version` | string | ✅ | 兼容的最低核心版本 |
| `dependencies.core` | string[] | ✅ | 依赖的核心层模块列表 |
| `dependencies.modules` | string[] | — | 依赖的其他模块名（含版本约束 `name>=1.0`） |
| `entry_points.classes` | string[] | ✅ | 对外暴露的类名 |
| `entry_points.functions` | string[] | — | 对外暴露的函数名 |
| `entry_points.signals` | object | — | 发布/订阅的信号事件 |
| `hooks.on_load` | string | ✅ | 加载时执行的函数名 |
| `hooks.on_unload` | string | ✅ | 卸载时执行的函数名 |
| `hooks.on_upgrade` | string | — | 升级时执行的函数名 |
| `resources` | string[] | — | 模块附带资源文件路径（相对于模块目录） |

### 2.3 模块目录标准结构

```
modules/feed_handler/
├── manifest.json         # 模块身份声明
├── __init__.py           # 导出 entry_points + hooks
├── feed_handler.py       # 核心逻辑（可选拆分子文件）
└── resources/            # 模块资源（可选）
    └── icon.png
```

---

## 3. ModuleLoader 加载流程

### 3.1 加载流程图

```
ModuleLoader.scan(path="plugins/")
    │
    ├─ 遍历目录 + .zip 文件
    │
    ├─ 读取 manifest.json → manifest_validator 校验
    │     ├─ 合法 → 加入候选列表
    │     └─ 非法 → 跳过并记录日志
    │
    ├─ 拓扑排序（按 dependencies.modules 依赖关系）
    │
    ├─ 逐个加载：
    │     ├─ 1. 校验 min_core_version ≥ 主程序版本
    │     ├─ 2. sys.path.insert(0, module_path)
    │     ├─ 3. importlib.import_module(name)
    │     ├─ 4. 调用 hooks.on_load()
    │     ├─ 5. 注册 entry_points 到全局注册表
    │     └─ 6. 记录到 _loaded_modules 字典
    │
    ├─ 依赖缺失 → 加载失败，记录错误但不终止其他模块
    │
    └─ 加载完成 → 返回模块列表
```

### 3.2 ModuleLoader API

```python
class ModuleLoader:
    def scan(path: str) -> list[dict]           # 扫描可用模块
    def load_all(path: str) -> dict[str, Module] # 加载全部模块
    def load(name: str) -> Module                # 加载单个模块
    def unload(name: str) -> bool                # 卸载单个模块
    def get(name: str) -> Optional[Module]       # 获取已加载模块
    def list() -> list[str]                      # 已加载模块列表
    def get_entry_point(name: str, type: str, key: str) -> Optional[Callable]
```

### 3.3 Module 数据类

```python
@dataclass
class Module:
    name: str
    version: str
    path: str                     # 模块文件路径
    manifest: dict                # manifest.json 原始内容
    entry_points: dict[str, Any]  # 注册的入口点
    _module: types.ModuleType     # importlib 模块对象
    signals: dict[str, list]      # 信号订阅列表
```

---

## 4. SignalBus 通信协议

### 4.1 设计目标

模块之间**不直接 import**，所有跨模块通信通过 SignalBus 的 `publish/subscribe` 模式进行。

### 4.2 EventBus API

```python
class EventBus:
    def subscribe(event: str, callback: Callable, module: str = "") -> None
    def unsubscribe(event: str, callback: Callable) -> None
    def publish(event: str, **data) -> None
    def clear_module(module: str) -> None     # 卸载时清理该模块所有订阅
```

### 4.3 预定义事件

| 事件名 | 方向 | 负载 | 触发者 | 消费者 |
|--------|------|------|--------|--------|
| `feed/received` | publish | `{item: FeedItem}` | feed_handler | UI气泡+动画 |
| `feed/started` | publish | `{item: FeedItem}` | feed_queue | pet_window动画 |
| `feed/done` | publish | `{item, ok, msg}` | feed_queue | UI气泡+动画 |
| `file/classified` | publish | `{file_info, category, tags}` | file+content_classifier | storage_manager |
| `storage/stored` | publish | `{item_id, category}` | storage_manager | UI浏览器 |
| `storage/indexed` | publish | `{item_id, chunks}` | storage_manager | 状态栏 |
| `watcher/file_created` | publish | `{path}` | file_watcher | storage_manager |
| `watcher/file_deleted` | publish | `{path}` | file_watcher | storage_manager |
| `qa/asked` | publish | `{question}` | question_dialog | kb_qa |
| `qa/token` | publish | `{token}` | kb_qa | question_dialog |
| `qa/response` | publish | `{answer, sources}` | kb_qa | question_dialog |
| `ui/pet_double_clicked` | publish | `{}` | pet_window | content_browser |
| `ui/tray_show` | publish | `{}` | tray_icon | pet_window |
| `ui/question_requested` | publish | `{}` | pet_window | question_dialog |
| `ui/settings_requested` | publish | `{}` | pet_window | settings_dialog |

### 4.4 通信示例

```python
# feed_handler 在接收投喂后发布事件
EventBus.publish("feed/received", item=feed_item)

# pet_window UI 模块订阅事件（不需要 import feed_handler）
EventBus.subscribe("feed/received", lambda data: bubble.show_received(data["item"].display_name), module="pet_window")
```

---

## 5. 模块打包格式

### 5.1 打包产物

每个模块独立打包为 `.zip` 文件，命名格式：

```
{module_name}_v{version}.zip
```

### 5.2 ZIP 内部结构

```
feed_handler_v1.0.0.zip
├── manifest.json
├── __init__.py
├── feed_handler.py
└── resources/
    └── ...（可选）
```

### 5.3 校验

每个 `.zip` 附带同目录下的 `{module_name}_v{version}.sha256` 校验文件。

### 5.4 输出目录

打包产物统一存放于 `outputs/` 目录：

```
outputs/
├── feed_handler_v1.0.0.zip
├── feed_handler_v1.0.0.zip.sha256
├── file_classifier_v1.0.0.zip
├── storage_manager_v1.1.0.zip
└── ...
```

---

## 6. 升级机制

### 6.1 升级流程

```
用户获取新版本模块 .zip
    │
    ├─ 放入 plugins/updates/ 目录
    │
    ├─ 主程序启动时 ModuleLoader 扫描
    │
    ├─ 版本比对：
    │     ├─ 新版本 > 旧版本 → 执行升级
    │     └─ 新版本 <= 旧版本 → 跳过
    │
    ├─ 升级步骤：
    │     ├─ 1. unload_module(name)
    │     ├─ 2. 备份旧模块 .zip 到 plugins/backups/{name}_v{old}.zip
    │     ├─ 3. 替换为新的 .zip
    │     ├─ 4. 校验 manifest + checksum
    │     │     ├─ 通过 → load_module(name)
    │     │     └─ 失败 → 恢复旧模块备份
    │     └─ 5. 执行 hooks.on_upgrade()
    │
    └─ 升级完成
```

### 6.2 安全措施

- **版本白名单**：仅允许向后兼容的版本升级（主版本号一致）
- **回退机制**：升级失败自动回退到旧版本
- **日志审计**：所有升级操作记录到 `upgrade.log`

---

## 7. 目录结构总览

```
TheDevourer/
├── core/                    # 核心层（内置，不可拆分）
│   ├── config.py
│   ├── logger.py
│   ├── db.py
│   ├── signal_bus.py        # 新增：事件总线
│   ├── manifest_validator.py # 新增：manifest 校验器
│   └── module_loader.py     # 新增：模块加载器
├── modules/                 # 模块源码（开发期）
│   ├── feed_handler/
│   ├── file_classifier/
│   ├── content_classifier/
│   ├── storage_manager/
│   ├── chroma_client/
│   ├── file_watcher/
│   ├── kb_qa/
│   ├── ui_pet_window/
│   ├── ui_content_browser/
│   ├── ui_question_dialog/
│   ├── ui_settings_dialog/
│   └── ui_tray/
├── plugins/                 # 打包后的 .zip 模块（运行期加载）
│   └── updates/             # 新版本模块存放目录
│   └── backups/             # 升级时自动备份
├── tools/
│   └── pack_module.py       # 新增：模块打包工具
├── outputs/                 # 打包产物
│   └── *.zip + *.sha256
├── main.py                  # 轻量启动器
├── tests/                   # 全部测试
└── ...
```
