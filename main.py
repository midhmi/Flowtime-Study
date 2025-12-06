from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from datetime import datetime, timedelta
import json
import os

# Dark Theme
Window.clearcolor = (0.12, 0.12, 0.12, 1)

class HistoryCard(BoxLayout):
    """
    Updated Row: Shows Task, Start-End Time, and Duration
    """
    def __init__(self, task, start_t, end_t, duration, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = 110 # Slightly taller for more info
        self.padding = 10
        
        # 1. Task Name
        self.add_widget(Label(text=task, font_size='18sp', bold=True, color=(1,1,1,1), size_hint_y=0.4))
        
        # 2. Start - End Time
        time_str = f"{start_t} - {end_t}"
        self.add_widget(Label(text=time_str, color=(0.7, 0.7, 0.7, 1), font_size='14sp', size_hint_y=0.3))
        
        # 3. Focus Duration
        dur_str = f"Focus Time: {duration}"
        self.add_widget(Label(text=dur_str, color=(0, 1, 0, 1), bold=True, size_hint_y=0.3))
        
        # Separator
        self.add_widget(Label(text="_"*30, color=(0.3,0.3,0.3,1), size_hint_y=0.1))

class FlowtimeApp(App):
    def build(self):
        self.data_file = "flowtime_v2.json"
        self.records = []
        
        self.state = 'IDLE'
        self.start_timestamp = None
        self.end_timestamp = None
        self.work_seconds_total = 0
        self.break_seconds_total = 0 # Track this for stats
        
        # Load Sound
        self.sound = SoundLoader.load('alarm.mp3') 

        # --- MAIN LAYOUT ---
        root = BoxLayout(orientation='vertical', padding=15, spacing=10)

        # 1. INPUT
        self.task_input = TextInput(hint_text="Enter Task Name...", 
                                    multiline=False, size_hint_y=0.1,
                                    background_color=(0.2, 0.2, 0.2, 1),
                                    foreground_color=(1, 1, 1, 1), font_size='18sp')
        root.add_widget(self.task_input)

        # 2. TIMER
        self.timer_label = Label(text="00:00:00", font_size='60sp', bold=True, color=(1, 1, 1, 1), size_hint_y=0.25)
        root.add_widget(self.timer_label)

        # 3. STATUS
        self.status_label = Label(text="Ready to Focus", color=(0.7, 0.7, 0.7, 1), size_hint_y=0.05)
        root.add_widget(self.status_label)

        # 4. BUTTONS ROW
        btn_layout = BoxLayout(size_hint_y=0.15, spacing=10)
        
        # Main Action Button
        self.main_btn = Button(text="START FOCUS", background_color=(0.2, 0.8, 0.2, 1), font_size='20sp', bold=True)
        self.main_btn.bind(on_press=self.on_main_button)
        btn_layout.add_widget(self.main_btn)
        
        # Stats / Settings Button
        self.stats_btn = Button(text="STATS", background_color=(0.3, 0.3, 0.3, 1), size_hint_x=0.3)
        self.stats_btn.bind(on_press=self.show_stats_popup)
        btn_layout.add_widget(self.stats_btn)
        
        root.add_widget(btn_layout)

        # 5. HISTORY
        root.add_widget(Label(text="Session History", size_hint_y=0.05, color=(0.5, 0.5, 0.5, 1)))
        self.scroll_view = ScrollView(size_hint_y=0.4)
        self.history_grid = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.history_grid.bind(minimum_height=self.history_grid.setter('height'))
        self.scroll_view.add_widget(self.history_grid)
        root.add_widget(self.scroll_view)

        self.load_records()
        return root

    # --- LOGIC HANDLERS ---
    def on_main_button(self, instance):
        if self.state == 'IDLE':
            self.start_work()
        elif self.state == 'WORKING':
            self.trigger_break_setup()
        elif self.state == 'BREAK':
            self.end_break()

    def start_work(self):
        if not self.task_input.text.strip():
            self.status_label.text = "Enter Task Name First!"
            self.status_label.color = (1, 0, 0, 1)
            return

        self.state = 'WORKING'
        self.start_timestamp = datetime.now()
        
        # UI Updates
        self.main_btn.text = "STOP FOCUS"
        self.main_btn.background_color = (0.9, 0.3, 0.3, 1) # Red
        self.stats_btn.disabled = True # Disable stats while working
        self.status_label.text = "Focus Mode: ON"
        self.status_label.color = (0, 1, 0, 1)
        
        Clock.schedule_interval(self.update_timer, 1)

    def trigger_break_setup(self):
        # 1. Capture Work Data
        self.end_timestamp = datetime.now()
        delta = self.end_timestamp - self.start_timestamp
        self.work_seconds_total = int(delta.total_seconds())
        work_minutes = self.work_seconds_total // 60

        # 2. Logic: Max(3, Work/5)
        if work_minutes <= 15:
            suggested_mins = 3
        else:
            suggested_mins = int(work_minutes / 5)
            if suggested_mins < 3: suggested_mins = 3

        # 3. Popup
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=f"Work Done: {self.format_time(self.work_seconds_total)}"))
        content.add_widget(Label(text="Break Duration (mins):"))
        
        self.break_input = TextInput(text=str(suggested_mins), multiline=False, font_size='25sp', halign='center')
        content.add_widget(self.break_input)
        
        btn = Button(text="START BREAK", background_color=(0.2, 0.6, 0.9, 1))
        btn.bind(on_press=self.confirm_break_start)
        content.add_widget(btn)

        self.break_popup = Popup(title="Break Time", content=content, size_hint=(0.8, 0.5), auto_dismiss=False)
        self.break_popup.open()

    def confirm_break_start(self, instance):
        try:
            mins = int(self.break_input.text)
        except ValueError:
            mins = 3
        
        self.break_popup.dismiss()
        
        # Save the Work Record NOW (so we have start/end times accurately)
        self.save_work_record()
        
        # Start Break
        self.start_break(mins)

    def start_break(self, minutes):
        self.state = 'BREAK'
        self.break_seconds_left = minutes * 60
        self.break_seconds_total = minutes * 60 # Store specifically for stats
        
        self.main_btn.text = "END BREAK"
        self.main_btn.background_color = (0.2, 0.6, 0.9, 1) # Blue
        self.status_label.text = f"Relaxing..."
        self.status_label.color = (0.2, 0.8, 1, 1)

    def end_break(self):
        Clock.unschedule(self.update_timer)
        if self.sound and self.sound.state == 'play':
            self.sound.stop()
        
        # Reset UI to IDLE
        self.state = 'IDLE'
        self.main_btn.text = "START FOCUS"
        self.main_btn.background_color = (0.2, 0.8, 0.2, 1)
        self.stats_btn.disabled = False
        self.status_label.text = "Ready"
        self.status_label.color = (0.7, 0.7, 0.7, 1)
        self.timer_label.text = "00:00:00"

    def update_timer(self, dt):
        if self.state == 'WORKING':
            delta = datetime.now() - self.start_timestamp
            self.timer_label.text = self.format_time(int(delta.total_seconds()))
            
        elif self.state == 'BREAK':
            if self.break_seconds_left > 0:
                self.break_seconds_left -= 1
                self.timer_label.text = self.format_time(self.break_seconds_left)
            else:
                self.timer_label.text = "00:00:00"
                self.status_label.text = "BREAK OVER!"
                # PLAY SOUND
                self.play_alarm()
                # Visual Flash (Backup if sound fails)
                if int(datetime.now().second) % 2 == 0:
                    Window.clearcolor = (0.5, 0, 0, 1)
                else:
                    Window.clearcolor = (0.12, 0.12, 0.12, 1)

    def play_alarm(self):
        try:
            if self.sound:
                self.sound.play()
        except: 
            print("Sound Error")

    # --- STATS & DATA ---
    def show_stats_popup(self, instance):
        # Calculate Totals
        total_work_sec = sum(r.get('work_sec', 0) for r in self.records)
        # Note: We are estimating break time based on user settings, or you could save it specifically
        # For now, let's just show Total Work Time as that's the most critical metric
        
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        stat_lbl = Label(text=f"Total Focus Time:\n{self.format_time(total_work_sec)}", 
                         font_size='25sp', halign='center')
        content.add_widget(stat_lbl)
        
        # Clear Data Button
        clear_btn = Button(text="CLEAR ALL DATA", background_color=(1, 0, 0, 1), size_hint_y=0.3)
        clear_btn.bind(on_press=self.clear_data)
        content.add_widget(clear_btn)
        
        close_btn = Button(text="Close", size_hint_y=0.3)
        self.stats_popup = Popup(title="Statistics", content=content, size_hint=(0.8, 0.6))
        
        close_btn.bind(on_press=self.stats_popup.dismiss)
        content.add_widget(close_btn)
        self.stats_popup.open()

    def clear_data(self, instance):
        self.records = []
        try:
            if os.path.exists(self.data_file):
                os.remove(self.data_file)
        except: pass
        
        self.history_grid.clear_widgets()
        self.stats_popup.dismiss()
        self.status_label.text = "Data Cleared"

    def save_work_record(self):
        # Format Times
        start_str = self.start_timestamp.strftime("%H:%M")
        end_str = self.end_timestamp.strftime("%H:%M")
        dur_str = self.format_time(self.work_seconds_total)
        
        record = {
            "task": self.task_input.text,
            "start": start_str,
            "end": end_str,
            "duration": dur_str,
            "work_sec": self.work_seconds_total
        }
        
        self.records.insert(0, record)
        
        # Save to JSON
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.records, f)
        except: pass
        
        # Add to UI
        card = HistoryCard(self.task_input.text, start_str, end_str, dur_str)
        self.history_grid.add_widget(card, index=len(self.history_grid.children))

    def load_records(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.records = json.load(f)
                    for r in reversed(self.records):
                        card = HistoryCard(r['task'], r['start'], r['end'], r['duration'])
                        self.history_grid.add_widget(card, index=len(self.history_grid.children))
            except: pass

    def format_time(self, seconds):
        return str(timedelta(seconds=seconds)).split('.')[0]

if __name__ == '__main__':
    FlowtimeApp().run()