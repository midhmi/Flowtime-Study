import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import json
import os
import threading
import time

# Try importing playsound, but provide a fallback if not installed/fails
try:
    from playsound import playsound
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False
    import winsound # For Windows system beep fallback

class TimeTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Flowtime Focus Tracker")
        self.root.geometry("700x600")

        # --- State Variables ---
        self.records = []
        self.data_file = "flowtime_data.json"
        self.is_working = False
        self.is_breaking = False
        self.alarm_active = False  # NEW: Tracks if alarm is currently ringing
        self.start_timestamp = None
        self.timer_id = None 

        # --- Load Data ---
        self.load_records()

        # --- UI Setup ---
        self.style = ttk.Style()
        self.style.configure("Treeview", rowheight=25)
        self.style.configure("Bold.TButton", font=("Arial", 10, "bold"))
        
        self.create_widgets()
        
        # --- Events ---
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        # 1. Top Control Panel
        control_frame = tk.LabelFrame(self.root, text="Current Session", padx=10, pady=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        # Task Input
        tk.Label(control_frame, text="Task:").grid(row=0, column=0, sticky="w")
        self.task_name_entry = tk.Entry(control_frame, width=30, font=("Arial", 11))
        self.task_name_entry.grid(row=0, column=1, padx=5, sticky="w")

        # Live Timer Display
        self.timer_label = tk.Label(control_frame, text="00:00:00", font=("Helvetica", 32, "bold"), fg="#333")
        self.timer_label.grid(row=0, column=2, rowspan=2, padx=20)

        # Main Action Button
        self.action_btn = tk.Button(control_frame, text="Start Focus", command=self.toggle_work, 
                                    bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), width=15)
        self.action_btn.grid(row=1, column=0, columnspan=2, pady=10, sticky="we")

        # 2. History Table
        tree_frame = tk.Frame(self.root)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("Task", "Start", "End", "Duration", "Break")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100 if col != "Task" else 200)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 3. Bottom Utility Buttons
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(btn_frame, text="Edit Selected", command=self.edit_record).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Copy CSV", command=self.copy_to_clipboard).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Reset Data", command=self.clear_records, fg="red").pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_frame, text="View Stats", command=self.show_total_time).pack(side=tk.RIGHT, padx=5)

        self.update_table()

    # --- Core Logic ---

    def toggle_work(self):
        if not self.is_working:
            # START WORKING
            task_name = self.task_name_entry.get().strip()
            if not task_name:
                messagebox.showwarning("Missing Input", "Please enter a task name first.")
                return
            
            self.is_working = True
            self.start_timestamp = datetime.now()
            
            self.action_btn.config(text="Stop & Break", bg="#f44336") # Red color
            self.task_name_entry.config(state="disabled")
            self.update_timer_display()

        else:
            # STOP WORKING
            self.is_working = False
            end_time = datetime.now()
            duration_seconds = int((end_time - self.start_timestamp).total_seconds())
            
            new_record = {
                "task_name": self.task_name_entry.get().strip(),
                "start_time": self.start_timestamp,
                "end_time": end_time,
                "work_time_str": self.format_seconds(duration_seconds),
                "break_time_str": "0:00"
            }
            self.records.append(new_record)
            
            # UI Reset
            self.action_btn.config(text="Start Focus", bg="#4CAF50")
            self.task_name_entry.config(state="normal")
            self.update_table()
            
            if self.timer_id:
                self.root.after_cancel(self.timer_id)
            
            self.prompt_break()

    def update_timer_display(self):
        if self.is_working:
            elapsed = datetime.now() - self.start_timestamp
            self.timer_label.config(text=str(elapsed).split('.')[0], fg="green")
            self.timer_id = self.root.after(1000, self.update_timer_display)

    def prompt_break(self):
        def set_break():
            try:
                minutes = int(entry.get())
                win.destroy()
                self.start_break_timer(minutes)
            except ValueError:
                messagebox.showerror("Error", "Please enter a number.")

        win = tk.Toplevel(self.root)
        win.title("Take a Break?")
        win.geometry("250x120")
        tk.Label(win, text="Work session complete!\nMinutes for break:").pack(pady=10)
        entry = tk.Entry(win)
        entry.pack()
        entry.focus_set()
        tk.Button(win, text="Start Break", command=set_break).pack(pady=10)

    def start_break_timer(self, minutes):
        self.is_breaking = True
        self.break_seconds_left = minutes * 60
        self.records[-1]['break_time_str'] = f"{minutes}:00"
        self.update_table()

        # Launch Break Window
        self.break_win = tk.Toplevel(self.root)
        self.break_win.title("On Break")
        self.break_win.geometry("300x200")
        # Handle 'X' button on break window
        self.break_win.protocol("WM_DELETE_WINDOW", self.end_break_early)
        
        self.lbl_break = tk.Label(self.break_win, text="00:00", font=("Arial", 30))
        self.lbl_break.pack(expand=True)
        
        self.btn_end_break = tk.Button(self.break_win, text="End Break", command=self.end_break_early, bg="#f44336", fg="white")
        self.btn_end_break.pack(pady=20)
        
        self.run_break_countdown()

    def run_break_countdown(self):
        if self.break_seconds_left > 0 and self.is_breaking:
            mins, secs = divmod(self.break_seconds_left, 60)
            self.lbl_break.config(text=f"{mins:02}:{secs:02}")
            self.timer_label.config(text=f"Break: {mins:02}:{secs:02}", fg="blue")
            
            self.break_seconds_left -= 1
            self.timer_id = self.root.after(1000, self.run_break_countdown)
        elif self.break_seconds_left <= 0 and self.is_breaking:
            # Time is up! Trigger the alarm loop
            self.trigger_alarm()

    def trigger_alarm(self):
        """Called when break timer hits 0. Starts the sound loop."""
        self.is_breaking = False
        self.alarm_active = True
        
        # Update UI to show Time is Up
        if hasattr(self, 'break_win') and self.break_win.winfo_exists():
            self.lbl_break.config(text="TIME UP!", fg="red")
            self.btn_end_break.config(text="STOP ALARM", bg="red")
            # Bring window to front
            self.break_win.lift()
            self.break_win.attributes('-topmost',True)
            self.break_win.after_idle(self.break_win.attributes,'-topmost',False)

        self.timer_label.config(text="00:00:00", fg="red")

        # Start the sound loop in a background thread
        threading.Thread(target=self.loop_sound, daemon=True).start()

    def loop_sound(self):
        """Runs in a separate thread. Loops until alarm_active is False."""
        while self.alarm_active:
            if SOUND_AVAILABLE and os.path.exists("notification.mp3"):
                try:
                    # block=True is crucial here so it waits for sound to finish before looping
                    playsound("notification.mp3", block=True)
                except:
                    self.system_beep()
                    time.sleep(1) # Gap between beeps
            else:
                self.system_beep()
                time.sleep(1) 

    def end_break_early(self):
        """Stops the break and the alarm."""
        self.is_breaking = False
        self.alarm_active = False  # This kills the loop_sound thread
        
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            
        if hasattr(self, 'break_win') and self.break_win.winfo_exists():
            self.break_win.destroy()
        
        self.timer_label.config(text="00:00:00", fg="#333")
        messagebox.showinfo("Focus", "Break ended. Ready for next task?")

    # --- Helpers & Utilities ---
            
    def system_beep(self):
        try:
            import winsound
            winsound.Beep(1000, 500) 
        except:
            print("\a") 

    def format_seconds(self, seconds):
        return str(timedelta(seconds=seconds))

    def update_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in reversed(self.records): 
            self.tree.insert("", "end", values=(
                r['task_name'],
                r['start_time'].strftime("%H:%M") if r['start_time'] else "-",
                r['end_time'].strftime("%H:%M") if r['end_time'] else "-",
                r['work_time_str'],
                r.get('break_time_str', "-")
            ))

    def copy_to_clipboard(self):
        self.root.clipboard_clear()
        header = "Task\tStart\tEnd\tWork\tBreak\n"
        data = ""
        for r in self.records:
            data += f"{r['task_name']}\t{r['start_time']}\t{r['end_time']}\t{r['work_time_str']}\t{r.get('break_time_str','')}\n"
        self.root.clipboard_append(header + data)
        messagebox.showinfo("Copied", "Data copied to clipboard.")

    def show_total_time(self):
        total_sec = 0
        for r in self.records:
            try:
                h, m, s = map(int, r['work_time_str'].split(':'))
                total_sec += h*3600 + m*60 + s
            except: pass
        msg = f"Total Work Time: {str(timedelta(seconds=total_sec))}"
        messagebox.showinfo("Statistics", msg)

    def clear_records(self):
        if messagebox.askyesno("Confirm", "Delete all history?"):
            self.records = []
            self.update_table()

    def save_records(self):
        serializable = []
        for r in self.records:
            item = r.copy()
            if item['start_time']: item['start_time'] = item['start_time'].strftime("%Y-%m-%d %H:%M:%S")
            if item['end_time']: item['end_time'] = item['end_time'].strftime("%Y-%m-%d %H:%M:%S")
            serializable.append(item)
        with open(self.data_file, "w") as f:
            json.dump(serializable, f, indent=4)

    def load_records(self):
        if not os.path.exists(self.data_file): return
        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)
                for r in data:
                    if r['start_time']: r['start_time'] = datetime.strptime(r['start_time'], "%Y-%m-%d %H:%M:%S")
                    if r['end_time']: r['end_time'] = datetime.strptime(r['end_time'], "%Y-%m-%d %H:%M:%S")
                    self.records.append(r)
        except Exception as e:
            print(f"Error loading data: {e}")

    def edit_record(self):
        pass 

    def on_close(self):
        self.alarm_active = False # Kill alarm thread if app closes
        self.save_records()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TimeTrackerApp(root)
    root.mainloop()