# -*- coding: utf-8 -*-
"""
打卡/任务提醒弹窗（参数化版）
- 置顶显示，必须手动点按钮关闭（防错过）
- 支持命令行参数，一个脚本可被多个计划任务复用
- 用法示例：
    python clock_reminder.py --title "⏰ 打卡提醒" --text "17点到了，别忘了打卡！" --button "我知道了"
    python clock_reminder.py --title "📋 日报提醒" --text "下班前记得提交日报" --button "去写日报"
"""
import argparse
import subprocess
import tkinter as tk

# ========== 默认内容（不带参数时的兜底，改这里也行） ==========
DEFAULT_TITLE = "⏰ 打卡提醒"
DEFAULT_TEXT = (
    "老刘，17:00 到了！\n\n"
    "别忘了打卡！\n"
    "全勤奖在向你招手 😎"
)
DEFAULT_BUTTON = "我知道了，去打卡"
# ============================================================


def delete_task(task_name):
    """弹窗关掉后删除自己的计划任务（一次性提醒用）。

    schtasks 的 /Z 只在部分计划类型上可用，/SC ONCE 直接带 /Z 会报
    "任务 XML 缺少个所需元素或属性 (EndBoundary)"，所以改由弹窗脚本
    自己删——这样各版本 Windows 都稳。
    """
    if not task_name:
        return
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            capture_output=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass  # 删除失败不影响已经弹过的提醒


def show_reminder(title, text, button_text):
    root = tk.Tk()
    root.title(title)

    # 窗口置顶 + 固定尺寸
    root.attributes("-topmost", True)
    root.resizable(False, False)

    # 居中
    w, h = 420, 240
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    x, y = (sw - w) // 2, (sh - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    # 提示图标区
    tk.Label(root, text="⏰", font=("Segoe UI Emoji", 48)).pack(pady=(24, 8))

    # 提醒内容
    tk.Label(
        root, text=text, font=("Microsoft YaHei", 13),
        justify="center", wraplength=360
    ).pack(pady=(0, 16))

    # 必须手动点击的关闭按钮
    tk.Button(
        root, text=button_text, font=("Microsoft YaHei", 12),
        bg="#2563eb", fg="white", activebackground="#1d4ed8",
        activeforeground="white", padx=24, pady=8,
        command=root.destroy
    ).pack(pady=(0, 20))

    root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="任务提醒弹窗")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="弹窗标题")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="提醒内容，\\n 换行")
    parser.add_argument("--button", default=DEFAULT_BUTTON, help="按钮文字")
    parser.add_argument("--delete-task", dest="delete_task", default="",
                        help="弹窗关闭后删除的计划任务全名（一次性提醒用）")
    args = parser.parse_args()
    show_reminder(args.title, args.text, args.button)
    delete_task(args.delete_task)
