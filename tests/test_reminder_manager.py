# -*- coding: utf-8 -*-
"""纯函数单元测试：不依赖 Windows，可在任意平台跑。

    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import reminder_manager as rm  # noqa: E402


class TaskNameTests(unittest.TestCase):
    def test_colon_replaced(self):
        name, replaced = rm.normalize_task_name("10:30 提醒")
        self.assertEqual(name, "10：30 提醒")
        self.assertTrue(any(":" in r for r in replaced))

    def test_dotdot_replaced(self):
        name, replaced = rm.normalize_task_name("备份..完成")
        self.assertEqual(name, "备份．．完成")
        self.assertTrue(replaced)

    def test_trailing_dot(self):
        name, _ = rm.normalize_task_name("日报.")
        self.assertEqual(name, "日报．")

    def test_clean_name_untouched(self):
        name, replaced = rm.normalize_task_name("  打卡提醒  ")
        self.assertEqual(name, "打卡提醒")
        self.assertEqual(replaced, [])


class TimeTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(rm.normalize_time("9:5"), "09:05")
        self.assertEqual(rm.normalize_time("17：00"), "17:00")

    def test_invalid(self):
        self.assertIsNone(rm.normalize_time("25:00"))
        self.assertIsNone(rm.normalize_time("17点"))
        self.assertIsNone(rm.normalize_time(""))


class DateTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(rm.normalize_date("2026-12-01"), ("2026/12/01", "2026-12-01"))
        self.assertEqual(rm.normalize_date("2026/12/1"), ("2026/12/01", "2026-12-01"))
        self.assertEqual(rm.normalize_date("2026年12月1日"), ("2026/12/01", "2026-12-01"))

    def test_invalid(self):
        self.assertIsNone(rm.normalize_date("2026-13-01"))
        self.assertIsNone(rm.normalize_date("明天"))
        self.assertIsNone(rm.normalize_date(""))


class ValidateFormTests(unittest.TestCase):
    def test_missing_fields(self):
        values, error = rm.validate_form("", "标题", "内容", "每天", "17:00", [], "")
        self.assertIsNone(values)
        self.assertIn("不能为空", error)

    def test_emoji_rejected(self):
        values, error = rm.validate_form("打卡⏰", "标题", "内容", "每天", "17:00", [], "")
        self.assertIsNone(values)
        self.assertIn("emoji", error)

    def test_once_requires_date(self):
        values, error = rm.validate_form("提醒", "标题", "内容", "一次性", "17:00", [], "")
        self.assertIsNone(values)
        self.assertIn("日期", error)

    def test_weekly_requires_day(self):
        values, error = rm.validate_form("提醒", "标题", "内容", "每周", "17:00", [], "")
        self.assertIsNone(values)
        self.assertIn("星期", error)

    def test_once_ok(self):
        values, error = rm.validate_form("提醒", "标题", "内容", "一次性", "17:00", [],
                                         "2026-12-01")
        self.assertEqual(error, "")
        self.assertEqual(values["date_arg"], "2026/12/01")
        self.assertEqual(values["date"], "2026-12-01")

    def test_name_autofixed_in_values(self):
        values, error = rm.validate_form("A:B", "标题", "内容", "每天", "17:00", [], "")
        self.assertEqual(error, "")
        self.assertEqual(values["name"], "A：B")
        self.assertTrue(values["replaced"])


class TriggerTests(unittest.TestCase):
    def test_once(self):
        self.assertEqual(
            rm.build_trigger("一次性", "17:00", [], "2026/12/01"),
            ["-SC", "ONCE", "-SD", "2026/12/01", "-ST", "17:00", "-Z"])

    def test_weekly(self):
        self.assertEqual(
            rm.build_trigger("每周", "09:30", ["周一", "周三"]),
            ["-SC", "WEEKLY", "-D", "MON,WED", "-ST", "09:30"])

    def test_daily(self):
        self.assertEqual(rm.build_trigger("每天", "17:00", []),
                         ["-SC", "DAILY", "-ST", "17:00"])


ONCE_OUTPUT = """文件夹: \\
主机名:                             PC
任务名:                             \\Reminder_一键提醒
下次运行时间:                       2026/12/1 17:00:00
状态:                               就绪
要运行的任务:                       "C:\\Tools\\ClockReminder.exe" --title "⏰ 一次性" --text "开会" --button "知道了"
计划类型:                           只在 2026/12/01 运行一次
开始时间:                           17:00:00
开始日期:                           2026/12/01
结束日期:                           N/A
天:                                 N/A
"""

WEEKLY_OUTPUT = """文件夹: \\
任务名:                             \\Reminder_周报
要运行的任务:                       "C:\\Tools\\ClockReminder.exe" --title "📋 周报" --text "写周报" --button "去写"
计划类型:                           每周
开始时间:                           09:30:00
开始日期:                           2026/11/02
天:                                 MON，WED
下次运行时间:                       2026/12/02 09:30:00
"""

DAILY_OUTPUT = """文件夹: \\
任务名:                             \\Reminder_打卡
要运行的任务:                       "C:\\Tools\\ClockReminder.exe" --title "⏰ 打卡" --text "别忘了" --button "好"
计划类型:                           每天
开始时间:                           17:00:00
开始日期:                           2026/10/01
天:                                 每 1 天
下次运行时间:                       2026/11/24 17:00:00
"""


class ParseDetailTests(unittest.TestCase):
    def test_once_task(self):
        d = rm.parse_detail_output(ONCE_OUTPUT, rm.TASK_PREFIX + "一键提醒")
        self.assertEqual(d["name"], "一键提醒")
        self.assertEqual(d["schedule"], "一次性")
        self.assertEqual(d["date"], "2026-12-01")
        self.assertEqual(d["time"], "17:00")
        self.assertEqual(d["title"], "⏰ 一次性")

    def test_weekly_task(self):
        d = rm.parse_detail_output(WEEKLY_OUTPUT, rm.TASK_PREFIX + "周报")
        self.assertEqual(d["schedule"], "每周")
        self.assertEqual(d["weekdays"], ["周一", "周三"])
        self.assertEqual(d["title"], "📋 周报")

    def test_daily_task(self):
        d = rm.parse_detail_output(DAILY_OUTPUT, rm.TASK_PREFIX + "打卡")
        self.assertEqual(d["schedule"], "每天")
        self.assertEqual(d["weekdays"], [])


if __name__ == "__main__":
    unittest.main()
