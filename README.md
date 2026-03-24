# OA 公文自动审批

## 当前可用流程

- 使用 Chrome 138 的 DevTools 附着模式运行。
- 登录页固定为 `http://oa.hq.cmcc/portal-new/login`，登录由人工完成。
- 登录后接管待办页 `http://todo.hq.cmcc/backlog/cmit/web/index/todo?menu=DB&group=province&company=GD&role=ALL`。
- 只处理“当前环节”精确等于 `部门落实` 或 `主办部门内部落实` 的公文。
- 点击标题后等待新标签页打开详情页。
- 在详情页顶部精确点击 `一键提交`。
- 在弹窗中找到 `下一步操作 = 结束办理` 的卡片，并点击该卡片里的 `提交`。
- 审批完成后等待系统关闭详情页并返回待办列表，然后自动刷新一次列表，再继续处理下一条。
- 如果暂时没有符合条件的公文，程序不会退出，会持续监控。

## 工作电脑使用

1. 关闭所有 Chrome 窗口。
2. 双击运行 `start-oa-approve-devtools.bat`。
3. 在打开的 Chrome 中手工登录 OA。
4. 登录后保持浏览器打开，程序会自动接管并开始审批。

## 关键文件

- 启动入口：`start-oa-approve-devtools.bat`
- 可执行文件：`dist\oa-auto-approve.exe`
- 主脚本：`oa_auto_approve.py`
- 日志目录：`logs\`
- 调试目录：`debug\`

## 常用命令

- 调试运行：`python oa_auto_approve.py`
- 附着到已打开的 Chrome：`python oa_auto_approve.py --browser chrome --attach-debugger 127.0.0.1:9222`
- 限制处理数量：`python oa_auto_approve.py --limit 3`
- 重新打包：`powershell -ExecutionPolicy Bypass -File .\build.ps1`

## 说明

- 当前版本按工作电脑的 Chrome 138 环境适配。
- 程序内置了 ChromeDriver 138。
- 失败时会把截图、HTML 和诊断文本写到 `debug\`，日志写到 `logs\oa_auto_approve.log`。
