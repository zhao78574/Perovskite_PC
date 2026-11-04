# Perovskite Engine

用于钙钛矿器件 J–V 性能计算、PL / TRPL 曲线观察和实验数据整理的 Windows 桌面工具。

## 功能

- 批量读取 TXT 和 CHI BIN 数据
- 计算 Voc、Jsc、FF 和 PCE
- J–V、PL 和 TRPL 曲线预览
- TRPL ExpDec2 双指数拟合、积分平均寿命与拟合优度分析
- 多文件 EIS Nyquist 对比绘图、原始数据查看、首尾阻抗差计算与 Excel 导出
- 多文件 MPP Tracking 对比绘图、PCE 纵坐标换算、启动段与稳定段自适应平滑、短时掉点修复、数据查看与 Excel 导出
- 多样品 UPS 0 V/−5 V 手动配对、自动与手动线性边拟合、功函数/VBM/CBM 计算、独立禁带宽度和动态能级图；可对曲线做 Savitzky-Golay 平滑（默认 2 阶 / 7 点，对齐 Origin），平滑在归一化与拟合之前完成
- 多文件 SCLC 正/负偏压筛选、按器件面积换算电流密度、双对数绘图与 Excel/PNG 导出
- 多实验组 J–V 统计箱线图，组合显示彩色箱体、最小/最大须线和原始散点，并支持 Excel/PNG 导出
- J–V 性能结果 CSV 导出
- 多文件数据列提取与 Excel 导出
- 按 PCE 扫描参数解析 CHI LSV BIN，可批量或递归转换为两列 TXT，保留子目录、自动避免覆盖同名文件，并在失败时输出 TXT 清单
- 实验文件批量重命名
- 设置 → 外观：浅色 / 深色 / 跟随系统，5 种强调色，设置保存到本机

## 目录

```text
build_exe.py  桌面应用入口
trpl_fit.py   TRPL 双/三指数拟合（首次拟合时才加载 NumPy/SciPy）
ups_fit.py    UPS 功函数 / VBM 拟合（首次拟合时才加载 NumPy/SciPy）
src/          应用页面源码
src/vendor/   本地前端依赖（Plotly、SheetJS）
assets/       启动画面和静态资源
docs/         启动提速与发布说明
tests/        前后端测试
scripts/      一键发布、UPS 数据提取、启动图生成
packaging/    打包配置与构建产物
              perovskite-engine.spec / PerovskiteEngine.iss
              release-dist/（免安装目录）、installers/（安装包）
analysis/     一次性分析脚本（MPP、EIS、XRD、SCLC、箱线图）
analysis/mpp_output/  上述脚本的 MPP 图表与数据输出
data/         原始实验数据（data/ups_source/*.xls）
outputs/      分析结果（图表、Excel、CSV）；发布包统一放在 packaging/
archive/      历史备份（backups/）与旧构建快照（old-builds/，可安全删除）
```

> 注意：`trpl_fit.py`、`ups_fit.py` 以顶层模块名被 `build_exe.py` 和 `tests/` 导入，
> 移动它们需要同步修改导入路径。`packaging/release-dist`、`release-build`、`installers`
> 三个目录被 `scripts/build_release.ps1` 硬编码，不要改名。
> `outputs/` 不保存发布包副本；历史构建快照统一放在 `archive/old-builds/`。

更新配置使用环境变量：`PEROVSKITE_UPDATE_REPOSITORY=owner/repository` 和
`PEROVSKITE_UPDATE_PUBLISHER=证书 Subject 中的发布者文本`。任一配置缺失或签名不匹配时，更新会被拒绝。

## 开发运行

```powershell
python -m pip install -r requirements.txt
python build_exe.py
```

## 构建与发布

一条命令同时改版本号、构建 exe 并生成安装包（在项目根目录执行）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Version 1.3.0
```

输出：`packaging/release-dist/PerovskiteEngine`（免安装目录）和
`packaging/installers/PerovskiteEngine-Setup-<版本号>.exe`（发给用户的安装包）。

只构建 exe、不生成安装包时加 `-SkipInstaller`。

## 启动画面

`assets/splash.png` 由 `scripts/make_splash.py` 生成，尺寸 2816×1536。
设计取自 `assets/icon.ico`（`#17212B` 深底 + 白 P + `#2DD4BF` 青点），
图标会被拆成掩膜重建硬边，所以放大后依然锐利。改配色或文案直接编辑脚本顶部常量：

```powershell
python scripts\make_splash.py --variant light   # 输出到 assets/_preview/
```

可用候选稿：`light`（当前定稿）、`dark`、`glow`、`split`、`mark`。
定稿后把生成的图覆盖到 `assets/splash.png`，重新打包即可生效（旧像素树版现存于
`archive/assets-backup/`）。

## 启动性能

- Plotly 2.27.0 与 SheetJS 0.18.5 已放到 `src/vendor/`，本地加载，不再访问 CDN。
- NumPy / SciPy 改为第一次执行拟合时才导入，不开拟合功能时启动不会加载。
- 启动耗时可用环境变量 `PEROVSKITE_STARTUP_TRACE` 记录，详见 `docs/启动提速与发布说明.md`。
