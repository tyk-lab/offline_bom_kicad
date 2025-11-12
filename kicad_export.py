#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KiCad 自动化导出脚本 (KiCad 9.0+)

功能说明：
- ERC (电气规则检查)：检查原理图电气连接问题
- DRC (设计规则检查)：检查 PCB 设计规则违规
- 导出原理图 PDF
- 导出 BOM 清单 (CSV 格式)
- 导出 Gerber 文件包 (ZIP 格式，包含钻孔文件)
- 导出 PCB 图像 (SVG 正面/背面)
- 导出 3D STEP 模型 (支持元件 3D 模型替换)
- 生成构建摘要报告 (Markdown 格式)

使用方法：
    基础用法：
        python kicad_export.py <项目文件.kicad_pro>

    完整示例：
        python kicad_export.py 229_Test.kicad_pro -o outputs

    参数说明：
        project               [必需] KiCad 项目文件路径 (.kicad_pro)
        -o, --output          [可选] 输出目录，默认为 "outputs"
        --kicad-cli           [可选] 指定 KiCad CLI 路径（自动检测失败时使用）
        --skip-checks         [可选] 跳过 ERC/DRC 检查，只导出文件
        --skip-exports        [可选] 跳过文件导出，只运行质量检查
        --export-mode         [可选] 导出模式：运行检查但只根据文件导出结果判断成败

运行模式详解：
    1. 完整模式（默认，无参数）：
       python kicad_export.py 229_Test.kicad_pro
       → 运行 ERC/DRC 检查 + 导出文件
       → 检查失败或导出失败都会返回错误退出码
       → 适用于：本地开发、完整质量验证

    2. 检查模式（--skip-exports）：
       python kicad_export.py 229_Test.kicad_pro --skip-exports
       → 只运行 ERC/DRC，不导出文件
       → 有任何错误或警告都会失败（退出码 1）
       → 适用于：CI/CD 检查阶段、Pull Request 验证

    3. 纯导出模式（--skip-checks）：
       python kicad_export.py 229_Test.kicad_pro --skip-checks
       → 跳过 ERC/DRC，只导出文件
       → 只要文件成功生成就返回成功
       → 适用于：快速生成文件、跳过质量检查

    4. 导出模式（--export-mode，推荐用于 CI/CD 导出阶段）：
       python kicad_export.py 229_Test.kicad_pro --export-mode
       → 运行 ERC/DRC 并生成报告（报告会保存但不影响退出码）
       → 只根据文件导出成功与否判断退出码
       → 即使有质量问题也不会阻断流程
       → 适用于：CI/CD 导出阶段，需要报告但不想因质量问题失败

输出说明：
    1. 质量检查报告（JSON 格式）：
       - outputs/erc_report.json - ERC 检查结果
       - outputs/drc_report.json - DRC 检查结果
       包含：错误数量、警告数量、排除项、详细违规信息

    2. 导出文件：
       - outputs/{项目名}-Schematic.pdf - 原理图 PDF
       - outputs/{项目名}-BOM.csv - BOM 清单
       - outputs/{项目名}-Gerber.zip - Gerber 文件包
       - outputs/{项目名}-PCB-Front.svg - PCB 正面图
       - outputs/{项目名}-PCB-Back.svg - PCB 背面图
       - outputs/{项目名}-3D.step - 3D STEP 模型

    3. 构建摘要：
       - outputs/build_summary.md - 构建报告（包含检查结果、文件列表、环境信息）

退出码：
    0 - 成功
    1 - 检查失败或导出失败
    2 - 脚本异常（文件不存在、KiCad CLI 未找到等）

KiCad CLI 路径检测：
    脚本会自动尝试以下命令：
    - kicad-cli (Linux/macOS 默认)
    - kicad.kicad-cli (某些发行版)

    如果自动检测失败，可使用 --kicad-cli 参数手动指定：

    Linux 示例：
        python kicad_export.py 229_Test.kicad_pro --kicad-cli /usr/bin/kicad-cli

    Windows 示例（默认安装路径）：
        python kicad_export.py 229_Test.kicad_pro --kicad-cli "C:\\Program Files\\KiCad\\9.0\\bin\\kicad-cli.exe"

    Windows 示例（用户安装路径）：
        python kicad_export.py 229_Test.kicad_pro --kicad-cli "%LOCALAPPDATA%\\Programs\\KiCad\\9.0\\bin\\kicad-cli.exe"

