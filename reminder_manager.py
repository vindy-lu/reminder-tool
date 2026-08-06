# -*- coding: utf-8 -*-
"""
提醒弹窗管理工具（可视化 v3）
- 图形界面：填写参数 -> 添加/编辑/删除计划任务
- 列表显示任务详情（标题、内容、时间、计划）
- 双击任务 -> 独立编辑对话框，确定后以新内容重建
- 底层调用 Windows 任务计划程序 (schtasks)
- 需要与 clock_reminder.py 放在同一目录
"""
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

PYTHON = sys.executable
# 程序所在目录：
# - 源码运行：脚本所在目录（用 __file__）
# - PyInstaller 打包后：exe 所在目录（用 sys.executable，__file__ 指向临时解压目录）
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_PREFIX = "Reminder_"  # 本工具管理的任务名前缀

# 弹窗脚本：优先用打包后的 exe，否则用源码 py（兼容两种运行方式）
SCRIPT_EXE = os.path.join(BASE_DIR, "ClockReminder.exe")
SCRIPT_PY = os.path.join(BASE_DIR, "clock_reminder.py")
SCRIPT = SCRIPT_EXE if os.path.exists(SCRIPT_EXE) else SCRIPT_PY


def script_invocation():
    """返回执行弹窗脚本的命令前缀（列表形式）"""
    if SCRIPT.endswith(".exe"):
        return [SCRIPT]
    return [PYTHON, SCRIPT]

WEEKDAY_MAP = {
    "周一": "MON", "周二": "TUE", "周三": "WED", "周四": "THU",
    "周五": "FRI", "周六": "SAT", "周日": "SUN",
}
WEEKDAY_CN = {v: k for k, v in WEEKDAY_MAP.items()}


