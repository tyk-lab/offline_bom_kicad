#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOM 转换与 KiCad 导出 GUI 工具

基于 bom_transform.py 和 kicad_export.py 脚本的图形界面版本。

功能：
- BOM转换：选择输入 CSV 文件，进行格式转换和校验
- KiCad导出：选择 KiCad 项目文件，导出各种文件并运行质量检查
"""

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import sys
import io
import contextlib
import subprocess
from pathlib import Path
from typing import Optional

# 导入原始脚本的 main 函数
try:
    from bom_transform import main as bom_main
except ImportError as e:
    messagebox.showerror(
        "导入错误",
        f"无法导入 bom_transform 模块: {e}\n请确保 bom_transform.py 在同一目录下。",
    )
    sys.exit(1)

try:
    from kicad_export import main as kicad_main
except ImportError as e:
    messagebox.showerror(
        "导入错误",
        f"无法导入 kicad_export 模块: {e}\n请确保 kicad_export.py 在同一目录下。",
    )
    sys.exit(1)


class BOMTransformGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BOM 转换与 KiCad 导出工具")
        self.root.geometry("700x600")

        # 创建选项卡
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # BOM转换选项卡
        self.bom_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.bom_frame, text="BOM 转换")
        self.create_bom_tab()

        # KiCad导出选项卡
        self.kicad_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.kicad_frame, text="KiCad 导出")
        self.create_kicad_tab()

        # 启动时自动检测KiCad CLI
        self.auto_detect_kicad_cli_on_startup()

    def detect_kicad_cli(self) -> Optional[str]:
        """检测可用的KiCad CLI命令"""
        # 尝试系统路径中的命令
        commands = ["kicad-cli", "kicad.kicad-cli"]

        for cmd in commands:
            try:
                result = subprocess.run(
                    [cmd, "version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
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

                # 添加用户指定的常见安装路径
                possible_paths.append(
                    Path(
                        "D:\\Users\\tyk\\AppData\\Local\\Programs\\KiCad\\9.0\\bin\\kicad-cli.exe"
                    )
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
                            return str(cli_path)
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        continue

        return None

    def create_bom_tab(self):
        # BOM转换变量
        self.bom_input_file = tk.StringVar()
        self.bom_output_dir = tk.StringVar(value=os.getcwd())
        self.bom_project_name = tk.StringVar()
        self.bom_mapping_file = tk.StringVar()
        self.bom_quiet = tk.BooleanVar(value=False)

        # 输入文件
        tk.Label(self.bom_frame, text="输入 CSV 文件:").grid(
            row=0, column=0, sticky="w", padx=10, pady=5
        )
        tk.Entry(self.bom_frame, textvariable=self.bom_input_file, width=50).grid(
            row=0, column=1, padx=10, pady=5
        )
        tk.Button(
            self.bom_frame, text="浏览...", command=self.select_bom_input_file
        ).grid(row=0, column=2, padx=10, pady=5)

        # 输出目录
        tk.Label(self.bom_frame, text="输出目录:").grid(
            row=1, column=0, sticky="w", padx=10, pady=5
        )
        tk.Entry(self.bom_frame, textvariable=self.bom_output_dir, width=50).grid(
            row=1, column=1, padx=10, pady=5
        )
        tk.Button(
            self.bom_frame, text="浏览...", command=self.select_bom_output_dir
        ).grid(row=1, column=2, padx=10, pady=5)

        # 项目名称
        tk.Label(self.bom_frame, text="项目名称 (可选):").grid(
            row=2, column=0, sticky="w", padx=10, pady=5
        )
        tk.Entry(self.bom_frame, textvariable=self.bom_project_name, width=50).grid(
            row=2, column=1, padx=10, pady=5
        )

        # 映射文件
        tk.Label(self.bom_frame, text="映射配置文件 (可选):").grid(
            row=3, column=0, sticky="w", padx=10, pady=5
        )
        tk.Entry(self.bom_frame, textvariable=self.bom_mapping_file, width=50).grid(
            row=3, column=1, padx=10, pady=5
        )
        tk.Button(
            self.bom_frame, text="浏览...", command=self.select_bom_mapping_file
        ).grid(row=3, column=2, padx=10, pady=5)

        # 选项
        tk.Checkbutton(
            self.bom_frame, text="静默模式 (不显示详细错误)", variable=self.bom_quiet
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        # 运行按钮
        tk.Button(
            self.bom_frame,
            text="运行 BOM 转换",
            command=self.run_bom_transform,
            bg="green",
            fg="white",
        ).grid(row=5, column=0, columnspan=3, pady=10)

    def create_kicad_tab(self):
        # KiCad导出变量
        self.kicad_project_file = tk.StringVar()
        self.kicad_output_dir = tk.StringVar(value="outputs")
        self.kicad_cli_path = tk.StringVar()
        self.kicad_skip_checks = tk.BooleanVar(value=False)
        self.kicad_skip_exports = tk.BooleanVar(value=False)
        self.kicad_export_mode = tk.BooleanVar(value=False)

        # 项目文件
        tk.Label(self.kicad_frame, text="KiCad 项目文件:").grid(
            row=0, column=0, sticky="w", padx=10, pady=5
        )
        tk.Entry(self.kicad_frame, textvariable=self.kicad_project_file, width=50).grid(
            row=0, column=1, padx=10, pady=5
        )
        tk.Button(
            self.kicad_frame, text="浏览...", command=self.select_kicad_project_file
        ).grid(row=0, column=2, padx=10, pady=5)

        # 输出目录
        tk.Label(self.kicad_frame, text="输出目录:").grid(
            row=1, column=0, sticky="w", padx=10, pady=5
        )
        tk.Entry(self.kicad_frame, textvariable=self.kicad_output_dir, width=50).grid(
            row=1, column=1, padx=10, pady=5
        )
        tk.Button(
            self.kicad_frame, text="浏览...", command=self.select_kicad_output_dir
        ).grid(row=1, column=2, padx=10, pady=5)

        # KiCad CLI路径
        tk.Label(self.kicad_frame, text="KiCad CLI 路径:").grid(
            row=2, column=0, sticky="w", padx=10, pady=5
        )
        tk.Entry(self.kicad_frame, textvariable=self.kicad_cli_path, width=50).grid(
            row=2, column=1, padx=10, pady=5
        )
        tk.Button(
            self.kicad_frame, text="浏览...", command=self.select_kicad_cli_path
        ).grid(row=2, column=2, padx=10, pady=5)
        tk.Button(
            self.kicad_frame, text="自动检测", command=self.auto_detect_kicad_cli
        ).grid(row=2, column=3, padx=10, pady=5)

        # 选项
        tk.Checkbutton(
            self.kicad_frame, text="跳过 ERC/DRC 检查", variable=self.kicad_skip_checks
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        tk.Checkbutton(
            self.kicad_frame, text="跳过文件导出", variable=self.kicad_skip_exports
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        tk.Checkbutton(
            self.kicad_frame,
            text="导出模式 (检查但只看文件导出结果)",
            variable=self.kicad_export_mode,
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        # 运行按钮
        tk.Button(
            self.kicad_frame,
            text="运行 KiCad 导出",
            command=self.run_kicad_export,
            bg="blue",
            fg="white",
        ).grid(row=6, column=0, columnspan=4, pady=10)

    # BOM转换相关方法
    def select_bom_input_file(self):
        file_path = filedialog.askopenfilename(
            title="选择输入 CSV 文件",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
        )
        if file_path:
            self.bom_input_file.set(file_path)
            # 自动设置输出目录为输入文件目录的outputs子目录
            input_dir = os.path.dirname(file_path)
            output_dir = os.path.join(input_dir, "outputs")
            self.bom_output_dir.set(output_dir)

    def select_bom_output_dir(self):
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.bom_output_dir.set(dir_path)

    def select_bom_mapping_file(self):
        file_path = filedialog.askopenfilename(
            title="选择映射配置文件",
            filetypes=[("YAML 文件", "*.yml *.yaml"), ("所有文件", "*.*")],
        )
        if file_path:
            self.bom_mapping_file.set(file_path)

    def run_bom_transform(self):
        # 验证输入
        if not self.bom_input_file.get():
            messagebox.showerror("错误", "请选择输入 CSV 文件")
            return

        if not os.path.isfile(self.bom_input_file.get()):
            messagebox.showerror("错误", "输入文件不存在")
            return

        # 确保输出目录存在，如果不存在则创建
        output_dir = self.bom_output_dir.get()
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
                print(f"创建输出目录: {output_dir}")
            except OSError as e:
                messagebox.showerror("错误", f"无法创建输出目录: {e}")
                return

        # 构建参数
        args = ["--input", self.bom_input_file.get(), "--output-dir", output_dir]

        if self.bom_project_name.get():
            args.extend(["--project-name", self.bom_project_name.get()])

        if self.bom_mapping_file.get():
            args.extend(["--mapping", self.bom_mapping_file.get()])

        if self.bom_quiet.get():
            args.append("--quiet")

        self.run_command(bom_main, args, "BOM转换")

    # KiCad导出相关方法
    def select_kicad_project_file(self):
        file_path = filedialog.askopenfilename(
            title="选择 KiCad 项目文件",
            filetypes=[("KiCad 项目文件", "*.kicad_pro"), ("所有文件", "*.*")],
        )
        if file_path:
            self.kicad_project_file.set(file_path)

    def select_kicad_output_dir(self):
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.kicad_output_dir.set(dir_path)

    def select_kicad_cli_path(self):
        file_path = filedialog.askopenfilename(
            title="选择 KiCad CLI 可执行文件",
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")],
        )
        if file_path:
            self.kicad_cli_path.set(file_path)

    def auto_detect_kicad_cli_on_startup(self):
        """启动时自动检测KiCad CLI路径（静默模式）"""
        detected_path = self.detect_kicad_cli()
        if detected_path:
            self.kicad_cli_path.set(detected_path)
            print(f"启动时自动检测到 KiCad CLI: {detected_path}")
        else:
            print("启动时未检测到 KiCad CLI，请手动指定路径")

    def auto_detect_kicad_cli(self):
        """自动检测KiCad CLI路径（显示消息框）"""
        detected_path = self.detect_kicad_cli()
        if detected_path:
            self.kicad_cli_path.set(detected_path)
            messagebox.showinfo("检测成功", f"已自动检测到 KiCad CLI:\n{detected_path}")
        else:
            messagebox.showwarning(
                "检测失败", "未找到 KiCad CLI\n请手动指定路径或安装 KiCad"
            )

    def run_kicad_export(self):
        # 验证输入
        if not self.kicad_project_file.get():
            messagebox.showerror("错误", "请选择 KiCad 项目文件")
            return

        if not os.path.isfile(self.kicad_project_file.get()):
            messagebox.showerror("错误", "项目文件不存在")
            return

        # 构建参数
        args = [self.kicad_project_file.get(), "--output", self.kicad_output_dir.get()]

        if self.kicad_cli_path.get():
            args.extend(["--kicad-cli", self.kicad_cli_path.get()])

        if self.kicad_skip_checks.get():
            args.append("--skip-checks")

        if self.kicad_skip_exports.get():
            args.append("--skip-exports")

        if self.kicad_export_mode.get():
            args.append("--export-mode")

        self.run_command(kicad_main, args, "KiCad导出")

    def run_command(self, main_func, args, operation_name):
        # 创建输出区域（如果不存在）
        if not hasattr(self, "output_text"):
            self.output_text = scrolledtext.ScrolledText(self.root, width=80, height=15)
            self.output_text.pack(fill="both", expand=True, padx=10, pady=10)

        # 清空输出
        self.output_text.delete(1.0, tk.END)

        # 运行命令，捕获输出
        try:
            # 重定向 stdout 和 stderr
            output_buffer = io.StringIO()
            with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(
                output_buffer
            ):
                result = main_func(args)

            output = output_buffer.getvalue()

            if result == 0:
                self.output_text.insert(tk.END, f"{operation_name}成功完成！\n\n")
            else:
                self.output_text.insert(
                    tk.END, f"{operation_name}失败，退出代码: {result}\n\n"
                )

            self.output_text.insert(tk.END, output)

        except Exception as e:
            self.output_text.insert(tk.END, f"运行时错误: {str(e)}\n")
            messagebox.showerror("错误", f"运行时错误: {str(e)}")


def main():
    root = tk.Tk()
    app = BOMTransformGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
