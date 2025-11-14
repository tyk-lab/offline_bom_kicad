#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KiCad 自动化导出脚本 (KiCad 9.0+)

功能：
- ERC/DRC 质量检查（电气规则、设计规则）
- 导出原理图 PDF、BOM 清单 (CSV)
- 导出 Gerber 文件包 (ZIP，含钻孔文件)
- 导出 PCB 图像 (SVG)、3D STEP 模型
- 生成构建摘要报告 (Markdown)

基础用法：
    python kicad_export.py <项目.kicad_pro> [-o 输出目录]

参数：
    project               KiCad 项目文件 (.kicad_pro)
    -o, --output          输出目录 (默认: outputs)
    --kicad-cli           指定 KiCad CLI 路径 (自动检测失败时使用)
    --gerber-layers       自定义 Gerber 层 (逗号分隔，或 "all" 导出全部)
    --skip-checks         跳过 ERC/DRC 检查
    --skip-exports        跳过文件导出 (仅运行检查)
    --export-mode         导出模式 (运行检查但不影响退出码)

运行模式：
    1. 完整模式 (默认)
       → 运行检查 + 导出文件，任何失败都返回错误退出码
       → 适用于：本地开发、完整验证

    2. 检查模式 (--skip-exports)
       → 仅运行 ERC/DRC，有错误即失败
       → 适用于：CI/CD 检查阶段、PR 验证

    3. 纯导出模式 (--skip-checks)
       → 跳过检查，仅导出文件
       → 适用于：快速生成文件

    4. 导出模式 (--export-mode，推荐用于 CI/CD)
       → 运行检查生成报告，但只根据文件导出判断成败
       → 适用于：CI/CD 导出阶段

输出文件：
    outputs/
    ├── erc_report.json            # ERC 检查报告
    ├── drc_report.json            # DRC 检查报告
    ├── build_summary.md           # 构建摘要
    ├── {项目名}-Schematic.pdf     # 原理图
    ├── {项目名}-BOM.csv           # BOM 清单
    ├── {项目名}-Gerber.zip        # Gerber 文件包
    ├── {项目名}-PCB-Front.svg     # PCB 正面图
    ├── {项目名}-PCB-Back.svg      # PCB 背面图
    └── {项目名}-3D.step           # 3D 模型

退出码：
    0 - 成功
    1 - 检查失败或导出失败
    2 - 脚本异常 (文件不存在、CLI 未找到等)

使用示例：

  本地开发：
    python kicad_export.py project.kicad_pro
    python kicad_export.py project.kicad_pro -o build

  CI/CD 检查阶段：
    python kicad_export.py project.kicad_pro --skip-exports

  CI/CD 导出阶段：
    python kicad_export.py project.kicad_pro --export-mode

  自定义 Gerber 层：
    python kicad_export.py project.kicad_pro --gerber-layers "F.Cu,B.Cu,Edge.Cuts"
    python kicad_export.py project.kicad_pro --gerber-layers "all"

  指定 KiCad CLI (自动检测失败时)：
    # Linux/macOS
    python kicad_export.py project.kicad_pro --kicad-cli /usr/bin/kicad-cli

    # Windows
    python kicad_export.py project.kicad_pro --kicad-cli "C:\\Program Files\\KiCad\\9.0\\bin\\kicad-cli.exe"

配置说明：

  Gerber 层配置 (优先级：参数 > 环境变量 > 默认值)：
    默认层：F.Cu, B.Cu, F.Paste, B.Paste, F.Silkscreen, B.Silkscreen,
            F.Mask, B.Mask, Edge.Cuts

    通过参数：--gerber-layers "F.Cu,B.Cu,Edge.Cuts"
    通过环境变量：export GERBER_LAYERS="F.Cu,B.Cu,Edge.Cuts"
    导出全部层：--gerber-layers "all"

  3D STEP 导出：
    - 使用 --subst-models 替换为 STEP/IGS 模型
    - 需设置 KICAD9_3DMODEL_DIR 环境变量指向 3D 模型库

  BOM 导出字段：
    描述, Reference, Qty, Value, Category, Part-DB IPN, lcsc#, manf, manf#

注意事项：
  - Windows 环境自动处理 UTF-8 编码
  - 钻孔文件自动生成为 Excellon 格式并打包到 Gerber.zip
  - 自动过滤 wxWidgets 调试信息
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import Tuple, Optional, List