def run_cmd(args):
    """执行命令，返回 (成功?, 输出)。schtasks 输出是 GBK，需按系统编码解码"""
    try:
        proc = subprocess.run(
            args, capture_output=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        enc = "cp936" if os.name == "nt" else "utf-8"
        out = (proc.stdout or b"").decode(enc, errors="replace")
        err = (proc.stderr or b"").decode(enc, errors="replace")
        return proc.returncode == 0, out + err
    except Exception as e:
        return False, str(e)


def parse_task_detail(full_name):
    """查询单个任务详情，返回 dict 或 None。
    dict: name(显示名), title, text, button, schedule(每天/每周), time, weekdays, next_run
    """
    ok, out = run_cmd(["schtasks", "-Query", "-TN", full_name, "-V", "-FO", "LIST"])
    if not ok:
        return None
    detail = {"name": full_name[len(TASK_PREFIX):], "title": "", "text": "",
              "button": "", "schedule": "每天", "time": "", "weekdays": [],
              "next_run": ""}

    # 要运行的任务 -> 提取 --title/--text/--button
    m = re.search(r"要运行的任务:\s*([^\r\n]+)", out)
    if m:
        cmdline = m.group(1).strip()
        for key in ("--title", "--text", "--button"):
            mm = re.search(re.escape(key) + r'\s+"([^"]*)"', cmdline)
            if mm:
                detail[key[2:]] = mm.group(1)

    # 计划类型 / 开始时间 / 天
    m = re.search(r"计划类型:\s*([^\r\n]+)", out)
    if m:
        stype = m.group(1).strip()
        detail["schedule"] = "每周" if "周" in stype else "每天"
    m = re.search(r"开始时间:\s*([^\r\n]+)", out)
    if m:
        t = m.group(1).strip()
        # 9:30:00 / 17:00:00 -> 09:30 / 17:00
        parts = t.split(":")
        detail["time"] = f"{int(parts[0]):02d}:{int(parts[1]):02d}" if len(parts) >= 2 else t
    m = re.search(r"天:\s*([^\r\n]+)", out)
    if m:
        days = m.group(1).strip()
        # 天字段可能是 "MON，TUE，WED"（全角逗号）或 "每 1 天"（每天任务）
        for en, cn in WEEKDAY_CN.items():
            if en in days.upper():
                detail["weekdays"].append(cn)

    # 下次运行时间
    m = re.search(r"下次运行时间:\s*([^\r\n]+)", out)
    if m:
        detail["next_run"] = m.group(1).strip()
    return detail


def list_tasks():
    """列出所有 Reminder_ 前缀任务，返回详情 dict 列表"""
    ok, out = run_cmd(["schtasks", "-Query", "-FO", "CSV"])
    if not ok:
        return []
    tasks = []
    for line in out.splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        full_name = parts[0].strip().strip('"').lstrip("\\")
        if full_name.startswith(TASK_PREFIX):
            tasks.append(full_name)
    # 逐个查详情（任务量不大，可接受）
    return [parse_task_detail(t) for t in tasks if parse_task_detail(t)]


def build_trigger(schedule_type, time_str, weekdays):
    """构造 schtasks 的触发参数"""
    if schedule_type == "每周":
        days = ",".join(WEEKDAY_MAP[d] for d in weekdays)
        return ["-SC", "WEEKLY", "-D", days, "-ST", time_str]
    return ["-SC", "DAILY", "-ST", time_str]


def add_task(name, title, text, button, schedule_type, time_str, weekdays):
    """添加任务"""
    task_name = TASK_PREFIX + name
    # 用 script_invocation() 拼命令行：exe 直接调用，py 用 python 解释器
    inv = script_invocation()
    cmd_str = " ".join(f'"{p}"' for p in inv)
    cmd = ["schtasks", "-Create", "-TN", task_name, "-F",
           "-TR",
           f'{cmd_str} --title "{title}" --text "{text}" --button "{button}"']
    cmd += build_trigger(schedule_type, time_str, weekdays)
    return run_cmd(cmd)


def delete_task(task_name):
    return run_cmd(["schtasks", "-Delete", "-TN", task_name, "-F"])


def compress_weekdays(days):
    """把星期列表压缩显示：['周一','周二','周三','周四','周五'] -> '周一-周五'"""
    order = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    idxs = sorted(order.index(d) for d in days if d in order)
    if not idxs:
        return ",".join(days)
    groups = []
    start = prev = idxs[0]
    for i in idxs[1:]:
        if i == prev + 1:
            prev = i
        else:
            groups.append((start, prev))
            start = prev = i
    groups.append((start, prev))
    parts = []
    for s, e in groups:
        parts.append(order[s] if s == e else f"{order[s]}-{order[e]}")
    return ",".join(parts)


class EditDialog:
    """编辑任务对话框：直接修改所有参数，确定后删旧建新"""

    def __init__(self, parent, detail, on_save):
        self.parent = parent
        self.on_save = on_save
        self.old_name = detail["name"]

        self.dlg = tk.Toplevel(parent)
        self.dlg.title(f"编辑任务 - {detail['name']}")
        self.dlg.geometry("520x420")
        self.dlg.resizable(False, False)
        self.dlg.grab_set()  # 模态
        self.dlg.attributes("-topmost", True)

        pad = 14
        body = tk.Frame(self.dlg, padx=pad, pady=10)
        body.pack(fill="both", expand=True)

        self.var_name = tk.StringVar(value=detail["name"])
        self.var_title = tk.StringVar(value=detail["title"])
        self.var_text = tk.StringVar(value=detail["text"])
        self.var_button = tk.StringVar(value=detail["button"])
        self.var_schedule = tk.StringVar(value=detail["schedule"])
        self.var_time = tk.StringVar(value=detail["time"])
        self.var_weekdays = {d: tk.BooleanVar(value=d in detail["weekdays"])
                             for d in WEEKDAY_MAP}

        def row(r, label, widget):
            tk.Label(body, text=label, font=("Microsoft YaHei", 10),
                     width=8, anchor="e").grid(row=r, column=0, sticky="e", padx=(0, 8), pady=4)
            widget.grid(row=r, column=1, sticky="w", pady=4)

        row(0, "任务名", tk.Entry(body, textvariable=self.var_name, width=32, font=("Microsoft YaHei", 10)))
        row(1, "弹窗标题", tk.Entry(body, textvariable=self.var_title, width=42, font=("Microsoft YaHei", 10)))
        row(2, "弹窗内容", tk.Entry(body, textvariable=self.var_text, width=56, font=("Microsoft YaHei", 10)))
        row(3, "按钮文字", tk.Entry(body, textvariable=self.var_button, width=20, font=("Microsoft YaHei", 10)))

        freq_frame = tk.Frame(body)
        freq_frame.grid(row=4, column=1, sticky="w", pady=4)
        self.sched_combo = ttk.Combobox(freq_frame, textvariable=self.var_schedule,
                                        values=["每天", "每周"], width=6,
                                        state="readonly", font=("Microsoft YaHei", 10))
        self.sched_combo.pack(side="left")
        self.sched_combo.bind("<<ComboboxSelected>>", self.on_schedule_change)
        tk.Label(freq_frame, text="时间", font=("Microsoft YaHei", 10)).pack(side="left", padx=(10, 4))
        tk.Entry(freq_frame, textvariable=self.var_time, width=7, font=("Microsoft YaHei", 10)).pack(side="left")

        week_frame = tk.Frame(body)
        week_frame.grid(row=5, column=1, sticky="w", pady=4)
        self.week_checks = []
        for d, var in self.var_weekdays.items():
            cb = tk.Checkbutton(week_frame, text=d, variable=var,
                                font=("Microsoft YaHei", 9))
            cb.pack(side="left")
            self.week_checks.append(cb)
        self.on_schedule_change()  # 初始化置灰状态

        hint = tk.Label(body, text="提示：任务名不支持 emoji，emoji 可放标题/内容",
                        font=("Microsoft YaHei", 9), fg="gray")
        hint.grid(row=6, column=0, columnspan=2, pady=(6, 0))

        btn_row = tk.Frame(self.dlg, padx=pad, pady=12)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="✅ 确定保存", command=self.save,
                  font=("Microsoft YaHei", 11), bg="#2563eb", fg="white",
                  padx=24, pady=5).pack(side="left")
        tk.Button(btn_row, text="▶️ 测试弹窗", command=self.test,
                  font=("Microsoft YaHei", 10), padx=14).pack(side="left", padx=8)
        tk.Button(btn_row, text="取消", command=self.dlg.destroy,
                  font=("Microsoft YaHei", 10)).pack(side="right")

    def on_schedule_change(self, event=None):
        """频率切换联动：每天时星期勾选置灰，每周时启用"""
        state = "normal" if self.var_schedule.get() == "每周" else "disabled"
        for cb in self.week_checks:
            cb.config(state=state)

    def collect(self):
        name = self.var_name.get().strip()
        title = self.var_title.get().strip()
        text = self.var_text.get().strip()
        button = self.var_button.get().strip()
        time_str = self.var_time.get().strip()
        if not name or not title or not text:
            messagebox.showwarning("提示", "任务名、标题、内容不能为空", parent=self.dlg)
            return None
        if re.search(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", name):
            messagebox.showwarning("提示", "任务名不支持 emoji，请使用中文/英文/数字",
                                   parent=self.dlg)
            return None
        weekdays = [d for d, var in self.var_weekdays.items() if var.get()]
        if self.var_schedule.get() == "每周" and not weekdays:
            messagebox.showwarning("提示", "请至少勾选一个星期几", parent=self.dlg)
            return None
        return dict(name=name, title=title, text=text, button=button,
                    schedule=self.var_schedule.get(), time=time_str, weekdays=weekdays)

    def test(self):
        d = self.collect()
        if d:
            subprocess.Popen(
                script_invocation() + ["--title", d["title"], "--text", d["text"],
                                       "--button", d["button"]],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

    def save(self):
        d = self.collect()
        if not d:
            return
        # 删旧任务（名字可能变了也要删原来的）
        if self.old_name != d["name"]:
            delete_task(TASK_PREFIX + self.old_name)
        ok, out = add_task(d["name"], d["title"], d["text"], d["button"],
                           d["schedule"], d["time"], d["weekdays"])
        if ok:
            messagebox.showinfo("成功", f"任务 [{d['name']}] 已保存", parent=self.dlg)
            self.dlg.destroy()
            self.on_save()
        else:
            messagebox.showerror("失败", out, parent=self.dlg)


class ReminderManager:
    def __init__(self, root):
        self.root = root
        root.title("提醒弹窗管理工具")
        root.geometry("860x600")
        root.resizable(False, False)

        # ============ 上半区：任务列表 ============
        top = tk.LabelFrame(root, text="已添加的提醒任务（双击行可编辑）",
                            font=("Microsoft YaHei", 11), padx=10, pady=6)
        top.pack(fill="both", expand=True, padx=12, pady=(12, 4))

        cols = ("name", "title", "text", "next_run", "schedule")
        self.tree = ttk.Treeview(top, columns=cols, show="headings", height=9)
        headers = [("name", "任务名", 130), ("title", "弹窗标题", 140),
                   ("text", "内容", 260), ("next_run", "下次运行", 150),
                   ("schedule", "计划", 90)]
        for key, text, width in headers:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.on_double_click)

        btn_row = tk.Frame(top)
        btn_row.pack(fill="x", pady=(6, 0))
        tk.Button(btn_row, text="🔄 刷新列表", command=self.refresh,
                  font=("Microsoft YaHei", 10)).pack(side="left")
        tk.Button(btn_row, text="✏️ 编辑选中任务", command=self.edit_selected,
                  font=("Microsoft YaHei", 10)).pack(side="left", padx=8)
        tk.Button(btn_row, text="🗑️ 删除选中任务", command=self.del_selected,
                  font=("Microsoft YaHei", 10), fg="red").pack(side="left", padx=8)

        # ============ 下半区：添加任务表单 ============
        bottom = tk.LabelFrame(root, text="添加新提醒", font=("Microsoft YaHei", 11), padx=12, pady=8)
        bottom.pack(fill="x", padx=12, pady=(8, 12))

        self.var_name = tk.StringVar()
        self.var_title = tk.StringVar(value="⏰ 打卡提醒")
        self.var_text = tk.StringVar(value="老刘，时间到了！别忘了打卡！")
        self.var_button = tk.StringVar(value="我知道了")
        self.var_schedule = tk.StringVar(value="每天")
        self.var_time = tk.StringVar(value="17:00")
        self.var_weekdays = {d: tk.BooleanVar() for d in WEEKDAY_MAP}

        grid = tk.Frame(bottom)
        grid.pack(fill="x")

        def row(r, label, widget):
            tk.Label(grid, text=label, font=("Microsoft YaHei", 10),
                     width=8, anchor="e").grid(row=r, column=0, sticky="e", padx=(0, 6), pady=3)
            widget.grid(row=r, column=1, sticky="w", pady=3)

        row(0, "任务名", tk.Entry(grid, textvariable=self.var_name, width=30, font=("Microsoft YaHei", 10)))
        row(1, "弹窗标题", tk.Entry(grid, textvariable=self.var_title, width=40, font=("Microsoft YaHei", 10)))
        row(2, "弹窗内容", tk.Entry(grid, textvariable=self.var_text, width=55, font=("Microsoft YaHei", 10)))
        row(3, "按钮文字", tk.Entry(grid, textvariable=self.var_button, width=20, font=("Microsoft YaHei", 10)))

        freq_frame = tk.Frame(grid)
        freq_frame.grid(row=4, column=1, sticky="w", pady=3)
        self.sched_combo = ttk.Combobox(freq_frame, textvariable=self.var_schedule,
                                        values=["每天", "每周"], width=6,
                                        state="readonly", font=("Microsoft YaHei", 10))
        self.sched_combo.pack(side="left")
        self.sched_combo.bind("<<ComboboxSelected>>", self.on_schedule_change)
        tk.Label(freq_frame, text="时间", font=("Microsoft YaHei", 10)).pack(side="left", padx=(10, 4))
        tk.Entry(freq_frame, textvariable=self.var_time, width=7, font=("Microsoft YaHei", 10)).pack(side="left")
        tk.Label(freq_frame, text="(格式 17:00)", font=("Microsoft YaHei", 9), fg="gray").pack(side="left", padx=6)

        week_frame = tk.Frame(grid)
        week_frame.grid(row=5, column=1, sticky="w", pady=3)
        self.week_checks = []
        for d, var in self.var_weekdays.items():
            cb = tk.Checkbutton(week_frame, text=d, variable=var,
                                font=("Microsoft YaHei", 9))
            cb.pack(side="left")
            self.week_checks.append(cb)
        self.on_schedule_change()  # 默认"每天"，星期置灰

        action = tk.Frame(bottom)
        action.pack(fill="x", pady=(10, 0))
        tk.Button(action, text="✅ 确定添加", command=self.add,
                  font=("Microsoft YaHei", 11), bg="#2563eb", fg="white",
                  padx=30, pady=6).pack(side="left")
        tk.Button(action, text="▶️ 立即测试弹窗", command=self.test_popup,
                  font=("Microsoft YaHei", 10), padx=16).pack(side="left", padx=10)

        self.refresh()

    # ---------- 功能 ----------
    def on_schedule_change(self, event=None):
        """频率切换联动：每天时星期勾选置灰，每周时启用"""
        state = "normal" if self.var_schedule.get() == "每周" else "disabled"
        for cb in self.week_checks:
            cb.config(state=state)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for d in list_tasks():
            if d["schedule"] == "每周" and d["weekdays"]:
                # 压缩显示：周一,周二,周三,周四,周五 -> 周一-周五
                plan = "每周 " + compress_weekdays(d["weekdays"])
            else:
                plan = "每天"
            self.tree.insert("", "end", values=(
                d["name"], d["title"], d["text"],
                d["next_run"], plan,
            ), tags=("full:" + TASK_PREFIX + d["name"],))

    def get_selected_fullname(self):
        sel = self.tree.selection()
        if not sel:
            return None
        for t in self.tree.item(sel[0]).get("tags", ()):
            if t.startswith("full:"):
                return t[5:]
        return None

    def del_selected(self):
        full_name = self.get_selected_fullname()
        if full_name is None:
            messagebox.showwarning("提示", "请先选中要删除的任务")
            return
        if not messagebox.askyesno("确认", f"确定删除任务 [{full_name}] 吗？"):
            return
        ok, out = delete_task(full_name)
        if ok:
            messagebox.showinfo("成功", f"任务 [{full_name}] 已删除")
            self.refresh()
        else:
            messagebox.showerror("失败", out)

    def on_double_click(self, event):
        self.edit_selected()

    def edit_selected(self):
        full_name = self.get_selected_fullname()
        if full_name is None:
            messagebox.showwarning("提示", "请先选中要编辑的任务")
            return
        detail = parse_task_detail(full_name)
        if detail is None:
            messagebox.showerror("查询失败", "无法读取任务详情")
            return
        EditDialog(self.root, detail, on_save=self.refresh)

    def add(self):
        name = self.var_name.get().strip()
        title = self.var_title.get().strip()
        text = self.var_text.get().strip()
        button = self.var_button.get().strip()
        time_str = self.var_time.get().strip()
        if not name or not title or not text:
            messagebox.showwarning("提示", "任务名、标题、内容不能为空")
            return
        if re.search(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", name):
            messagebox.showwarning("提示",
                                   "任务名不支持 emoji 图标，请使用中文/英文/数字。\n"
                                   "emoji 可以放在弹窗标题或内容里。")
            return
        weekdays = [d for d, var in self.var_weekdays.items() if var.get()]
        if self.var_schedule.get() == "每周" and not weekdays:
            messagebox.showwarning("提示", "请至少勾选一个星期几")
            return
        ok, out = add_task(name, title, text, button,
                           self.var_schedule.get(), time_str, weekdays)
        if ok:
            messagebox.showinfo("成功", f"任务 [{TASK_PREFIX}{name}] 已添加")
            self.var_name.set("")
            self.refresh()
        else:
            messagebox.showerror("失败", out)

    def test_popup(self):
        title = self.var_title.get().strip() or "测试弹窗"
        text = self.var_text.get().strip() or "测试内容"
        button = self.var_button.get().strip() or "关闭"
        subprocess.Popen(
            script_invocation() + ["--title", title, "--text", text, "--button", button],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )


if __name__ == "__main__":
    root = tk.Tk()
    ReminderManager(root)
    root.mainloop()
