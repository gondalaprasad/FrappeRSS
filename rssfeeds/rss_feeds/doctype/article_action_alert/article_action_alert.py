# Copyright (c) 2026, Prasad Gondala and contributors
# For license information, please see license.txt

import frappe
import datetime
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime, add_days, get_time

class ArticleActionAlert(Document):
    def validate(self):
        if self.status == "Active":
            if self.frequency == "Once":
                if not self.once_datetime:
                    frappe.throw("Please select a Schedule Date & Time for 'Once' frequency.")

                if get_datetime(self.once_datetime) < get_datetime(now_datetime()):
                    frappe.msgprint(
                        "Warning: The scheduled time is in the past. The alert may fire immediately.",
                        indicator="orange"
                    )

                # Copy into next_trigger_datetime so scheduler logic is unchanged
                self.next_trigger_datetime = self.once_datetime

            else:
                if not self.time_of_day:
                    frappe.throw("Please set a Time of Day for recurring alerts.")

                calculated = self.calculate_next_trigger()
                if not calculated:
                    frappe.throw(
                        "Could not calculate next trigger. For 'Specific Days', "
                        "please ensure at least one day is selected."
                    )
                self.next_trigger_datetime = calculated

    def calculate_next_trigger(self, from_datetime=None):
        """Calculate the next trigger datetime for recurring alerts."""
        base_dt = get_datetime(from_datetime or now_datetime())

        day_map = {
            0: self.monday,   1: self.tuesday,  2: self.wednesday,
            3: self.thursday, 4: self.friday,   5: self.saturday,
            6: self.sunday
        }

        if self.frequency == "Interval" and from_datetime:
            return add_days(base_dt, self.interval_days or 1)

        for i in range(366):
            check_date = add_days(base_dt.date(), i)
            t = get_time(self.time_of_day) if self.time_of_day else base_dt.time()
            check_dt = datetime.datetime.combine(check_date, t)

            if get_datetime(check_dt) <= get_datetime(now_datetime()):
                continue

            weekday = check_dt.weekday()

            if self.frequency == "Daily":
                return check_dt
            elif self.frequency == "Weekdays" and weekday < 5:
                return check_dt
            elif self.frequency == "Weekends" and weekday >= 5:
                return check_dt
            elif self.frequency == "Specific Days" and day_map.get(weekday):
                return check_dt
            elif self.frequency == "Interval":
                return check_dt

        return None