import json
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from datetime import datetime, timedelta, date
from tkcalendar import DateEntry
import os
from typing import Dict, List
import math
from isoweek import Week

class JSONProcessorApp:
    REQUIRED_FILES = ['accounts.json', 'products.json', 'KPIs.json']
    
    def __init__(self, root):
        self.root = root
        self.root.title("JSON Processor")
        self.root.geometry("400x450")
        
        # Store loaded JSON data
        self.json_data = {file: None for file in self.REQUIRED_FILES}
        
        self.create_ui()
        
    def create_ui(self):
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        instructions = "Select a folder containing:\n" + "\n".join(self.REQUIRED_FILES)
        tk.Label(main_frame, text=instructions, justify=tk.LEFT).pack(anchor='w', pady=(0, 20))
        
        # Folder selection
        select_button = tk.Button(
            main_frame,
            text="Select Folder",
            command=self.select_folder,
            width=20
        )
        select_button.pack(pady=10)
        
        # Status frame
        self.status_frame = tk.Frame(main_frame)
        self.status_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        self.status_labels = {}
        for file in self.REQUIRED_FILES:
            frame = tk.Frame(self.status_frame)
            frame.pack(fill=tk.X, pady=2)
            
            tk.Label(frame, text=file, width=15, anchor='w').pack(side=tk.LEFT)
            status_label = tk.Label(frame, text="Not loaded", fg="red")
            status_label.pack(side=tk.LEFT, padx=10)
            self.status_labels[file] = status_label

        # Input frame for dates and salesorg
        input_frame = tk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=10)

        # Date selection
        date_frame = tk.Frame(input_frame)
        date_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(date_frame, text="Start Date:").pack(side=tk.LEFT, padx=5)
        self.start_date = DateEntry(date_frame, width=12, background='darkblue', foreground='white')
        self.start_date.pack(side=tk.LEFT, padx=5)
        start_date, end_date = self.get_year_dates()
        self.start_date.set_date(start_date)

        tk.Label(date_frame, text="End Date:").pack(side=tk.LEFT, padx=5)
        self.end_date = DateEntry(date_frame, width=12, background='darkblue', foreground='white')
        self.end_date.pack(side=tk.LEFT, padx=5)
        self.end_date.set_date(end_date)

        # Sales Org input
        salesorg_frame = tk.Frame(input_frame)
        salesorg_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(salesorg_frame, text="Sales Org:").pack(side=tk.LEFT, padx=5)
        self.salesorg_entry = tk.Entry(salesorg_frame, width=10)
        self.salesorg_entry.pack(side=tk.LEFT, padx=5)
        self.salesorg_entry.insert(0, "0000")
        
        # Process button
        self.process_button = tk.Button(
            main_frame,
            text="Process Files",
            command=self.process_files,
            state=tk.DISABLED
        )
        self.process_button.pack(pady=10)

    def get_year_dates(self):
        current_year = datetime.now().year
        return date(current_year, 1, 1), date(current_year, 12, 31)

    def get_period_index(self, start_date: date, current_date: date, granularity: str) -> int:
        if granularity == 'D':
            return (current_date - start_date).days
        else:  # 'W'
            start_week = Week.withdate(start_date)
            current_week = Week.withdate(current_date)
            return (current_week.week - start_week.week) + \
                   (current_week.year - start_week.year) * 52

    def calculate_kpi_value(self, formula: str, period: int, product: dict, account: dict) -> float:
        # Extract the calculation part after '=' in the formula
        calculation = formula.strip()
        
        # Replace variables with values
        calculation = calculation.replace('periodIndex', str(period))
        calculation = calculation.replace('initialValue', str(product['initialValue']))
        
        # Replace product custom values if they exist
        for i in range(1, 4):
            key = f'prdCustomValue{i}'
            if key in product:
                calculation = calculation.replace(f'prdCustomValue{i}', str(product[key]))
        
        # Replace account custom values if they exist
        for i in range(1, 4):
            key = f'accCustomValue{i}'
            if key in account:
                calculation = calculation.replace(f'accCustomValue{i}', str(account[key]))
        
        # Evaluate the expression
        try:
            return eval(calculation)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to evaluate formula: {formula}\nError: {str(e)}")
            return 0                        

    def generate_date_range(self, start_date: date, end_date: date, granularity: str) -> List[date]:
        dates = []
        current = start_date
        
        if granularity == 'W':
            # Adjust to start of week
            current = Week.withdate(current).monday()
            end = Week.withdate(end_date).monday()
            
            while current <= end:
                dates.append(current)
                current += timedelta(days=7)
        else:  # 'D'
            while current <= end_date:
                dates.append(current)
                current += timedelta(days=1)
                
        return dates

    def process_files(self):
        try:
            start_date = self.start_date.get_date()
            end_date = self.end_date.get_date()
            salesorg = self.salesorg_entry.get()

            # Create output directory
            output_dir = filedialog.askdirectory(title="Select Output Directory")
            if not output_dir:
                return

            accounts = self.json_data['accounts.json']['accounts']
            products = self.json_data['products.json']['products']
            kpis = self.json_data['KPIs.json']['measures']

            # Group KPIs by granularity and format
            kpi_groups = {
                'a': [],  # W + I
                'b': [],  # W + D
                'c': [],  # D + I
                'd': []   # D + D
            }

            for kpi in kpis:
                key = 'a' if kpi['timeGranularity'] == 'W' and kpi['format'] == 'I' else \
                      'b' if kpi['timeGranularity'] == 'W' and kpi['format'] == 'D' else \
                      'c' if kpi['timeGranularity'] == 'D' and kpi['format'] == 'I' else \
                      'd'
                kpi_groups[key].append(kpi)

            # Process each KPI group
            for group_key, group_kpis in kpi_groups.items():
                if not group_kpis:
                    continue

                granularity = group_kpis[0]['timeGranularity']
                is_decimal = group_kpis[0]['format'] == 'D'
                
                dates = self.generate_date_range(start_date, end_date, granularity)

                # Process each KPI in the group
                for kpi in group_kpis:
                    output_data = {
                        "type": kpi['measureCode'],
                        "salesorg": salesorg,
                        "volumes": []
                    }

                    for current_date in dates:
                        period_data = {
                            "startdate": current_date.isoformat(),
                            "rows": []
                        }

                        period_index = self.get_period_index(start_date, current_date, granularity)

                        for product in products:
                            for account in accounts:
                                value = self.calculate_kpi_value(
                                    kpi['formula'],
                                    period_index,
                                    product,
                                    account
                                ) * account['weight'] / 100

                                # Round according to format
                                value = round(value, 2 if is_decimal else 0)

                                period_data["rows"].append({
                                    "prd": product['extId'],
                                    "acc": account['extId'],
                                    "value": value
                                })

                        output_data["volumes"].append(period_data)

                    # Save to file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{timestamp}_output_{kpi['measureCode']}.json"
                    filepath = os.path.join(output_dir, filename)
                    with open(filepath, 'w') as f:
                        json.dump(output_data, f, indent=2)

            messagebox.showinfo("Success", "Files processed and saved successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while processing: {str(e)}")

    def select_folder(self):
        folder_path = filedialog.askdirectory(title="Select Folder")
        if not folder_path:
            return
            
        self.json_data = {file: None for file in self.REQUIRED_FILES}
        
        all_files_present = True
        for filename in self.REQUIRED_FILES:
            file_path = os.path.join(folder_path, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        self.json_data[filename] = json.load(f)
                    self.status_labels[filename].config(text="Loaded", fg="green")
                except json.JSONDecodeError:
                    self.status_labels[filename].config(text="Invalid JSON", fg="red")
                    all_files_present = False
                except Exception as e:
                    self.status_labels[filename].config(text=f"Error: {str(e)}", fg="red")
                    all_files_present = False
            else:
                self.status_labels[filename].config(text="Not found", fg="red")
                all_files_present = False
        
        self.process_button.config(state=tk.NORMAL if all_files_present else tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = JSONProcessorApp(root)
    root.mainloop()