DEFAULT_GERBER_LAYERS: List[str] = [
    "F.Cu",
    "B.Cu",
    "F.Paste",
    "B.Paste",
    "F.Silkscreen",
    "B.Silkscreen",
    "F.Mask",
    "B.Mask",
    "Edge.Cuts",
]


class KiCadExporter:
    def __init__(
        self,
        project_path: str,
        output_dir: str = "outputs",
        kicad_cli_path: Optional[str] = None,
        gerber_layers: Optional[str] = None,
    ):
        self.project_path = Path(project_path)
        self.project_name = self.project_path.stem
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 检测KiCad CLI命令
        self.kicad_cli = self._detect_kicad_cli(kicad_cli_path)

        # Gerber层配置
        self.gerber_layers = self._resolve_gerber_layers(gerber_layers)

        # 文件路径
        self.sch_file = self.project_path.with_suffix(".kicad_sch")
        self.pcb_file = self.project_path.with_suffix(".kicad_pcb")

        # 结果统计
        self.results = {
            "erc": {"status": "skipped", "violations": 0},
            "drc": {"status": "skipped", "violations": 0},
            "exports": {},
        }

    def _resolve_gerber_layers(
        self, layers_option: Optional[str]
    ) -> Optional[List[str]]:
        """解析Gerber层配置

        返回：
            None 表示导出全部层；否则返回被限定的层列表
        """

        raw_value = layers_option or os.getenv("GERBER_LAYERS")

        if raw_value:
            raw_value = raw_value.strip()
            if raw_value.lower() in {"all", "*", "any"}:
                print("ℹ Gerber层设置: 导出全部层")
                return None

            layers = [layer.strip() for layer in raw_value.split(",") if layer.strip()]
            if layers:
                print(f"ℹ Gerber层设置: {', '.join(layers)}")
                return layers

        print("ℹ Gerber层设置: 使用默认层 (" + ", ".join(DEFAULT_GERBER_LAYERS) + ")")
        return DEFAULT_GERBER_LAYERS.copy()

    def _detect_kicad_cli(self, custom_path: Optional[str] = None) -> str:
        """检测可用的KiCad CLI命令"""
        # 如果指定了自定义路径，优先使用
        if custom_path:
            if Path(custom_path).exists():
                try:
                    result = subprocess.run(
                        [custom_path, "version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        print(f"✓ 使用指定的KiCad CLI: {custom_path}")
                        print(f"  版本: {result.stdout.strip()}")
                        return custom_path
                except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                    raise RuntimeError(
                        f"错误: 指定的KiCad CLI路径无效: {custom_path} - {e}"
                    )
            else:
                raise RuntimeError(f"错误: 指定的KiCad CLI路径不存在: {custom_path}")

        # 尝试系统路径中的命令
        commands = ["kicad-cli", "kicad.kicad-cli"]

        for cmd in commands:
            try:
                result = subprocess.run(
                    [cmd, "version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    print(f"✓ 检测到系统KiCad CLI: {cmd}")
                    print(f"  版本: {result.stdout.strip()}")
                    return cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        raise RuntimeError(
            "错误: 未找到KiCad CLI命令\n"
            "  请安装KiCad或使用 --kicad-cli 参数指定路径\n"
            "  尝试过: kicad-cli, kicad.kicad-cli"
        )

    def _run_command(self, args: list, description: str) -> Tuple[bool, str]:
        """运行命令并返回结果"""
        print(f"\n{'='*60}")
        print(f"执行: {description}")
        print(f"命令: {' '.join(args)}")
        print("=" * 60)

        try:
            # 在Windows上明确指定UTF-8编码，避免GBK解码错误
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",  # 遇到无法解码的字符时用替换字符
            )

            # 过滤掉 wxWidgets 调试信息
            filtered_stderr = self._filter_wx_debug(result.stderr)

            if result.returncode == 0:
                print(f"✓ {description} - 成功")
                return True, result.stdout
            else:
                return False, filtered_stderr

        except subprocess.TimeoutExpired:
            print(f"⚠ {description} - 超时")
            return False, "命令执行超时"
        except Exception as e:
            print(f"⚠ {description} - 异常: {str(e)}")
            return False, str(e)

    def _filter_wx_debug(self, stderr: str) -> str:
        """过滤掉 wxWidgets 调试信息"""
        if not stderr:
            return ""

        lines = stderr.split("\n")
        filtered = []

        for line in lines:
            if any(
                pattern in line
                for pattern in [
                    "Adding duplicate image handler",
                    "Debug: Adding duplicate",
                ]
            ):
                continue
            filtered.append(line)

        return "\n".join(filtered).strip()

    def run_erc(self) -> bool:
        """运行ERC检查"""
        if not self.sch_file.exists():
            print(f"⚠ 跳过ERC: 原理图文件不存在 ({self.sch_file})")
            return False

        report_file = self.output_dir / "erc_report.json"

        args = [
            self.kicad_cli,
            "sch",
            "erc",
            "--severity-all",
            "--format",
            "json",
            "--output",
            str(report_file),
            str(self.sch_file),
        ]

        success, output = self._run_command(args, "ERC检查")

        if report_file.exists():
            try:
                with open(report_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sheets = data.get("sheets", [])
                    violations = []
                    for sheet in sheets:
                        violations.extend(sheet.get("violations", []))

                    # 统计不同严重级别的问题数量
                    # error: 必须修复的错误
                    # warning: 建议修复的警告
                    # excluded: 已被用户排除的问题
                    errors = sum(1 for v in violations if v.get("severity") == "error")
                    warnings = sum(
                        1 for v in violations if v.get("severity") == "warning"
                    )
                    exclusions = sum(1 for v in violations if v.get("excluded", False))
                    total = len(violations)

                    if errors > 0:
                        self.results["erc"] = {
                            "status": "failed",
                            "violations": total,
                            "errors": errors,
                            "warnings": warnings,
                            "exclusions": exclusions,
                        }
                        print(f"  ✗ 发现 {errors} 个错误, {warnings} 个警告")
                    elif warnings > 0:
                        self.results["erc"] = {
                            "status": "passed",
                            "violations": total,
                            "errors": 0,
                            "warnings": warnings,
                            "exclusions": exclusions,
                        }
                        print(f"  ⚠ 发现 {warnings} 个警告（不影响通过）")
                    else:
                        self.results["erc"] = {
                            "status": "passed",
                            "violations": total,
                            "errors": 0,
                            "warnings": 0,
                            "exclusions": exclusions,
                        }
                        print("  ✓ 未发现问题")

            except json.JSONDecodeError as e:
                print(f"  ⚠ JSON解析失败: {e}")
                self.results["erc"] = {"status": "error", "violations": "unknown"}

        return True

    def run_drc(self) -> bool:
        """运行DRC检查"""
        if not self.pcb_file.exists():
            print(f"⚠ 跳过DRC: PCB文件不存在 ({self.pcb_file})")
            return False

        report_file = self.output_dir / "drc_report.json"

        args = [
            self.kicad_cli,
            "pcb",
            "drc",
            "--severity-all",
            "--format",
            "json",
            "--output",
            str(report_file),
            str(self.pcb_file),
        ]

        success, output = self._run_command(args, "DRC检查")

        if report_file.exists():
            try:
                with open(report_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 兼容不同版本的 JSON 结构
                    violations = data.get("violations", [])
                    if not violations:
                        sheets = data.get("sheets", [])
                        for sheet in sheets:
                            violations.extend(sheet.get("violations", []))

                    # 统计不同严重级别的问题数量
                    errors = sum(1 for v in violations if v.get("severity") == "error")
                    warnings = sum(
                        1 for v in violations if v.get("severity") == "warning"
                    )
                    exclusions = sum(1 for v in violations if v.get("excluded", False))
                    total = len(violations)

                    if errors > 0:
                        self.results["drc"] = {
                            "status": "failed",
                            "violations": total,
                            "errors": errors,
                            "warnings": warnings,
                            "exclusions": exclusions,
                        }
                        print(f"  ✗ 发现 {errors} 个错误, {warnings} 个警告")
                    elif warnings > 0:
                        self.results["drc"] = {
                            "status": "passed",
                            "violations": total,
                            "errors": 0,
                            "warnings": warnings,
                            "exclusions": exclusions,
                        }
                        print(f"  ⚠ 发现 {warnings} 个警告（不影响通过）")
                    else:
                        self.results["drc"] = {
                            "status": "passed",
                            "violations": total,
                            "errors": 0,
                            "warnings": 0,
                            "exclusions": exclusions,
                        }
                        print("  ✓ 未发现问题")

            except json.JSONDecodeError as e:
                print(f"  ⚠ JSON解析失败: {e}")
                self.results["drc"] = {"status": "error", "violations": "unknown"}

        return True

    def export_schematic_pdf(self) -> bool:
        """导出原理图PDF"""
        if not self.sch_file.exists():
            print(f"⚠ 跳过PDF导出: 原理图文件不存在")
            return False

        output_file = self.output_dir / f"{self.project_name}-Schematic.pdf"

        args = [
            self.kicad_cli,
            "sch",
            "export",
            "pdf",
            "--output",
            str(output_file),
            str(self.sch_file),
        ]

        success, _ = self._run_command(args, "导出原理图PDF")
        self.results["exports"]["schematic_pdf"] = output_file.exists()
        return success

    def export_bom(self) -> bool:
        """导出BOM清单（CSV格式）

        字段顺序：Description, Reference, Quantity, Value, Category,
                  Part-DB IPN, lcsc#, manf, manf#
        输出标签：描述, Reference, Qty, Value, Category,
                  Part-DB IPN, lcsc#, manf, manf#
        """
        if not self.sch_file.exists():
            print(f"⚠ 跳过BOM导出: 原理图文件不存在")
            return False

        output_file = self.output_dir / f"{self.project_name}-BOM.csv"

        fields = "Description,Reference,${QUANTITY},Value,Category,Part-DB IPN,lcsc#,manf,manf#"
        labels = "描述,Reference,Qty,Value,Category,Part-DB IPN,lcsc#,manf,manf#"
        group_by = "Value,Description,Category,Part-DB IPN,lcsc#,manf,manf#"

        args = [
            self.kicad_cli,
            "sch",
            "export",
            "bom",
            "--fields",
            fields,
            "--labels",
            labels,
            "--group-by",
            group_by,
            "--sort-field",
            "Reference",
            "--sort-asc",
            "--include-excluded-from-bom",
            "--output",
            str(output_file),
            str(self.sch_file),
        ]

        success, _ = self._run_command(args, "导出BOM")
        self.results["exports"]["bom"] = output_file.exists()
        return success

    def export_gerber(self) -> bool:
        """导出Gerber文件并打包为ZIP

        导出内容：
        - 默认仅导出指定的关键层（F/B.Cu、F/B.Paste、F/B.Silkscreen、F/B.Mask、Edge.Cuts）
        - 可通过 --gerber-layers 或 GERBER_LAYERS 覆盖，或设置为 all 导出全部层
        - 钻孔文件（Excellon 格式）
        - 自动打包为 ZIP 文件
        """
        if not self.pcb_file.exists():
            print(f"⚠ 跳过Gerber导出: PCB文件不存在")
            return False

        gerber_dir = self.output_dir / "gerber"
        gerber_dir.mkdir(exist_ok=True)

        args_gerber = [
            self.kicad_cli,
            "pcb",
            "export",
            "gerbers",
            "--output",
            str(gerber_dir) + "/",
            str(self.pcb_file),
        ]

        if self.gerber_layers:
            args_gerber.extend(["--layers", ",".join(self.gerber_layers)])

        success1, _ = self._run_command(args_gerber, "导出Gerber层文件")

        args_drill = [
            self.kicad_cli,
            "pcb",
            "export",
            "drill",
            "--format",
            "excellon",
            "--output",
            str(gerber_dir) + "/",
            str(self.pcb_file),
        ]

        success2, _ = self._run_command(args_drill, "导出钻孔文件")
        if success1 and success2:
            import zipfile

            zip_file = self.output_dir / f"{self.project_name}-Gerber.zip"

            with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in gerber_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(gerber_dir))

            print(f"✓ Gerber文件已打包: {zip_file}")
            self.results["exports"]["gerber_zip"] = zip_file.exists()

        return success1 and success2

    def export_pcb_images(self) -> bool:
        """导出PCB图像和3D模型"""
        if not self.pcb_file.exists():
            print(f"⚠ 跳过PCB图像导出: PCB文件不存在")
            return False

        all_success = True

        # 导出正面SVG
        front_svg = self.output_dir / f"{self.project_name}-PCB-Front.svg"
        args_front = [
            self.kicad_cli,
            "pcb",
            "export",
            "svg",
            "--output",
            str(front_svg),
            "--layers",
            "F.Cu,F.Mask,F.Silkscreen,Edge.Cuts",
            str(self.pcb_file),
        ]

        success, _ = self._run_command(args_front, "导出PCB正面图像")
        self.results["exports"]["pcb_front_svg"] = front_svg.exists()
        all_success = all_success and success

        # 导出背面SVG
        back_svg = self.output_dir / f"{self.project_name}-PCB-Back.svg"
        args_back = [
            self.kicad_cli,
            "pcb",
            "export",
            "svg",
            "--output",
            str(back_svg),
            "--layers",
            "B.Cu,B.Mask,B.Silkscreen,Edge.Cuts",
            str(self.pcb_file),
        ]

        success, _ = self._run_command(args_back, "导出PCB背面图像")
        self.results["exports"]["pcb_back_svg"] = back_svg.exists()
        all_success = all_success and success

        # 导出3D STEP模型
        step_file = self.output_dir / f"{self.project_name}-3D.step"

        args_step = [
            self.kicad_cli,
            "pcb",
            "export",
            "step",
            "--no-dnp",
            "--drill-origin",
            "--subst-models",
            "--min-distance",
            "0.01mm",
            "--output",
            str(step_file),
            str(self.pcb_file),
        ]

        success, _ = self._run_command(args_step, "导出3D STEP模型")

        # 验证STEP结果
        if step_file.exists() and step_file.stat().st_size > 0:
            file_size_kb = step_file.stat().st_size / 1024
            print(f"✓ STEP文件: {file_size_kb:.1f} KB")

            # 提示文件大小信息但不作为失败依据
            if file_size_kb < 100:
                print(f"  ℹ 文件较小（< 100KB），可能未包含元件 3D 模型")
                print(
                    f"  提示：需要设置 KICAD9_3DMODEL_DIR 环境变量并使用 --subst-models 参数"
                )

            self.results["exports"]["step_3d"] = True
        else:
            print(f"✗ STEP文件未生成或为空")
            self.results["exports"]["step_3d"] = False

        all_success = all_success and success
        return all_success

    def _get_system_info(self) -> dict:
        """获取系统和构建环境信息

        返回：
            包含操作系统、Python版本、KiCad版本和CI/CD环境信息的字典
        """
        import platform

        info = {
            "os": platform.system(),
            "os_version": platform.release(),
            "python_version": platform.python_version(),
            "kicad_cli": self.kicad_cli,
        }

        try:
            result = subprocess.run(
                [self.kicad_cli, "version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                info["kicad_version"] = result.stdout.strip()
        except:
            info["kicad_version"] = "未知"

        # 从 GitLab CI/CD 环境变量中提取关键信息
        # CI_COMMIT_SHA 截取前8位以便显示
        ci_vars = {
            "CI_RUNNER_DESCRIPTION": os.getenv("CI_RUNNER_DESCRIPTION", ""),
            "CI_RUNNER_TAGS": os.getenv("CI_RUNNER_TAGS", ""),
            "GITLAB_USER_LOGIN": os.getenv("GITLAB_USER_LOGIN", ""),
            "CI_COMMIT_SHA": (
                os.getenv("CI_COMMIT_SHA", "")[:8] if os.getenv("CI_COMMIT_SHA") else ""
            ),
            "CI_COMMIT_REF_NAME": os.getenv("CI_COMMIT_REF_NAME", ""),
        }

        info.update({k: v for k, v in ci_vars.items() if v})

        return info

    def generate_summary(self, skip_exports: bool = False) -> str:
        """生成构建摘要（Markdown 格式）

        生成包含以下内容的构建报告：
        - 构建状态和基本信息
        - ERC/DRC 质量检查结果（错误/警告统计）
        - 导出文件列表（成功/失败标识，仅在 skip_exports=False 时显示）
        - 测试环境详情（操作系统、工具版本等）

        参数：
            skip_exports: 是否跳过文件导出报告部分

        返回：
            Markdown 格式的报告字符串
        """
        from datetime import datetime, timezone, timedelta

        system_info = self._get_system_info()

        required_exports = [
            "schematic_pdf",
            "bom",
            "gerber_zip",
            "pcb_front_svg",
            "pcb_back_svg",
            "step_3d",
        ]

        failed_exports = [
            key
            for key in required_exports
            if not self.results["exports"].get(key, False)
        ]

        # 判断构建状态：检测模式下根据ERC/DRC错误判断，导出模式下根据文件导出判断
        erc_has_errors = self.results["erc"].get("errors", 0) > 0
        drc_has_errors = self.results["drc"].get("errors", 0) > 0

        if skip_exports:
            # 只检测模式：根据 ERC/DRC 判断
            if erc_has_errors or drc_has_errors:
                build_status = "检测失败"
                status_emoji = "❌"
            else:
                build_status = "检测成功"
                status_emoji = "✅"
        else:
            # 完整模式：同时考虑检测和导出
            if erc_has_errors or drc_has_errors:
                build_status = "❌ 质量检测失败"
                status_emoji = "❌"
            elif failed_exports:
                build_status = "❌ 文件导出失败"
                status_emoji = "❌"
            else:
                build_status = "✅ 构建成功"
                status_emoji = "✅"

        # 获取北京时间 (UTC+8)
        beijing_tz = timezone(timedelta(hours=8))
        beijing_time = datetime.now(beijing_tz)

        summary = f"""# {status_emoji} {self.project_name} - 构建报告

## 📋 构建信息

| 项目 | 信息 |
|------|------|
| **状态** | {build_status} |
| **时间** | {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间) |
| **项目** | {self.project_name} |"""

        # 添加提交信息
        if system_info.get("CI_COMMIT_SHA"):
            summary += f"\n| **提交** | `{system_info['CI_COMMIT_SHA']}` ({system_info.get('CI_COMMIT_REF_NAME', '')}) |"

        summary += "\n\n## 🔍 质量检查结果\n\n"

        # ERC 检查
        erc_result = self.results["erc"]
        if erc_result["status"] == "passed":
            if erc_result.get("warnings", 0) > 0:
                summary += f"### ✅ ERC (电气规则检查) - 通过\n\n- 警告: {erc_result.get('warnings', 0)} 个（不影响通过）\n"
                if erc_result.get("exclusions", 0) > 0:
                    summary += f"- 已排除: {erc_result['exclusions']} 个\n"
                summary += "\n"
            else:
                summary += f"### ✅ ERC (电气规则检查) - 通过\n\n无错误和警告\n\n"
        elif erc_result["status"] == "failed":
            summary += f"### ❌ ERC (电气规则检查) - 失败\n\n- 错误: {erc_result.get('errors', 0)} 个\n- 警告: {erc_result.get('warnings', 0)} 个\n"
            if erc_result.get("exclusions", 0) > 0:
                summary += f"- 已排除: {erc_result['exclusions']} 个\n"
            summary += "\n"
        else:
            summary += f"### ℹ️ ERC (电气规则检查) - {erc_result['status']}\n\n"

        # DRC 检查
        drc_result = self.results["drc"]
        if drc_result["status"] == "passed":
            if drc_result.get("warnings", 0) > 0:
                summary += f"### ✅ DRC (设计规则检查) - 通过\n\n- 警告: {drc_result.get('warnings', 0)} 个（不影响通过）\n"
                if drc_result.get("exclusions", 0) > 0:
                    summary += f"- 已排除: {drc_result['exclusions']} 个\n"
                summary += "\n"
            else:
                summary += f"### ✅ DRC (设计规则检查) - 通过\n\n无错误和警告\n\n"
        elif drc_result["status"] == "failed":
            summary += f"### ❌ DRC (设计规则检查) - 失败\n\n- 错误: {drc_result.get('errors', 0)} 个\n- 警告: {drc_result.get('warnings', 0)} 个\n"
            if drc_result.get("exclusions", 0) > 0:
                summary += f"- 已排除: {drc_result['exclusions']} 个\n"
            summary += "\n"
        else:
            summary += f"### ℹ️ DRC (设计规则检查) - {drc_result['status']}\n\n"

        # 只在非跳过导出模式下显示文件导出部分
        if not skip_exports:
            summary += "## 📦 生成文件\n\n"

            exports = [
                ("schematic_pdf", "📄 原理图PDF", True),
                ("bom", "📋 BOM清单(CSV)", True),
                ("gerber_zip", "📦 Gerber文件包(ZIP)", True),
                ("pcb_front_svg", "🖼️ PCB正面图(SVG)", True),
                ("pcb_back_svg", "🖼️ PCB背面图(SVG)", True),
                ("step_3d", "🎨 3D模型(STEP)", True),
            ]

            for key, name, required in exports:
                exported = self.results["exports"].get(key, False)
                if exported:  # 如果导出成功
                    summary += f"- ✅ {name}\n"
                elif required:  # 如果导出失败 且 required=True
                    summary += f"- ❌ {name}\n"
                else:  # 如果导出失败 且 required=False
                    summary += f"- ⏭️ {name} (可选)\n"

            summary += "\n"

        # 测试环境信息(折叠区域)
        summary += f"\n<details>\n<summary>🔧 测试环境详情</summary>\n\n"
        summary += f"- **操作系统**: {system_info.get('os', 'unknown')} {system_info.get('os_version', '')}\n"
        summary += f"- **Python版本**: {system_info.get('python_version', 'unknown')}\n"
        summary += f"- **KiCad CLI**: `{system_info.get('kicad_cli', 'unknown')}`\n"
        summary += f"- **KiCad版本**: {system_info.get('kicad_version', 'unknown')}\n"

        if system_info.get("CI_RUNNER_DESCRIPTION"):
            summary += f"- **CI Runner**: {system_info['CI_RUNNER_DESCRIPTION']}\n"
        if system_info.get("CI_RUNNER_TAGS"):
            summary += f"- **Runner标签**: {system_info['CI_RUNNER_TAGS']}\n"

        summary += "\n</details>\n"

        return summary

    def save_summary(self, skip_exports: bool = False):
        """保存构建摘要

        参数：
            skip_exports: 是否跳过文件导出报告部分
        """
        summary = self.generate_summary(skip_exports=skip_exports)
        summary_file = self.output_dir / "build_summary.md"

        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(summary)

        print(f"\n✓ 构建摘要已保存: {summary_file}")
        print("\n" + summary)

    def run_all(self, skip_checks=False, skip_exports=False):
        """运行所有任务"""
        print("=" * 60)
        print("KiCad 自动化导出工具")
        print("=" * 60)
        print(f"项目: {self.project_name}")
        print(f"输出目录: {self.output_dir}")
        print("=" * 60)

        # 质量检查
        if not skip_checks:
            self.run_erc()
            self.run_drc()

        # 导出文件
        if not skip_exports:
            self.export_schematic_pdf()
            self.export_bom()
            self.export_gerber()
            self.export_pcb_images()

        # 生成摘要（传递 skip_exports 参数）
        self.save_summary(skip_exports=skip_exports)

        print("\n" + "=" * 60)
        print("✓ 所有任务完成")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="KiCad 自动化导出工具 (KiCad 9.0+)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：

  完整流程 (检查 + 导出)：
    python kicad_export.py project.kicad_pro
    python kicad_export.py project.kicad_pro -o build

  CI/CD 检查阶段 (仅检查，有错误即失败)：
    python kicad_export.py project.kicad_pro --skip-exports

  CI/CD 导出阶段 (包含检查但不影响退出码)：
    python kicad_export.py project.kicad_pro --export-mode

  自定义 Gerber 层：
    python kicad_export.py project.kicad_pro --gerber-layers "F.Cu,B.Cu,Edge.Cuts"
    python kicad_export.py project.kicad_pro --gerber-layers "all"

  指定 KiCad CLI 路径：
    # Linux/macOS
    python kicad_export.py project.kicad_pro --kicad-cli /usr/bin/kicad-cli
    
    # Windows
    python kicad_export.py project.kicad_pro --kicad-cli "C:\\Program Files\\KiCad\\9.0\\bin\\kicad-cli.exe"
        """,
    )

    parser.add_argument("project", help="KiCad 项目文件 (.kicad_pro)")
    parser.add_argument(
        "-o", "--output", default="outputs", help="输出目录 (默认: outputs)"
    )
    parser.add_argument(
        "--kicad-cli",
        dest="kicad_cli_path",
        help="指定 KiCad CLI 路径 (自动检测失败时使用)",
    )
    parser.add_argument(
        "--gerber-layers",
        help="自定义 Gerber 层 (逗号分隔，默认: "
        + ",".join(DEFAULT_GERBER_LAYERS)
        + "，设为 all 导出全部层，或通过 GERBER_LAYERS 环境变量设置)",
    )
    parser.add_argument("--skip-checks", action="store_true", help="跳过 ERC/DRC 检查")
    parser.add_argument(
        "--skip-exports", action="store_true", help="跳过文件导出 (仅运行检查)"
    )
    parser.add_argument(
        "--export-mode",
        action="store_true",
        help="导出模式：运行检查但只根据文件导出判断成败 (推荐用于 CI/CD)",
    )

    args = parser.parse_args()

    try:
        exporter = KiCadExporter(
            args.project,
            args.output,
            args.kicad_cli_path,
            args.gerber_layers,
        )
        exporter.run_all(skip_checks=args.skip_checks, skip_exports=args.skip_exports)

        # 判断运行模式
        check_only_mode = args.skip_exports
        export_only_mode = args.skip_checks or args.export_mode

        if check_only_mode:
            # 检查模式：ERC 或 DRC 有错误（不包括警告）视为失败
            erc_failed = exporter.results["erc"]["status"] == "failed"
            drc_failed = exporter.results["drc"]["status"] == "failed"

            if erc_failed or drc_failed:
                erc_status = exporter.results["erc"]
                drc_status = exporter.results["drc"]
                print(f"\n❌ 检测失败:", file=sys.stderr)
                if erc_failed:
                    print(
                        f"  ERC: {erc_status.get('errors', 0)} 个错误, {erc_status.get('warnings', 0)} 个警告",
                        file=sys.stderr,
                    )
                if drc_failed:
                    print(
                        f"  DRC: {drc_status.get('errors', 0)} 个错误, {drc_status.get('warnings', 0)} 个警告",
                        file=sys.stderr,
                    )
                sys.exit(1)
            else:
                erc_status = exporter.results["erc"]
                drc_status = exporter.results["drc"]
                total_warnings = erc_status.get("warnings", 0) + drc_status.get(
                    "warnings", 0
                )
                if total_warnings > 0:
                    print(f"\n✅ 检测通过: 无错误（{total_warnings} 个警告不影响通过）")
                else:
                    print(f"\n✅ 检测通过: ERC 和 DRC 均无问题")
                sys.exit(0)

        elif export_only_mode:
            # 导出模式：只要文件成功导出就算成功
            required_exports = [
                "schematic_pdf",
                "bom",
                "gerber_zip",
                "pcb_front_svg",
                "pcb_back_svg",
                "step_3d",
            ]
            failed_exports = [
                key
                for key in required_exports
                if not exporter.results["exports"].get(key, False)
            ]

            if failed_exports:
                print(f"\n❌ 导出失败: 以下文件未成功生成", file=sys.stderr)
                for key in failed_exports:
                    print(f"  - {key}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"\n✅ 导出成功: 所有必需文件已生成")
                sys.exit(0)

        else:
            # 完整模式：检查 + 导出，只有错误才算失败
            erc_has_errors = exporter.results["erc"].get("errors", 0) > 0
            drc_has_errors = exporter.results["drc"].get("errors", 0) > 0

            required_exports = [
                "schematic_pdf",
                "bom",
                "gerber_zip",
                "pcb_front_svg",
                "pcb_back_svg",
                "step_3d",
            ]
            failed_exports = [
                key
                for key in required_exports
                if not exporter.results["exports"].get(key, False)
            ]

            if erc_has_errors or drc_has_errors:
                erc_status = exporter.results["erc"]
                drc_status = exporter.results["drc"]
                print(f"\n❌ 质量检测失败:", file=sys.stderr)
                if erc_has_errors:
                    print(
                        f"  ERC: {erc_status.get('errors', 0)} 个错误, {erc_status.get('warnings', 0)} 个警告",
                        file=sys.stderr,
                    )
                if drc_has_errors:
                    print(
                        f"  DRC: {drc_status.get('errors', 0)} 个错误, {drc_status.get('warnings', 0)} 个警告",
                        file=sys.stderr,
                    )
                sys.exit(1)
            elif failed_exports:
                print(f"\n❌ 文件导出失败: 以下文件未成功生成", file=sys.stderr)
                for key in failed_exports:
                    print(f"  - {key}", file=sys.stderr)
                sys.exit(1)
            else:
                erc_status = exporter.results["erc"]
                drc_status = exporter.results["drc"]
                total_warnings = erc_status.get("warnings", 0) + drc_status.get(
                    "warnings", 0
                )
                if total_warnings > 0:
                    print(
                        f"\n✅ 构建成功: 无错误且文件已导出（{total_warnings} 个警告不影响通过）"
                    )
                else:
                    print(f"\n✅ 构建成功: 检查通过且文件已导出")
                sys.exit(0)

    except Exception as e:
        print(f"\n✗ 错误: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
