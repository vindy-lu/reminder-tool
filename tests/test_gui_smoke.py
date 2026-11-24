# -*- coding: utf-8 -*-
"""GUI 冒烟测试：在虚拟显示（xvfb-run）里把窗口真建出来，验证控件与联动。

    xvfb-run -a python -m unittest tests.test_gui_smoke -v

不打桩 schtasks 会失败，所以这里把 run_cmd 换成返回样例文本。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import reminder_manager as rm  # noqa: E402

SAMPLE = """文件夹: \\
任务名:                             \\Reminder_一键
要运行的任务:                       "C:\\Tools\\ClockReminder.exe" --title "提醒" --text "内容" --button "好"
计划类型:                           只在 2026/12/01 运行一次
开始时间:                           17:00:00
开始日期:                           2026/12/01
天:                                 N/A
下次运行时间:                       2026/12/1 17:00:00
"""


def fake_run_cmd(args):
    if "-TN" in args:
        return True, SAMPLE
    return True, '任务名,下次运行时间,状态\n"\\Reminder_一键","2026/12/1 17:00:00","就绪"\n'


class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        cls.rm = rm
        cls._orig_run_cmd = rm.run_cmd
        rm.run_cmd = fake_run_cmd
        cls.tk = tk
        try:
            cls.root = tk.Tk()
        except Exception as exc:  # 没有显示环境时跳过
            raise unittest.SkipTest("no display: %s" % exc)

    @classmethod
    def tearDownClass(cls):
        cls.rm.run_cmd = cls._orig_run_cmd
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_main_window_builds(self):
        app = rm.ReminderManager(self.root)
        self.assertIn("一次性", rm.SCHEDULE_TYPES)
        self.assertEqual(tuple(app.sched_combo.cget("values")), tuple(rm.SCHEDULE_TYPES))
        # 默认"每天"：星期与日期都应置灰
        self.assertEqual(str(app.date_entry.cget("state")), "disabled")
        # 切到一次性：日期可用、星期仍置灰
        app.var_schedule.set("一次性")
        app.on_schedule_change()
        self.assertEqual(str(app.date_entry.cget("state")), "normal")
        self.assertTrue(app.var_date.get())
        # 切到每周：星期可用、日期置灰
        app.var_schedule.set("每周")
        app.on_schedule_change()
        self.assertEqual(str(app.date_entry.cget("state")), "disabled")
        self.assertEqual(str(app.week_checks[0].cget("state")), "normal")
        # 列表渲染不抛异常
        app.refresh()
        self.assertEqual(len(app.tree.get_children()), 1)

    def test_edit_dialog_builds(self):
        detail = rm.parse_detail_output(SAMPLE, rm.TASK_PREFIX + "一键")
        dlg = rm.EditDialog(self.root, detail, on_save=lambda: None)
        self.assertEqual(dlg.var_schedule.get(), "一次性")
        self.assertEqual(str(dlg.date_entry.cget("state")), "normal")
        self.assertEqual(dlg.var_date.get(), "2026-12-01")
        dlg.dlg.destroy()


if __name__ == "__main__":
    unittest.main()