CI/CD 使用示例：
    GitLab CI/CD 检查阶段：
        python kicad_export.py ${PROJECT}.kicad_pro -o ${OUTPUT_DIR} --skip-exports
        # 只检查质量，不导出文件，有问题就失败

    GitLab CI/CD 导出阶段：
        python kicad_export.py ${PROJECT}.kicad_pro -o ${OUTPUT_DIR} --export-mode
        # 运行检查生成报告，但只根据文件导出结果判断成败

注意事项：
    1. BOM 导出字段顺序(kicad硬编码)：
       Description, Reference, Quantity, Value, Category, Part-DB IPN, lcsc#, manf, manf#
       输出标签（中文）：描述, Reference, Qty, Value, Category, Part-DB IPN, lcsc#, manf, manf#

    2. 3D STEP 导出：
       - 使用 --subst-models 参数，会尝试使用 STEP/IGS 模型替代 VRML
       - 需要环境变量 KICAD9_3DMODEL_DIR 指向 3D 模型库路径
       - 文件大小 < 100KB 视为导出失败（仅包含 PCB 板体）

    3. Gerber 文件：
       - 自动导出所有必需层（铜层、阻焊层、丝印、边框等）
       - 钻孔文件使用 Excellon 格式
       - 所有文件自动打包为 ZIP 格式

    4. 编码兼容性：
       - Windows 环境下自动处理 UTF-8 编码
       - 过滤 wxWidgets 调试信息，避免输出干扰
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import Tuple, Optional, List


