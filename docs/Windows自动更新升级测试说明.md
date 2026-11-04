# Windows 自动更新升级测试

## 发布前准备

在构建和测试安装包的 PowerShell 会话中设置：

```powershell
$env:PEROVSKITE_UPDATE_PUBLISHER = 'CN=实际代码签名证书发布者'
```

发布流程必须使用已签名的 Inno Setup 安装包。`scripts/build_release.ps1` 会拒绝未签名或发布者不匹配的安装包，并生成同名 `.sha256` 文件。

## 升级矩阵

使用现有安装包分别安装 `1.3.0`、`1.3.1`、`1.4.0` 和 `1.4.1`，再安装当前版本。每个版本都检查：

1. 原安装目录仍为 `%LOCALAPPDATA%\Programs\Perovskite Engine`，AppId 和卸载入口不变。
2. 用户设置、`%LOCALAPPDATA%\PerovskiteEngine\logs` 和实验数据不被删除或覆盖。
3. 新版本包含 `PerovskiteEngine.exe`、`Updater.exe`、`_internal\src\index.html` 和本地 vendor 文件。
4. 运行中的 TRPL/UPS 任务或未导出结果会阻止“立即更新”。
5. 关闭主程序后，Updater 能启动安装包；新程序启动后健康标记变为 `healthy`。
6. 断网、下载中断、SHA-256 错误、签名无效、发布者不匹配和安装失败均不会执行未经验证的安装包。

## 自动化命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_installer.ps1 -Version 1.4.2
```

真实 GitHub Release 测试还需要设置：

```powershell
$env:PEROVSKITE_UPDATE_REPOSITORY = 'owner/repository'
```
