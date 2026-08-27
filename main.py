import tkinter as tk
import keyboard
import threading
import os
from datetime import datetime

import requests

import cron_vision as vision
from embedder import get_embedding
from vector_store import VectorStore

class SubconsciousUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw() # Hide window initially
        
        # Make borderless and keep on top
        self.root.overrideredirect(True)
        self.root.configure(bg='#1e1e1e', padx=10, pady=10)
        self.root.attributes('-topmost', True)
        
        # Setup UI elements (Input State)
        self.entry = tk.Entry(
            self.root, font=('Consolas', 16), bg='#2d2d2d', fg='#ffffff', 
            insertbackground='white', width=60, borderwidth=0, 
            highlightthickness=1, highlightbackground="#3d3d3d"
        )
        
        # Setup UI elements (Reflection State)
        self.reflection_text = tk.Text(
            self.root, font=('Consolas', 12), bg='#1e1e1e', fg='#a0a0a0', 
            width=80, height=12, borderwidth=0, highlightthickness=0, 
            state=tk.DISABLED, wrap=tk.WORD
        )
        
        # Initialize the local Vector Database connection
        self.vector_store = VectorStore()
        self.is_visible = False
        
        # Thread-safe event binding for showing the window from the hotkey thread
        self.root.bind("<<ShowWindow>>", self._show_window_safe)
        self.root.bind("<<VisionCapture>>", self._vision_capture_safe)
        
        # Global key bindings for the application
        self.root.bind('<Escape>', self.hide_window)
        self.entry.bind('<Return>', self.on_enter)
        
        # Start keyboard listeners for the global hotkeys
        keyboard.add_hotkey('ctrl+alt+space', self.trigger_show_window)
        keyboard.add_hotkey('ctrl+alt+v', self.trigger_vision_capture)
        
    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def trigger_show_window(self):
        """Called by the keyboard listener thread; safely alerts main thread."""
        try:
            self.root.event_generate("<<ShowWindow>>", when="tail")
        except tk.TclError:
            pass

    def trigger_vision_capture(self):
        """Called by the keyboard listener thread; safely alerts main thread."""
        try:
            self.root.event_generate("<<VisionCapture>>", when="tail")
        except tk.TclError:
            pass

    def _vision_capture_safe(self, event=None):
        """Screenshot → Copilot vision → entity mind map, on demand."""
        if self.is_visible:
            return
        # Capture BEFORE the overlay appears so it never observes itself
        try:
            temp_path = vision.capture_screen()
        except Exception as exc:
            temp_path = None
            capture_error = exc

        self.is_visible = True
        self.entry.pack_forget()
        self.reflection_text.config(state=tk.NORMAL)
        self.reflection_text.delete(1.0, tk.END)
        if temp_path:
            self.reflection_text.insert(tk.END, "[optic nerve] screen captured.\n[visual cortex] consulting the model...\n\nThis can take a minute. Press Escape to hide (processing continues).")
        else:
            self.reflection_text.insert(tk.END, f"Screen capture failed: {capture_error}\n\nPress Escape to close.")
        self.reflection_text.config(state=tk.DISABLED)
        self.reflection_text.pack(padx=10, pady=10)

        self.root.deiconify()
        self.root.attributes('-topmost', True)
        self.center_window()

        if temp_path:
            threading.Thread(target=self.process_vision_thread, args=(temp_path,), daemon=True).start()

    def process_vision_thread(self, temp_path):
        """Background: transduce the capture and inject it into the entity mind map."""
        try:
            copilot_path = vision.resolve_copilot()
            if not copilot_path:
                self.root.after(0, lambda: self.display_message("Copilot CLI not found on PATH.\n\nPress Escape to close."))
                return

            thought = vision.transduce(copilot_path, temp_path)
            payload = vision.inject(thought)

            lines = ["--- Narrated Thought ---", "", thought, ""]
            if payload.get("status") == "duplicate":
                lines.append("(the void already knew — duplicate, skipped.)")
            else:
                related = payload.get("related") or []
                if related:
                    lines.append("--- Echoes ---")
                    lines.extend(f"~ {prior}" for prior in related)
                else:
                    lines.append("(no echoes — thought zero territory.)")
            lines.extend(["", "Press Escape to close."])
            message = "\n".join(lines)
        except requests.ConnectionError:
            message = f"Local subconscious API unreachable at {vision.API_URL}.\n\nIs explorer.py running?\n\nPress Escape to close."
        except Exception as exc:
            message = f"Vision pipeline error: {exc}\n\nPress Escape to close."
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        self.root.after(0, lambda: self.display_message(message))

    def _show_window_safe(self, event=None):
        if self.is_visible: return
        self.is_visible = True
        
        self.reflection_text.pack_forget()
        self.entry.pack(padx=10, pady=10)
        self.entry.config(state=tk.NORMAL)
        self.entry.delete(0, tk.END)
        
        self.root.deiconify()
        self.root.attributes('-topmost', True)
        self.root.focus_force()
        self.entry.focus_set()
        self.center_window()

    def hide_window(self, event=None):
        self.root.withdraw()
        self.is_visible = False

    def on_enter(self, event):
        thought = self.entry.get().strip()
        if not thought:
            self.hide_window()
            return
        
        self.entry.config(state=tk.DISABLED)
        self.entry.pack_forget()
        
        # Transition to reflection state visually
        self.reflection_text.config(state=tk.NORMAL)
        self.reflection_text.delete(1.0, tk.END)
        self.reflection_text.insert(tk.END, "Processing thought...")
        self.reflection_text.config(state=tk.DISABLED)
        self.reflection_text.pack(padx=10, pady=10)
        self.center_window()
        
        # Run API call and ChromaDB logic in background thread to prevent UI freezing
        threading.Thread(target=self.process_thought_thread, args=(thought,), daemon=True).start()

    def process_thought_thread(self, thought):
        # Issue #1: Check for duplicates before hitting the slow embedding API
        if self.vector_store.is_duplicate(thought):
            self.root.after(0, lambda: self.display_message("Thought already exists in your subconscious.\n\nDuplicate skipped.\n\nPress Escape to close."))
            return

        embedding = get_embedding(thought)
        
        if embedding is None:
            # Graceful Fallback: write to backlog.txt if LM Studio is not reachable
            backlog_path = os.path.join(os.path.dirname(__file__), "backlog.txt")
            with open(backlog_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} - {thought}\n")
            self.root.after(0, self.display_error)
            return
        
        # Execute query and upsert logic
        matches = self.vector_store.process_thought(thought, embedding)
        
        # Push matches to main thread for UI display
        self.root.after(0, lambda: self.display_matches(matches))

    def display_error(self):
        self.reflection_text.config(state=tk.NORMAL)
        self.reflection_text.delete(1.0, tk.END)
        self.reflection_text.insert(tk.END, "LM Studio endpoint unreachable.\n\nThought saved locally to backlog.txt.\n\nPress Escape to close.")
        self.reflection_text.config(state=tk.DISABLED)
        self.center_window()

    def display_message(self, message):
        self.reflection_text.config(state=tk.NORMAL)
        self.reflection_text.delete(1.0, tk.END)
        self.reflection_text.insert(tk.END, message)
        self.reflection_text.config(state=tk.DISABLED)
        self.center_window()

    def display_matches(self, matches):
        self.reflection_text.config(state=tk.NORMAL)
        self.reflection_text.delete(1.0, tk.END)
        
        if not matches:
            self.reflection_text.insert(tk.END, "Thought embedded and saved.\n\nNo historical thoughts found (Database is empty).\n\nPress Escape to close.")
        else:
            self.reflection_text.insert(tk.END, "--- Top 3 Similar Thoughts ---\n\n")
            for i, match in enumerate(matches, 1):
                self.reflection_text.insert(tk.END, f"{i}. {match}\n\n")
            self.reflection_text.insert(tk.END, "Press Escape to close.")
        
        self.reflection_text.config(state=tk.DISABLED)
        self.center_window()

    def check_events(self):
        # Periodically process events to allow KeyboardInterrupt (Ctrl+C) to be caught
        self.root.after(100, self.check_events)

    def run(self):
        self.check_events()
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\nExiting Local Subconscious...")
            self.root.destroy()

if __name__ == "__main__":
    app = SubconsciousUI()
    app.run()