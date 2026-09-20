# Windows 本地网页文件管理器

单用户本地文件管理 Web UI（Python + FastAPI）。默认仅绑定 `127.0.0.1`，通过浏览器浏览、搜索、上传/下载、复制/剪切/粘贴、重命名与文本编辑。

> **安全警告**：本项目**没有登录认证**。请**不要**将服务暴露到公网或局域网（不要改为 `0.0.0.0`）。仅在本机使用。所有操作限制在环境变量 `FILE_MANAGER_ROOT` 指定的目录内，并阻止路径穿越。

## 功能

- 目录浏览（面包屑导航）
- 按名称在根目录（或当前目录树）下搜索
- 复制 / 粘贴、剪切 / 移动
- 重命名、新建文件夹、删除
- 上传、下载
- 编辑并保存文本文件

## 目录结构

```
app/
  __init__.py
  main.py      # FastAPI 路由
  files.py     # 安全路径与文件操作
static/
  index.html
  app.js
  style.css
requirements.txt
README.md
.gitignore
```

## Windows 上运行

在项目根目录打开 **PowerShell** 或 **命令提示符**：

```bat
cd /d 路径\到\windows-web-file-manager

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt

REM 可选：设置可访问的根目录（默认为 %USERPROFILE%\Documents）
set FILE_MANAGER_ROOT=%USERPROFILE%\Documents

uvicorn app.main:app --host 127.0.0.1 --port 8765
```

浏览器打开：[http://127.0.0.1:8765/](http://127.0.0.1:8765/)

也可：

```bat
python -m app.main
```

### Linux / macOS（测试）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FILE_MANAGER_ROOT="$HOME/Documents"
uvicorn app.main:app --host 127.0.0.1 --port 8765
```

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `FILE_MANAGER_ROOT` | 允许访问的根目录 | Windows：`%USERPROFILE%\Documents`；否则 `~/Documents` 或 home |
| `FILE_MANAGER_HOST` | 监听地址 | `127.0.0.1` |
| `FILE_MANAGER_PORT` | 端口 | `8765` |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 前端页面 |
| GET | `/api/info` | 根目录信息 |
| GET | `/api/list?path=` | 列出目录（含面包屑） |
| GET | `/api/search?q=&path=` | 按名称搜索 |
| POST | `/api/rename` | `{path, new_name}` 重命名 |
| POST | `/api/copy` | `{source, dest_dir}` 复制 |
| POST | `/api/move` | `{source, dest_dir}` 剪切/移动 |
| POST | `/api/mkdir` | `{parent, name}` 新建文件夹 |
| POST | `/api/delete` | `{path}` 删除 |
| GET | `/api/download?path=` | 下载文件 |
| POST | `/api/upload?path=` | `multipart/form-data` 字段 `file` |
| GET | `/api/read?path=` | 读取文本 |
| POST | `/api/write` | `{path, content, encoding}` 保存文本 |

## 安全设计

- 所有路径经 `resolve()` 后校验必须位于 `FILE_MANAGER_ROOT` 之内，阻止 `..` 穿越。
- 默认仅监听本机回环地址。
- **无认证**：不要对外网开放端口。

## 许可证

MIT
