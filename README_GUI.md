# BOM 转换与 KiCad 导出 GUI 工具

这是一个基于 `bom_transform.py` 和 `kicad_export.py` 脚本的图形界面工具，用于 BOM 格式转换与校验以及 KiCad 项目文件导出。

## ✨ 新功能

- **实时输出显示**：KiCad导出选项卡现在包含专用的只读输出区域，实时显示导出过程的详细信息，避免GUI卡住
- **后台线程执行**：KiCad导出在后台线程中运行，GUI保持响应，用户可以查看实时进度
- **智能按钮状态**：导出过程中按钮显示"正在导出..."并被禁用，防止重复操作

## 功能

- **BOM转换**：选择输入 CSV 文件，进行格式转换和校验
- **KiCad导出**：选择 KiCad 项目文件，导出各种文件并运行质量检查
- **自动检测KiCad CLI**：软件启动时自动检测KiCad CLI路径，无需手动配置

## 依赖

确保安装以下 Python 库：

- pandas
- openpyxl
- chardet
- PyYAML
- tkinter (通常随 Python 安装)

可以使用以下命令安装：

```bash
pip install pandas openpyxl chardet PyYAML
```

## 使用方法

1. 运行 GUI 工具：

```bash
python gui_bom_transform.py
```

2. 选择功能选项卡：

### BOM 转换选项卡

- 点击 "浏览..." 选择输入 CSV 文件
- 输出目录会自动设置为输入文件所在目录的 "outputs" 子目录（如果不存在会自动创建）
- 可选输入项目名称
- 可选选择映射配置文件（mapping.yml）
- 勾选静默模式如果不需要详细错误输出
- 点击 "运行 BOM 转换"

### KiCad 导出选项卡

- 点击 "浏览..." 选择 KiCad 项目文件（.kicad_pro）
- 点击 "浏览..." 选择输出目录（默认为 "outputs"）
- KiCad CLI 路径支持：
  - **启动时自动检测**：软件启动时自动检测并填充KiCad CLI路径
  - 手动浏览选择（如果自动检测失败）
  - 点击 "自动检测" 按钮重新查找常见安装路径
  - 支持的路径包括：
    - C:\Program Files\KiCad\9.0\bin\kicad-cli.exe
    - %LOCALAPPDATA%\Programs\KiCad\9.0\bin\kicad-cli.exe
    - D:\Users\用户名\AppData\Local\Programs\KiCad\9.0\bin\kicad-cli.exe（针对用户特定安装）
- 选择运行模式：
  - 跳过 ERC/DRC 检查
  - 跳过文件导出
  - 导出模式（检查但只看文件导出结果）
- **实时输出显示**：导出过程中会在专用输出区域显示详细的执行信息，包括：
  - 检测到的KiCad CLI版本
  - ERC/DRC检查进度和结果
  - 文件导出状态
  - 错误信息和警告
  - 最终的成功/失败状态
- 点击 "运行 KiCad 导出"

## 输出文件

### BOM 转换输出

- XLSX 格式的 BOM 文件：`{项目名}_BOM_{日期}.xlsx`
- TXT 格式的质量报告：`{项目名}_BOM_Report_{日期}.txt`

### KiCad 导出输出

- 原理图 PDF：`{项目名}-Schematic.pdf`
- BOM 清单 CSV：`{项目名}-BOM.csv`
- Gerber 文件包：`{项目名}-Gerber.zip`
- PCB 图像：`{项目名}-PCB-Front.svg`, `{项目名}-PCB-Back.svg`
- 3D STEP 模型：`{项目名}-3D.step`
- 质量检查报告：`erc_report.json`, `drc_report.json`
- 构建摘要：`build_summary.md`

## 注意事项

- 输入文件必须是有效的格式
- 确保输出目录存在且可写
- KiCad 导出需要安装 KiCad 并确保 CLI 可用
- KiCad CLI 路径自动检测顺序：
  1. 系统 PATH 中的 `kicad-cli` 或 `kicad.kicad-cli`
  2. Windows 常见安装路径：
     - `C:\Program Files\KiCad\9.0\bin\kicad-cli.exe`
     - `%LOCALAPPDATA%\Programs\KiCad\9.0\bin\kicad-cli.exe`
     - 各驱动器用户目录下的 `AppData\Local\Programs\KiCad\9.0\bin\kicad-cli.exe`
- 如果缺少依赖库，工具会尝试运行但可能失败
