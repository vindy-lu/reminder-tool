# -*- coding: utf-8 -*-
"""在真实 Windows 上跑一遍端到端：建一次性任务 -> 查询 -> 自删。"""
import sys

sys.path.insert(0, r"C:\Users\Administrator\reminder-test")
import reminder_manager as rm  # noqa: E402
import clock_reminder  # noqa: E402

values, error = rm.validate_form(
    "测试:一次性", "一次性测试", "这是一次性提醒", "一次性", "09:00", [], "2026-12-01")
print("validate_error =", repr(error))
print("sanitized_name =", values["name"])
print("date_arg =", values["date_arg"])

ok, out = rm.add_task(values["name"], values["title"], values["text"], "好",
                      values["schedule"], values["time"], values["weekdays"],
                      values["date_arg"])
print("add_ok =", ok)
print("add_out =", out.strip().replace("\r\n", " | ")[:300])

tasks = rm.list_tasks()
print("total_tasks =", len(tasks))
hit = [t for t in tasks if t["name"] == values["name"]]
print("found =", len(hit))
if hit:
    t = hit[0]
    print("parsed_schedule =", t["schedule"])
    print("parsed_date =", t["date"])
    print("parsed_time =", t["time"])
    print("parsed_title =", t["title"])

# 模拟弹窗关闭后的自动删除
clock_reminder.delete_task(rm.TASK_PREFIX + values["name"])
print("after_delete =", [t["name"] for t in rm.list_tasks()])

# 顺带验证「每天」任务不带 --delete-task
ok2, out2 = rm.add_task("日常测试", "每天测试", "内容", "好", "每天", "09:30", [])
print("daily_add_ok =", ok2)
print("daily_tr =", [t for t in rm.list_tasks() if t["name"] == "日常测试"][:1])
clock_reminder.delete_task(rm.TASK_PREFIX + "日常测试")
print("final_tasks =", [t["name"] for t in rm.list_tasks()])
