# OA 自动审批打包说明

## 功能

- 打开已安装的 Microsoft Edge。
- 访问 OA 待办地址。
- 只处理“当前环节”为“部门落实”的单据。
- 进入详情后点击“一键提交”。
- 在弹窗中点击“提交”。
- 返回待办列表后继续循环，直到当前页没有符合条件的单据。
- 当前批次处理完成后自动退出程序。

## 首次使用

1. 运行程序前，先关闭所有 Edge 窗口。
2. 再运行 `oa-auto-approve.exe`。
3. 程序默认会用 Chrome 打开 `http://oa.hq.cmcc`。
4. 你手工登录 OA 后，回到命令窗口按回车。
5. 程序会在当前门户页点击待办区域的“更多”，再进入审批列表处理。

## 常用命令

- 调试运行: `python oa_auto_approve.py`
- 限制处理数量: `python oa_auto_approve.py --limit 3`
- 切换到 Edge: `python oa_auto_approve.py --browser edge`
- 指定浏览器配置名: `python oa_auto_approve.py --profile "Profile 1"`
- 指定用户数据目录: `python oa_auto_approve.py --user-data-dir "C:\Users\你的用户名\AppData\Local\Google\Chrome\User Data"`
- 如果你不想让程序自动关闭现有浏览器: `python oa_auto_approve.py --keep-browser`
- 打包: `powershell -ExecutionPolicy Bypass -File .\build.ps1`

## 当前打包说明

- 当前版本已内置 `ChromeDriver 138.0.7204.183 (win64)`，用于兼容 Chrome 138.0.7204 系列。
- 当前版本默认使用程序自己的独立浏览器配置目录，因此每次运行都按“手工登录一次，再继续处理”的流程执行。

## 输出文件

- 打包后可执行文件在 `dist\oa-auto-approve.exe`
- 日志文件在 `logs\oa_auto_approve.log`

## 注意

- 办公电脑需要安装 Microsoft Edge。
- 程序默认会先关闭现有 `msedge.exe` 进程，避免 Edge 用户配置被锁定。
- 如果你选择 `--keep-edge`，就需要你自己先确保所有 Edge 进程都已退出。
- 如果你的日常 Edge 不是默认配置而是 `Profile 1`、`Profile 2`，需要用 `--edge-profile` 指定。
- 如果 OA 页面结构和截图不完全一致，可能需要微调选择器。
