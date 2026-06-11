# AI-Small-Tool

Boss 直聘招聘助手桌面工具。它会识别 Boss 直聘客户端或网页端消息页里的未读消息、左侧候选人会话列表、当前候选人卡片、聊天内容，并生成招聘跟进建议。

## 功能概览

- 支持 Boss 直聘电脑客户端和网页端窗口识别。
- 支持导入截图识别，方便排查或离线分析。
- 本地优先识别：窗口文本、截图切区、OCR。
- 视觉模型兜底：OCR 不完整时可调用阿里云百炼视觉模型。
- 文本模型建议：基于识别结果生成未读摘要、当前聊天判断、优先级、快捷回复建议。
- 无 API Key 也能运行：会使用本地 OCR 和本地规则建议，只是不调用云端大模型。
- 支持最近 20 次扫描历史、历史回放、Markdown/JSON 导出。

## 直接使用 exe

如果你只是想直接运行当前打包版本，打开项目根目录里的：

```powershell
.\BossInsightAssistant_EXE\BossInsightAssistant.exe
```

注意：不要只移动单独的 `BossInsightAssistant.exe`，它需要同目录下的 `_internal` 文件夹。要复制给别人使用时，请复制整个 `BossInsightAssistant_EXE` 文件夹。

## 使用前准备

1. 打开 Boss 直聘电脑客户端，或在浏览器中打开 Boss 直聘网页端。
2. 停留在消息/候选人聊天页面。
3. Boss 窗口不要最小化。可以不在最前台，但最稳的方式是保持窗口可见、页面缩放 100%。
4. 启动本工具，点击 `立即扫描窗口`。

## 首次配置

启动后在左侧配置区填写：

- `Base URL`：阿里云百炼 OpenAI 兼容接口地址，默认推荐 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
- `API Key`：你的阿里云百炼 API Key。
- `文本模型`：推荐先用 `qwen-plus`。
- `视觉模型`：推荐先用 `qwen-vl-ocr-latest`，如果账号不可用，就填写百炼控制台中可用的 Qwen-VL/OCR 模型。
- `Boss窗口关键字`：默认 `BOSS`，找不到窗口时可改成浏览器标题里的关键词。
- `网页端优先走视觉识别`：网页端布局变化较多，建议开启。

填完后点击 `保存配置`。

## 常用操作

- `立即扫描窗口`：扫描当前打开的 Boss 客户端或网页端窗口。
- `导入截图识别`：选择一张 Boss 页面截图进行识别。
- `开始监控`：按配置的间隔持续扫描。
- `停止监控`：停止自动扫描。
- `导出本次结果`：导出 Markdown 或 JSON，方便复盘和排查。
- `复制AI建议`：复制右侧生成的回复建议。

## 识别逻辑说明

这个工具不是所有步骤都必须调用大模型：

- 先走本地识别：窗口文本、截图分区和 OCR 会优先提取左侧会话列表、未读数、当前候选人资料、当前聊天内容。
- 再走视觉模型兜底：当 OCR 结果明显不完整时，再调用视觉模型补充识别。
- 最后走文本模型建议：拿到候选人和聊天内容后，再生成摘要、优先级和回复建议。
- 如果没有 API Key 或模型调用失败，会保留本地识别结果并使用本地规则生成基础建议。

左侧“候选人列表”指 Boss 消息页左侧的所有会话列表。当前聊天区只能精确读取当前打开的那一个会话；左侧未打开的会话只能读取列表卡片上的最近消息和未读数。

## 源码运行

环境要求：

- Windows
- Python 3.12+

安装依赖：

```powershell
python -m pip install -e .[dev]
```

启动：

```powershell
python -m boss_tool.app
```

测试：

```powershell
python -m pytest tests -q
```

## 重新打包 exe

项目内已经提供 PyInstaller 打包脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1
```

打包完成后产物在：

```powershell
.\dist\BossInsightAssistant\BossInsightAssistant.exe
```

如果要放到项目根目录方便使用，可以复制整个文件夹：

```powershell
Copy-Item .\dist\BossInsightAssistant .\BossInsightAssistant_EXE -Recurse -Force
```

## 常见问题

- 找不到窗口：请确认 Boss 客户端或网页端已经打开，并且窗口没有最小化。
- 网页端识别不准：建议浏览器缩放 100%，打开 `网页端优先走视觉识别`。
- exe 启动缺 OCR 文件：请使用本仓库的 `scripts/build_exe.ps1` 重新打包，它会把 RapidOCR 模型文件一起打进去。
- 扫描卡顿：建议不要把监控间隔设太短，第一版推荐 5 秒以上。
- 不会自动发送消息：当前版本只做识别、总结、建议和导出，不会自动点击或自动发送。

## 目录结构

```text
src/boss_tool/
  app.py          # 程序入口
  gui.py          # 桌面界面
  config.py       # 配置持久化
  capture.py      # Boss 窗口查找与截图
  ocr.py          # OCR 封装
  parsers.py      # OCR 文本解析
  fallback.py     # 视觉兜底决策
  bailian.py      # 百炼文本/视觉调用
  exporter.py     # JSON/Markdown 导出
  pipeline.py     # 扫描主流程
  monitor.py      # 轮询监控
  models.py       # 数据模型
```

## 当前限制

- 第一版只支持 Windows。
- Boss 页面布局变化明显时，可能需要继续微调识别区域。
- 网页端受浏览器缩放、窗口宽度、页面布局影响更大。
- 云端模型名称需要按自己的阿里云百炼账号可用模型填写。