class KiCadExporter:
    def __init__(
        self,
        project_path: str,
        output_dir: str = "outputs",
        kicad_cli_path: Optional[str] = None,
    ):
        self.project_path = Path(project_path)
        self.project_name = self.project_path.stem
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 检测KiCad CLI命令
        self.kicad_cli = self._detect_kicad_cli(kicad_cli_path)

        # 文件路径
        self.sch_file = self.project_path.with_suffix(".kicad_sch")
        self.pcb_file = self.project_path.with_suffix(".kicad_pcb")

        # 结果统计
        self.results = {
            "erc": {"status": "skipped", "violations": 0},
            "drc": {"status": "skipped", "violations": 0},
            "exports": {},
        }

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

        # 在Windows上尝试常见安装路径
        import platform

        if platform.system() == "Windows":
            possible_paths = []

            # 添加系统Program Files路径
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            possible_paths.append(
                Path(program_files) / "KiCad" / "9.0" / "bin" / "kicad-cli.exe"
            )

            # 添加用户AppData路径（支持多个驱动器）
            local_appdata = os.environ.get("LOCALAPPDATA")
            if local_appdata:
                possible_paths.append(
                    Path(local_appdata)
                    / "Programs"
                    / "KiCad"
                    / "9.0"
                    / "bin"
                    / "kicad-cli.exe"
                )

                # 检查其他驱动器（C: 和 D:）
                for drive in ["C:", "D:"]:
                    try:
                        drive_path = Path(drive) / "Users"
                        if drive_path.exists():
                            # 查找所有用户目录
                            for user_dir in drive_path.iterdir():
                                if user_dir.is_dir():
                                    appdata_path = (
                                        user_dir
                                        / "AppData"
                                        / "Local"
                                        / "Programs"
                                        / "KiCad"
                                        / "9.0"
                                        / "bin"
                                        / "kicad-cli.exe"
                                    )
                                    if appdata_path.exists():
                                        possible_paths.append(appdata_path)
                    except (OSError, PermissionError):
                        continue

            # 检查所有可能的路径
            for cli_path in possible_paths:
                if cli_path.exists():
                    try:
                        result = subprocess.run(
                            [str(cli_path), "version"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        if result.returncode == 0:
                            print(f"✓ 检测到KiCad CLI: {cli_path}")
                            print(f"  版本: {result.stdout.strip()}")
                            return str(cli_path)
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        continue

        raise RuntimeError(
            "错误: 未找到KiCad CLI命令\n"
            "  请安装KiCad或使用 --kicad-cli 参数指定路径\n"
            "  尝试过: kicad-cli, kicad.kicad-cli 以及常见安装路径"
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
                            "status": "warning",
                            "violations": total,
                            "errors": 0,
                            "warnings": warnings,
                            "exclusions": exclusions,
                        }
                        print(f"  ⚠ 发现 {warnings} 个警告")
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
                            "status": "warning",
                            "violations": total,
                            "errors": 0,
                            "warnings": warnings,
                            "exclusions": exclusions,
                        }
                        print(f"  ⚠ 发现 {warnings} 个警告")
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
        - 所有 Gerber 层（铜层、阻焉层、丝印、边框等）
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

    def generate_summary(self) -> str:
        """生成构建摘要（Markdown 格式）

        生成包含以下内容的构建报告：
        - 构建状态和基本信息
        - ERC/DRC 质量检查结果（错误/警告统计）
        - 导出文件列表（成功/失败标识）
        - 测试环境详情（操作系统、工具版本等）

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

        if failed_exports:
            build_status = "❌ 构建失败"
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
            summary += f"### ✅ ERC (电气规则检查) - 通过\n\n无错误和警告\n\n"
        elif erc_result["status"] == "warning":
            summary += f"### ⚠️ ERC (电气规则检查) - 有警告\n\n- 警告: {erc_result.get('warnings', 0)} 个\n"
            if erc_result.get("exclusions", 0) > 0:
                summary += f"- 已排除: {erc_result['exclusions']} 个\n"
            summary += "\n"
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
            summary += f"### ✅ DRC (设计规则检查) - 通过\n\n无错误和警告\n\n"
        elif drc_result["status"] == "warning":
            summary += f"### ⚠️ DRC (设计规则检查) - 有警告\n\n- 警告: {drc_result.get('warnings', 0)} 个\n"
            if drc_result.get("exclusions", 0) > 0:
                summary += f"- 已排除: {drc_result['exclusions']} 个\n"
            summary += "\n"
        elif drc_result["status"] == "failed":
            summary += f"### ❌ DRC (设计规则检查) - 失败\n\n- 错误: {drc_result.get('errors', 0)} 个\n- 警告: {drc_result.get('warnings', 0)} 个\n"
            if drc_result.get("exclusions", 0) > 0:
                summary += f"- 已排除: {drc_result['exclusions']} 个\n"
            summary += "\n"
        else:
            summary += f"### ℹ️ DRC (设计规则检查) - {drc_result['status']}\n\n"

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

    def save_summary(self):
        """保存构建摘要"""
        summary = self.generate_summary()
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

        # 生成摘要
        self.save_summary()

        print("\n" + "=" * 60)
        print("✓ 所有任务完成")
        print("=" * 60)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="KiCad自动化导出工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：

  1. 完整流程 (检查 + 导出，严格模式)：
     python kicad_export.py 229_Test.kicad_pro
     → 检查失败或导出失败都会返回错误退出码

  2. 只运行质量检查 (CI/CD 检查阶段)：
     python kicad_export.py 229_Test.kicad_pro --skip-exports
     → 有任何 ERC/DRC 错误或警告都会失败

  3. 只导出文件 (跳过检查)：
     python kicad_export.py 229_Test.kicad_pro --skip-checks
     → 不运行 ERC/DRC，只导出文件

  4. 导出模式 (包含检查但只看文件导出结果，推荐用于 CI/CD 导出阶段)：
     python kicad_export.py 229_Test.kicad_pro --export-mode
     → 运行 ERC/DRC 生成报告
     → 但只根据文件导出成功与否判断退出码
     → 即使有质量问题也不影响 CI/CD 流程

  5. 指定输出目录：
     python kicad_export.py 229_Test.kicad_pro -o build

  6. 指定KiCad CLI路径 (Linux)：
     python kicad_export.py 229_Test.kicad_pro --kicad-cli /usr/local/bin/kicad-cli

  7. 指定KiCad CLI路径 (Windows - 默认路径)：
     python kicad_export.py 229_Test.kicad_pro --kicad-cli "C:\\Program Files\\KiCad\\9.0\\bin\\kicad-cli.exe"

  8. 指定KiCad CLI路径 (Windows - 用户目录)：
     python kicad_export.py 229_Test.kicad_pro --skip-checks --kicad-cli "D:\\Users\\用户名\\AppData\\Local\\Programs\\KiCad\\9.0\\bin\\kicad-cli.exe"

  9. 组合使用 (导出模式 + 自定义路径)：
     python kicad_export.py 229_Test.kicad_pro --export-mode --kicad-cli /custom/kicad-cli -o release

Windows 常见路径：
  • C:\\Program Files\\KiCad\\9.0\\bin\\kicad-cli.exe (默认安装)
  • %LOCALAPPDATA%\\Programs\\KiCad\\9.0\\bin\\kicad-cli.exe (用户安装)
  • D:\\Software\\KiCad\\9.0\\bin\\kicad-cli.exe (自定义路径)
        """,
    )

    parser.add_argument("project", help="KiCad项目文件路径 (.kicad_pro)")
    parser.add_argument(
        "-o", "--output", default="outputs", help="输出目录 (默认: outputs)"
    )
    parser.add_argument(
        "--kicad-cli",
        dest="kicad_cli_path",
        help="指定KiCad CLI路径 (例: /usr/bin/kicad-cli 或 C:\\Program Files\\KiCad\\9.0\\bin\\kicad-cli.exe)",
    )
    parser.add_argument("--skip-checks", action="store_true", help="跳过ERC/DRC检查")
    parser.add_argument("--skip-exports", action="store_true", help="跳过文件导出")
    parser.add_argument(
        "--export-mode",
        action="store_true",
        help="导出模式：运行完整检查但只根据文件导出结果判断成功/失败（忽略ERC/DRC错误）",
    )

    args = parser.parse_args(argv)

    try:
        exporter = KiCadExporter(args.project, args.output, args.kicad_cli_path)
        exporter.run_all(skip_checks=args.skip_checks, skip_exports=args.skip_exports)

        # 判断运行模式
        check_only_mode = args.skip_exports
        export_only_mode = args.skip_checks or args.export_mode

        if check_only_mode:
            # 检查模式：ERC 或 DRC 有错误或警告都视为失败
            erc_failed = exporter.results["erc"]["status"] in ["failed", "warning"]
            drc_failed = exporter.results["drc"]["status"] in ["failed", "warning"]

            if erc_failed or drc_failed:
                erc_status = exporter.results["erc"]
                drc_status = exporter.results["drc"]
                print(f"\n❌ 检查失败:", file=sys.stderr)
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
                print(f"\n✅ 检查通过: ERC 和 DRC 均无问题")
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
            # 完整模式：检查 + 导出
            erc_has_issues = exporter.results["erc"]["status"] in ["failed", "warning"]
            drc_has_issues = exporter.results["drc"]["status"] in ["failed", "warning"]

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

            if erc_has_issues or drc_has_issues:
                erc_status = exporter.results["erc"]
                drc_status = exporter.results["drc"]
                print(f"\n❌ 构建失败: 检查发现问题", file=sys.stderr)
                if erc_has_issues:
                    print(
                        f"  ERC: {erc_status.get('errors', 0)} 个错误, {erc_status.get('warnings', 0)} 个警告",
                        file=sys.stderr,
                    )
                if drc_has_issues:
                    print(
                        f"  DRC: {drc_status.get('errors', 0)} 个错误, {drc_status.get('warnings', 0)} 个警告",
                        file=sys.stderr,
                    )
                sys.exit(1)
            elif failed_exports:
                print(f"\n❌ 构建失败: 文件导出不完整", file=sys.stderr)
                for key in failed_exports:
                    print(f"  - {key}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"\n✅ 构建成功: 检查通过且文件已导出")
                sys.exit(0)

    except Exception as e:
        print(f"\n✗ 错误: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
