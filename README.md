# OA Leader Approver

## 当前流程

- 登录页固定为 `http://oa.hq.cmcc/portal-new/login`，登录由人工完成。
- 登录后接管待办页 `http://todo.hq.cmcc/backlog/cmit/web/index/todo?menu=DB&group=province&company=GD&role=ALL`。
- 只处理同时满足以下条件的公文：
  - `当前环节 = 相关部门会签`
  - `上一环节提交人 = 张喆`
- 点击标题进入详情页后，检查“审批意见”里 `张喆` 的意见是否严格等于 `请会签`。
- 如果不是 `请会签`，关闭当前公文并返回待办列表，不做处理。
- 如果是 `请会签`，点击顶部 `提交处理`。
- 在弹窗中执行：
  - `处理意见 = 其他`
  - 文本框填写 `请确认。`
  - `提交路径 = 部门内部征求意见`
  - 点击 `提交`
- 在选人弹窗中搜索 `卢志超`，选入右侧已选列表后点击 `确定`。
- 页面处理完成后等待系统自动返回待办列表，并自动刷新一次，避免重复处理刚办完的单。

## 使用方式

1. 关闭所有 Chrome 窗口。
2. 双击运行 `start-oa-approve-devtools.bat`。
3. 在打开的 Chrome 中手工登录 OA。
4. 登录后保持浏览器打开，程序会自动接管并持续处理。

## 关键文件

- 启动入口：`start-oa-approve-devtools.bat`
- 主脚本：`oa_auto_approve.py`
- 打包脚本：`build.ps1`
- 可执行文件：`dist\oa-auto-approve-leader.exe`
- 默认驱动：`drivers\chromedriver-unpacked-146\chromedriver-win64\chromedriver.exe`
- 日志目录：`logs\`
- 调试目录：`debug\`

## 常用命令

- 调试运行：`python oa_auto_approve.py`
- 附着到已打开 Chrome：`python oa_auto_approve.py --browser chrome --attach-debugger 127.0.0.1:9222`
- 限制处理数量：`python oa_auto_approve.py --limit 3`
- 重新打包：`powershell -ExecutionPolicy Bypass -File .\build.ps1`
