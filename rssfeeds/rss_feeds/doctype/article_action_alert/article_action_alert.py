# Copyright (c) 2026, Prasad Gondala and contributors
# For license information, please see license.txt

# Copyright (c) 2026, Prasad Gondala and contributors

# For license information, please see license.txt



import frappe

from frappe.model.document import Document

from frappe.utils import now_datetime, get_datetime, add_days, get_time



class ArticleActionAlert(Document):

    def validate(self):

        """Runs automatically right before you click 'Save'."""

        if self.status == "Active":

            self.next_trigger_datetime = self.calculate_next_trigger()



    def calculate_next_trigger(self, from_datetime=None):

        """Calculates the exact next date/time this alert should fire."""

        now_dt = from_datetime or now_datetime()

        current_date = now_dt.date()

       

        # Ensure time_of_day is treated as a string (e.g. "09:00:00")

        target_time = str(self.time_of_day)



        # Map Python's weekday index (0=Monday, 6=Sunday) to your checkboxes

        day_map = {

            0: self.monday, 1: self.tuesday, 2: self.wednesday,

            3: self.thursday, 4: self.friday, 5: self.saturday, 6: self.sunday

        }



        # Handle Interval specifically for recurring triggers

        if self.frequency == "Interval" and from_datetime:

            next_date = add_days(current_date, self.interval_days)

            return get_datetime(f"{next_date} {target_time}")



        # Scan the next 365 days to find the first day that matches your rules

        for i in range(365):

            check_date = add_days(current_date, i)

            check_dt = get_datetime(f"{check_date} {target_time}")



            # The scheduled time MUST be in the future

            if check_dt <= now_datetime():

                continue



            weekday = check_dt.weekday()



            if self.frequency in ["Once", "Daily"]:

                return check_dt

            elif self.frequency == "Weekdays" and weekday < 5:

                return check_dt

            elif self.frequency == "Weekends" and weekday >= 5:

                return check_dt

            elif self.frequency == "Specific Days" and day_map.get(weekday):

                return check_dt

            elif self.frequency == "Interval":

                return check_dt # For the very first time it is set



        return None
