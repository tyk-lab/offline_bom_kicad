#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOM 转换 GUI 工具

基于 bom_transform.py 脚本的图形界面版本。

功能：
- 选择输入 CSV 文件
- 选择输出目录
- 设置项目名称
- 可选选择映射配置文件
- 运行转换并显示结果
"""

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import sys
import io
import contextlib
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


class BOMTransformGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BOM 转换工具")
        self.root.geometry("600x500")

        # 变量
        self.input_file = tk.StringVar()
        self.output_dir = tk.StringVar(value=os.getcwd())
        self.project_name = tk.StringVar()
        self.mapping_file = tk.StringVar()
        self.quiet = tk.BooleanVar(value=False)

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        # 输入文件
        tk.Label(self.root, text="输入 CSV 文件:").grid(
            row=0, column=0, sticky="w", padx=10, pady=5
        )
        tk.Entry(self.root, textvariable=self.input_file, width=50).grid(
            row=0, column=1, padx=10, pady=5
        )
        tk.Button(self.root, text="浏览...", command=self.select_input_file).grid(
            row=0, column=2, padx=10, pady=5
        )

        # 输出目录
        tk.Label(self.root, text="输出目录:").grid(
            row=1, column=0, sticky="w", padx=10, pady=5
        )
        tk.Entry(self.root, textvariable=self.output_dir, width=50).grid(
            row=1, column=1, padx=10, pady=5
        )
        tk.Button(self.root, text="浏览...", command=self.select_output_dir).grid(
            row=1, column=2, padx=10, pady=5
        )

        # 项目名称
        tk.Label(self.root, text="项目名称 (可选):").grid(
            row=2, column=0, sticky="w", padx=10, pady=5
        )
        tk.Entry(self.root, textvariable=self.project_name, width=50).grid(
            row=2, column=1, padx=10, pady=5
        )

        # 映射文件
        tk.Label(self.root, text="映射配置文件 (可选):").grid(
            row=3, column=0, sticky="w", padx=10, pady=5
        )
        tk.Entry(self.root, textvariable=self.mapping_file, width=50).grid(
            row=3, column=1, padx=10, pady=5
        )
        tk.Button(self.root, text="浏览...", command=self.select_mapping_file).grid(
            row=3, column=2, padx=10, pady=5
        )

        # 选项
        tk.Checkbutton(
            self.root, text="静默模式 (不显示详细错误)", variable=self.quiet
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        # 运行按钮
        tk.Button(
            self.root,
            text="运行转换",
            command=self.run_transform,
            bg="green",
            fg="white",
        ).grid(row=5, column=0, columnspan=3, pady=10)

        # 输出区域
        tk.Label(self.root, text="输出:").grid(
            row=6, column=0, sticky="w", padx=10, pady=5
        )
        self.output_text = scrolledtext.ScrolledText(self.root, width=70, height=15)
        self.output_text.grid(row=7, column=0, columnspan=3, padx=10, pady=5)

    def select_input_file(self):
        file_path = filedialog.askopenfilename(
            title="选择输入 CSV 文件",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
        )
        if file_path:
            self.input_file.set(file_path)

    def select_output_dir(self):
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_dir.set(dir_path)

    def select_mapping_file(self):
        file_path = filedialog.askopenfilename(
            title="选择映射配置文件",
            filetypes=[("YAML 文件", "*.yml *.yaml"), ("所有文件", "*.*")],
        )
        if file_path:
            self.mapping_file.set(file_path)

    def run_transform(self):
        # 验证输入
        if not self.input_file.get():
            messagebox.showerror("错误", "请选择输入 CSV 文件")
            return

        if not os.path.isfile(self.input_file.get()):
            messagebox.showerror("错误", "输入文件不存在")
            return

        if not os.path.isdir(self.output_dir.get()):
            messagebox.showerror("错误", "输出目录不存在")
            return

        # 构建参数
        args = ["--input", self.input_file.get(), "--output-dir", self.output_dir.get()]

        if self.project_name.get():
            args.extend(["--project-name", self.project_name.get()])

        if self.mapping_file.get():
            args.extend(["--mapping", self.mapping_file.get()])

        if self.quiet.get():
            args.append("--quiet")

        # 清空输出
        self.output_text.delete(1.0, tk.END)

        # 运行转换，捕获输出
        try:
            # 重定向 stdout
            output_buffer = io.StringIO()
            with contextlib.redirect_stdout(output_buffer):
                with contextlib.redirect_stderr(output_buffer):
                    result = bom_main(args)

            output = output_buffer.getvalue()

            if result == 0:
                self.output_text.insert(tk.END, "转换成功完成！\n\n")
            else:
                self.output_text.insert(tk.END, f"转换失败，退出代码: {result}\n\n")

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
