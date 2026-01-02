import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
from PIL import Image, ImageTk, ImageDraw
import cv2
import numpy as np
import os
from datetime import datetime
from copy import deepcopy
import gc


class AutoSaveManager:
    """Manages automatic saving of all operations to a designated folder"""
    def __init__(self):
        self.save_folder = None
        self.auto_save_enabled = False
        self.session_name = datetime.now().strftime("%Y%m%d_%H%M%S")

    def setup_save_folder(self, parent_window):
        """Let user select or create a save folder"""
        choice = messagebox.askyesnocancel(
            "Auto-Save Setup",
            "Do you want to:\n\n" +
            "YES - Select existing folder\n" +
            "NO - Create new project folder\n" +
            "CANCEL - Skip auto-save"
        )

        if choice is None:
            return False

        if choice:
            folder = filedialog.askdirectory(title="Select Save Folder")
            if folder:
                self.save_folder = folder
                self.auto_save_enabled = True
                messagebox.showinfo("Auto-Save Enabled", 
                                   f"✅ Saving to:\n{folder}")
                return True
        else:
            base_folder = filedialog.askdirectory(title="Select Location for New Project Folder")
            if base_folder:
                project_name = simpledialog.askstring(
                    "Project Name",
                    "Enter project folder name:",
                    initialvalue=f"LeafAnalysis_{self.session_name}"
                )
                if project_name:
                    self.save_folder = os.path.join(base_folder, project_name)
                    try:
                        os.makedirs(self.save_folder, exist_ok=True)
                        os.makedirs(os.path.join(self.save_folder, "palettes"), exist_ok=True)
                        os.makedirs(os.path.join(self.save_folder, "boundaries"), exist_ok=True)
                        os.makedirs(os.path.join(self.save_folder, "edits"), exist_ok=True)
                        os.makedirs(os.path.join(self.save_folder, "merged"), exist_ok=True)

                        self.auto_save_enabled = True
                        messagebox.showinfo("Auto-Save Enabled", 
                                           f"✅ Project folder created:\n{self.save_folder}")
                        return True
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to create folder:\n{e}")
                        return False
        return False

    def change_save_folder(self, parent_window):
        """Change the save folder"""
        self.auto_save_enabled = False
        return self.setup_save_folder(parent_window)

    def save_palette(self, palette_id, image, category="palettes"):
        """Auto-save a palette image"""
        if not self.auto_save_enabled or self.save_folder is None:
            return None

        try:
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"{palette_id}_{timestamp}.png"
            subfolder = os.path.join(self.save_folder, category)
            filepath = os.path.join(subfolder, filename)

            image.save(filepath)
            return filepath
        except Exception as e:
            print(f"Auto-save error: {e}")
            return None

    def save_cv_image(self, name, cv_image, category="boundaries"):
        """Auto-save OpenCV image"""
        if not self.auto_save_enabled or self.save_folder is None:
            return None

        try:
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"{name}_{timestamp}.png"
            subfolder = os.path.join(self.save_folder, category)
            filepath = os.path.join(subfolder, filename)

            cv2.imwrite(filepath, cv_image)
            return filepath
        except Exception as e:
            print(f"Auto-save error: {e}")
            return None

    def get_status(self):
        """Get auto-save status string"""
        if self.auto_save_enabled and self.save_folder:
            return f"✅ Auto-Save: ON ({os.path.basename(self.save_folder)})"
        return "❌ Auto-Save: OFF"


class PaletteEditor:
    """OPTIMIZED palette editor with smooth RGB replacement"""
    def __init__(self, parent, palette_image, palette_id, callback, auto_save_manager=None):
        self.window = tk.Toplevel(parent)
        self.window.title(f"Edit {palette_id}")
        self.window.geometry("1400x850")
        self.window.configure(bg="#2b2b2b")

        self.original_palette = palette_image.copy()
        self.edit_layer = Image.new('RGBA', palette_image.size, (0, 0, 0, 0))
        self.palette_image = palette_image.copy()

        self.palette_id = palette_id
        self.callback = callback
        self.auto_save_manager = auto_save_manager

        self.drawing = False
        self.last_x = None
        self.last_y = None
        self.current_tool = "pencil"
        self.draw_color = (255, 0, 0)
        self.line_thickness = 5
        self.zoom_level = 1.0

        # OPTIMIZED: Reduced history from 50 to 15 to save memory
        self.history = [self.palette_image.copy()]
        self.history_index = 0
        self.max_history = 15

        self.temp_line_start = None

        # RGB replacement variables
        self.selected_rgb_to_replace = None
        self.replacement_rgb = None

        self.setup_ui()
        self.update_composite_image()
        self.display_canvas_image()

    def setup_ui(self):
        # Main container with LEFT (editor) and RIGHT (RGB panel)
        main_container = tk.Frame(self.window, bg="#2b2b2b")
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # LEFT SIDE - Editor
        left_frame = tk.Frame(main_container, bg="#2b2b2b")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Toolbar
        toolbar = tk.Frame(left_frame, bg="#363636", relief=tk.RAISED, bd=2)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        tk.Label(toolbar, text="Tools:", bg="#363636", fg="#FFD700",
                font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=10)

        tools = [
            ("✏️ Pencil", "pencil", "#4CAF50"),
            ("📏 Line", "line", "#9C27B0"),
            ("🎨 Fill", "fill", "#FF9800"),
            ("🧹 Eraser", "eraser", "#FF5722")
        ]

        for text, tool, color in tools:
            btn = tk.Button(toolbar, text=text, command=lambda t=tool: self.select_tool(t),
                          bg=color, fg="white", font=("Arial", 9, "bold"),
                          padx=8, pady=5, relief=tk.RAISED)
            btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=10)

        color_frame = tk.Frame(toolbar, bg="#363636")
        color_frame.pack(side=tk.LEFT, padx=5)

        tk.Label(color_frame, text="Color:", bg="#363636", fg="white",
                font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)

        self.color_display = tk.Canvas(color_frame, width=30, height=25, bg="#FF0000",
                                      relief=tk.SUNKEN, bd=2, cursor="hand2")
        self.color_display.pack(side=tk.LEFT)
        self.color_display.bind("<Button-1>", self.choose_color)

        preset_colors = [
            ("#FF0000", "Red"), ("#00FF00", "Green"), ("#0000FF", "Blue"),
            ("#FFFF00", "Yellow"), ("#FF00FF", "Magenta"), ("#00FFFF", "Cyan")
        ]

        for color_hex, name in preset_colors:
            preset_btn = tk.Button(color_frame, bg=color_hex, width=2, height=1,
                                  relief=tk.RAISED, bd=2,
                                  command=lambda c=color_hex: self.set_preset_color(c))
            preset_btn.pack(side=tk.LEFT, padx=1)

        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=10)

        tk.Button(toolbar, text="💾 Save", command=self.save_changes,
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                 padx=15, pady=5).pack(side=tk.RIGHT, padx=5)

        tk.Button(toolbar, text="❌ Cancel", command=self.window.destroy,
                 bg="#F44336", fg="white", font=("Arial", 10, "bold"),
                 padx=15, pady=5).pack(side=tk.RIGHT, padx=2)

        # Canvas frame
        canvas_frame = tk.Frame(left_frame, bg="#1e1e1e", relief=tk.SUNKEN, bd=3)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#1e1e1e", cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<MouseWheel>", self.on_mousewheel_zoom)
        self.canvas.bind("<Button-4>", self.on_mousewheel_zoom)
        self.canvas.bind("<Button-5>", self.on_mousewheel_zoom)

        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # BOTTOM BAR
        bottom_bar = tk.Frame(left_frame, bg="#363636", relief=tk.RAISED, bd=2)
        bottom_bar.pack(fill=tk.X, pady=(10, 0))

        # LEFT - Undo/Redo
        undo_frame = tk.Frame(bottom_bar, bg="#363636")
        undo_frame.pack(side=tk.LEFT, padx=10, pady=5)

        tk.Label(undo_frame, text="History:", bg="#363636", fg="#FFD700",
                font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)

        tk.Button(undo_frame, text="↶ Undo", command=self.undo,
                 bg="#607D8B", fg="white", font=("Arial", 9, "bold"),
                 padx=10, pady=4).pack(side=tk.LEFT, padx=2)

        tk.Button(undo_frame, text="↷ Redo", command=self.redo,
                 bg="#607D8B", fg="white", font=("Arial", 9, "bold"),
                 padx=10, pady=4).pack(side=tk.LEFT, padx=2)

        self.history_label = tk.Label(undo_frame, text="1/1", bg="#363636",
                                      fg="#00E676", font=("Arial", 9, "bold"))
        self.history_label.pack(side=tk.LEFT, padx=5)

        # RIGHT - Zoom
        zoom_frame = tk.Frame(bottom_bar, bg="#363636")
        zoom_frame.pack(side=tk.RIGHT, padx=10, pady=5)

        self.zoom_label = tk.Label(zoom_frame, text="100%", bg="#363636",
                                   fg="#00E676", font=("Arial", 9, "bold"))
        self.zoom_label.pack(side=tk.RIGHT, padx=5)

        tk.Button(zoom_frame, text="1:1", command=self.zoom_reset,
                 bg="#009688", fg="white", font=("Arial", 9, "bold"),
                 padx=8, pady=4).pack(side=tk.RIGHT, padx=2)

        tk.Button(zoom_frame, text="🔍-", command=self.zoom_out,
                 bg="#009688", fg="white", font=("Arial", 9, "bold"),
                 padx=8, pady=4).pack(side=tk.RIGHT, padx=2)

        tk.Button(zoom_frame, text="🔍+", command=self.zoom_in,
                 bg="#009688", fg="white", font=("Arial", 9, "bold"),
                 padx=8, pady=4).pack(side=tk.RIGHT, padx=2)

        tk.Label(zoom_frame, text="Zoom:", bg="#363636", fg="#FFD700",
                font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=5)

        # Status bar
        self.status_bar = tk.Label(left_frame, text="Tool: Pencil",
                                   bg="#363636", fg="#00E676", font=("Arial", 9, "bold"),
                                   anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # RIGHT SIDE - RGB Replacement Panel
        self.setup_rgb_panel(main_container)

    def setup_rgb_panel(self, parent):
        """Setup fixed RGB replacement panel on the right"""
        right_panel = tk.Frame(parent, bg="#363636", relief=tk.RAISED, bd=3, width=450)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        right_panel.pack_propagate(False)

        # Header
        header = tk.Frame(right_panel, bg="#E91E63")
        header.pack(fill=tk.X)
        tk.Label(header, text="🔄 RGB Color Replacement", 
                bg="#E91E63", fg="white",
                font=("Arial", 12, "bold")).pack(pady=10)

        # Scrollable content
        canvas = tk.Canvas(right_panel, bg="#363636", highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_panel, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#363636")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scroll
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        def _on_linux_scroll_up(event):
            canvas.yview_scroll(-1, "units")

        def _on_linux_scroll_down(event):
            canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_linux_scroll_up)
        canvas.bind_all("<Button-5>", _on_linux_scroll_down)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Detect button
        detect_frame = tk.Frame(scrollable_frame, bg="#363636")
        detect_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(detect_frame, text="🔍 Detect Colors in Palette",
                 command=self.detect_and_populate_colors,
                 bg="#2196F3", fg="white", font=("Arial", 10, "bold"),
                 padx=15, pady=8).pack(fill=tk.X)

        # Info label
        self.info_label = tk.Label(scrollable_frame, 
                                   text="Click 'Detect Colors' to start",
                                   bg="#363636", fg="#FFD700",
                                   font=("Arial", 9, "bold"), wraplength=400)
        self.info_label.pack(pady=5, padx=10)

        # Source colors
        source_frame = tk.Frame(scrollable_frame, bg="#2b2b2b", relief=tk.RAISED, bd=2)
        source_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        header_frame = tk.Frame(source_frame, bg="#2b2b2b")
        header_frame.pack(fill=tk.X, pady=5)

        tk.Label(header_frame, text="Step 1: Select Colors",
                bg="#2b2b2b", fg="#FFD700", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)

        self.select_all_var = tk.BooleanVar(value=False)
        select_all_cb = tk.Checkbutton(header_frame, text="Select All",
                                       variable=self.select_all_var,
                                       command=self.toggle_select_all_colors,
                                       bg="#2b2b2b", fg="#00FF00",
                                       selectcolor="#1e1e1e",
                                       font=("Arial", 9, "bold"))
        select_all_cb.pack(side=tk.RIGHT, padx=10)

        # Listbox
        list_container = tk.Frame(source_frame, bg="#2b2b2b")
        list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        list_scrollbar = tk.Scrollbar(list_container)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.color_listbox = tk.Listbox(list_container, bg="#1e1e1e", fg="#00FF00",
                                        font=("Courier", 9), height=8,
                                        yscrollcommand=list_scrollbar.set,
                                        selectmode=tk.MULTIPLE,
                                        selectbackground="#4CAF50")
        self.color_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scrollbar.config(command=self.color_listbox.yview)

        self.color_listbox.bind('<<ListboxSelect>>', self.on_source_colors_select)

        # Selected display
        display_frame = tk.Frame(source_frame, bg="#2b2b2b")
        display_frame.pack(pady=8)

        tk.Label(display_frame, text="Selected:", bg="#2b2b2b", fg="white",
                font=("Arial", 8)).pack(side=tk.LEFT, padx=5)

        self.source_color_display = tk.Canvas(display_frame, width=80, height=30, 
                                              bg="#FFFFFF", relief=tk.SUNKEN, bd=3)
        self.source_color_display.pack(side=tk.LEFT, padx=5)

        self.source_rgb_label = tk.Label(source_frame, text="No colors selected",
                                         bg="#2b2b2b", fg="#FFD700", font=("Arial", 9, "bold"))
        self.source_rgb_label.pack(pady=3)

        # Target color
        target_frame = tk.Frame(scrollable_frame, bg="#2b2b2b", relief=tk.RAISED, bd=2)
        target_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(target_frame, text="Step 2: Replacement Color",
                bg="#2b2b2b", fg="#FFD700", font=("Arial", 10, "bold")).pack(pady=5)

        target_display_frame = tk.Frame(target_frame, bg="#2b2b2b")
        target_display_frame.pack(pady=5)

        tk.Label(target_display_frame, text="New Color:", bg="#2b2b2b", fg="white",
                font=("Arial", 8)).pack(side=tk.LEFT, padx=5)

        self.target_color_display = tk.Canvas(target_display_frame, width=80, height=30,
                                              bg="#FFFFFF", relief=tk.SUNKEN, bd=3)
        self.target_color_display.pack(side=tk.LEFT, padx=5)

        self.target_rgb_label = tk.Label(target_frame, text="Click below to choose",
                                         bg="#2b2b2b", fg="#FFD700", font=("Arial", 9, "bold"))
        self.target_rgb_label.pack(pady=3)

        tk.Button(target_frame, text="🎨 Pick Color",
                 command=self.choose_replacement_color,
                 bg="#FF9800", fg="white", font=("Arial", 9, "bold"),
                 padx=10, pady=6).pack(pady=5)

        # Tolerance
        tolerance_frame = tk.Frame(scrollable_frame, bg="#2b2b2b", relief=tk.RAISED, bd=2)
        tolerance_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(tolerance_frame, text="Tolerance:",
                bg="#2b2b2b", fg="white", font=("Arial", 9, "bold")).pack(pady=3)

        self.tolerance_var = tk.IntVar(value=5)
        tolerance_slider = ttk.Scale(tolerance_frame, from_=0, to=50,
                                    variable=self.tolerance_var, orient=tk.HORIZONTAL)
        tolerance_slider.pack(fill=tk.X, padx=15, pady=5)

        self.tolerance_label = tk.Label(tolerance_frame, text="± 5 RGB units",
                                       bg="#2b2b2b", fg="#00E676", font=("Arial", 9))
        self.tolerance_label.pack(pady=2)

        self.tolerance_var.trace_add("write", lambda *args: 
                                    self.tolerance_label.config(text=f"± {self.tolerance_var.get()} RGB units"))

        # Apply button
        apply_frame = tk.Frame(scrollable_frame, bg="#363636")
        apply_frame.pack(fill=tk.X, padx=10, pady=15)

        tk.Button(apply_frame, text="✅ Apply Replacement",
                 command=self.apply_rgb_replacement,
                 bg="#4CAF50", fg="white", font=("Arial", 11, "bold"),
                 padx=20, pady=10).pack(fill=tk.X)

    def detect_and_populate_colors(self):
        """Detect colors and populate listbox"""
        unique_colors = self.detect_unique_colors()

        if len(unique_colors) == 0:
            self.info_label.config(text="⚠️ No colors detected (only white background)")
            messagebox.showwarning("No Colors", "No colors detected in this palette!")
            return

        self.info_label.config(text=f"✓ Found {len(unique_colors)} unique color(s)")

        self.color_listbox.delete(0, tk.END)
        self.unique_colors_list = unique_colors

        for color, pixel_count in unique_colors:
            color_hex = '#{:02x}{:02x}{:02x}'.format(*color)
            display_text = f"RGB{color} | {pixel_count:>6,}px | {color_hex}"
            self.color_listbox.insert(tk.END, display_text)

    def toggle_select_all_colors(self):
        if self.select_all_var.get():
            self.color_listbox.selection_set(0, tk.END)
        else:
            self.color_listbox.selection_clear(0, tk.END)
        self.on_source_colors_select(None)

    def detect_unique_colors(self):
        """OPTIMIZED: More efficient color detection"""
        img_array = np.array(self.palette_image)
        pixels = img_array.reshape(-1, 3)
        non_white_mask = ~np.all(pixels > 250, axis=1)
        colored_pixels = pixels[non_white_mask]

        if len(colored_pixels) == 0:
            return []

        unique_colors, counts = np.unique(colored_pixels, axis=0, return_counts=True)
        sorted_indices = np.argsort(-counts)
        unique_colors = unique_colors[sorted_indices]
        counts = counts[sorted_indices]

        return [(tuple(color), int(count)) for color, count in zip(unique_colors, counts)]

    def on_source_colors_select(self, event):
        selections = self.color_listbox.curselection()
        if not selections:
            self.source_rgb_label.config(text="No colors selected")
            return

        self.selected_rgb_to_replace = [self.unique_colors_list[idx][0] for idx in selections]

        if len(selections) == 1:
            selected_color, pixel_count = self.unique_colors_list[selections[0]]
            color_hex = '#{:02x}{:02x}{:02x}'.format(*selected_color)
            self.source_color_display.config(bg=color_hex)
            self.source_rgb_label.config(text=f"RGB{selected_color} ({pixel_count:,}px)")
        else:
            first_color = self.unique_colors_list[selections[0]][0]
            color_hex = '#{:02x}{:02x}{:02x}'.format(*first_color)
            self.source_color_display.config(bg=color_hex)
            total_pixels = sum(self.unique_colors_list[idx][1] for idx in selections)
            self.source_rgb_label.config(text=f"{len(selections)} colors ({total_pixels:,}px)")

    def choose_replacement_color(self):
        color = colorchooser.askcolor(title="Choose Replacement Color")
        if color[0]:
            self.replacement_rgb = tuple(int(c) for c in color[0])
            self.target_color_display.config(bg=color[1])
            self.target_rgb_label.config(text=f"RGB{self.replacement_rgb}")

    def apply_rgb_replacement(self):
        """OPTIMIZED AND STABILIZED RGB replacement"""
        if self.selected_rgb_to_replace is None or len(self.selected_rgb_to_replace) == 0:
            messagebox.showwarning("Error", "Please select at least one color!")
            return

        if self.replacement_rgb is None:
            messagebox.showwarning("Error", "Please choose a replacement color!")
            return

        # Create progress window
        progress_window = tk.Toplevel(self.window)
        progress_window.title("Processing...")
        progress_window.geometry("400x150")
        progress_window.transient(self.window)
        progress_window.grab_set()

        tk.Label(progress_window, text="Replacing colors, please wait...",
                font=("Arial", 12, "bold")).pack(pady=20)

        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var,
                                      maximum=100, length=350)
        progress_bar.pack(pady=10)

        status_label = tk.Label(progress_window, text="Starting...",
                               font=("Arial", 10))
        status_label.pack(pady=10)

        progress_window.update()

        try:
            # OPTIMIZED: Work directly with numpy array
            img_array = np.array(self.palette_image, dtype=np.uint8)
            tolerance = self.tolerance_var.get()
            total_pixels_changed = 0

            # Process each color with progress feedback
            num_colors = len(self.selected_rgb_to_replace)
            for idx, source_color in enumerate(self.selected_rgb_to_replace):
                status_label.config(text=f"Processing color {idx+1}/{num_colors}...")
                progress_var.set((idx / num_colors) * 90)
                progress_window.update()

                # OPTIMIZED: Vectorized operation
                target_color = np.array(source_color, dtype=np.int16)
                color_diff = np.abs(img_array.astype(np.int16) - target_color)
                mask = np.all(color_diff <= tolerance, axis=2)

                pixels_changed = np.sum(mask)
                total_pixels_changed += pixels_changed

                if pixels_changed > 0:
                    img_array[mask] = self.replacement_rgb

            if total_pixels_changed == 0:
                progress_window.destroy()
                messagebox.showwarning("No Match", "No pixels found! Try increasing tolerance.")
                return

            # Update progress
            status_label.config(text="Updating display...")
            progress_var.set(95)
            progress_window.update()

            # OPTIMIZED: Convert to Image efficiently
            self.palette_image = Image.fromarray(img_array, mode='RGB')

            # Clear old display to free memory
            self.canvas.delete("all")

            # Update display
            self.display_canvas_image()

            # OPTIMIZED: Save to history AFTER display update
            self.save_to_history()

            # Force garbage collection to free memory
            gc.collect()

            progress_var.set(100)
            status_label.config(text="Complete!")
            progress_window.update()

            # Auto-save
            if self.auto_save_manager:
                self.auto_save_manager.save_palette(f"{self.palette_id}_RGB_replaced", 
                                                   self.palette_image, "edits")

            progress_window.destroy()

            messagebox.showinfo("Success", 
                              f"✅ {total_pixels_changed:,} pixels changed!\n"
                              f"To: RGB{self.replacement_rgb}")

            self.selected_rgb_to_replace = None
            self.replacement_rgb = None
            self.update_status_bar()

        except Exception as e:
            progress_window.destroy()
            messagebox.showerror("Error", f"RGB replacement failed:\n{str(e)}")
            print(f"RGB replacement error: {e}")

    def select_tool(self, tool):
        self.current_tool = tool
        self.update_status_bar()

    def choose_color(self, event=None):
        color = colorchooser.askcolor(initialcolor=self.draw_color)
        if color[0]:
            self.draw_color = tuple(int(c) for c in color[0])
            self.color_display.config(bg=color[1])

    def set_preset_color(self, color_hex):
        color_hex = color_hex.lstrip('#')
        self.draw_color = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
        self.color_display.config(bg=f"#{color_hex}")

    def undo(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.palette_image = self.history[self.history_index].copy()
            self.display_canvas_image()
            self.update_status_bar()
            gc.collect()

    def redo(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.palette_image = self.history[self.history_index].copy()
            self.display_canvas_image()
            self.update_status_bar()
            gc.collect()

    def zoom_in(self):
        self.zoom_level = min(5.0, self.zoom_level + 0.25)
        self.display_canvas_image()
        self.update_status_bar()

    def zoom_out(self):
        self.zoom_level = max(0.25, self.zoom_level - 0.25)
        self.display_canvas_image()
        self.update_status_bar()

    def zoom_reset(self):
        self.zoom_level = 1.0
        self.display_canvas_image()
        self.update_status_bar()

    def on_mousewheel_zoom(self, event):
        if event.num == 4 or event.delta > 0:
            self.zoom_in()
        elif event.num == 5 or event.delta < 0:
            self.zoom_out()

    def update_status_bar(self):
        self.status_bar.config(text=f"Tool: {self.current_tool.capitalize()}")
        self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
        self.history_label.config(text=f"{self.history_index + 1}/{len(self.history)}")

    def update_composite_image(self):
        base = self.original_palette.convert('RGBA')
        composite = Image.alpha_composite(base, self.edit_layer)
        self.palette_image = composite.convert('RGB')

    def display_canvas_image(self):
        """OPTIMIZED: Memory-efficient canvas update"""
        display_img = self.palette_image.copy()
        new_size = (int(display_img.width * self.zoom_level),
                   int(display_img.height * self.zoom_level))
        display_img = display_img.resize(new_size, Image.Resampling.LANCZOS)

        self.display_image = display_img

        # OPTIMIZED: Clear old image reference before creating new
        if hasattr(self, 'photo_image'):
            del self.photo_image

        self.photo_image = ImageTk.PhotoImage(display_img)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

    def get_canvas_coords(self, x, y):
        img_x = int(x / self.zoom_level)
        img_y = int(y / self.zoom_level)
        img_x = max(0, min(self.palette_image.width - 1, img_x))
        img_y = max(0, min(self.palette_image.height - 1, img_y))
        return img_x, img_y

    def on_mouse_down(self, event):
        self.drawing = True
        img_x, img_y = self.get_canvas_coords(event.x, event.y)

        if self.current_tool == "fill":
            self.fill_enclosed_area(img_x, img_y)
        elif self.current_tool == "line":
            self.temp_line_start = (img_x, img_y)
        else:
            self.last_x = img_x
            self.last_y = img_y

    def on_mouse_drag(self, event):
        if not self.drawing:
            return
        img_x, img_y = self.get_canvas_coords(event.x, event.y)
        if self.current_tool in ["pencil", "eraser"]:
            if self.last_x is not None and self.last_y is not None:
                self.draw_line_on_layer(self.last_x, self.last_y, img_x, img_y)
                self.last_x = img_x
                self.last_y = img_y

    def on_mouse_up(self, event):
        if self.current_tool == "line" and self.temp_line_start:
            img_x, img_y = self.get_canvas_coords(event.x, event.y)
            self.draw_line_on_layer(self.temp_line_start[0], self.temp_line_start[1], img_x, img_y)
            self.temp_line_start = None
        self.drawing = False
        self.last_x = None
        self.last_y = None
        if self.current_tool != "fill":
            self.save_to_history()

    def draw_line_on_layer(self, x1, y1, x2, y2):
        draw = ImageDraw.Draw(self.edit_layer)
        if self.current_tool == "eraser":
            color = (0, 0, 0, 0)
        else:
            color = self.draw_color + (255,)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=5)
        self.update_composite_image()
        self.display_canvas_image()

    def fill_enclosed_area(self, x, y):
        img_array = np.array(self.palette_image)
        h, w = img_array.shape[:2]
        if x < 0 or x >= w or y < 0 or y >= h:
            return
        target_color = tuple(img_array[y, x, :3])
        fill_color = self.draw_color
        if target_color == fill_color:
            return
        if np.all(np.array(target_color) > 250):
            return
        visited = np.zeros((h, w), dtype=bool)
        stack = [(x, y)]
        tolerance = 30
        pixels_filled = 0
        while stack:
            cx, cy = stack.pop()
            if cx < 0 or cx >= w or cy < 0 or cy >= h:
                continue
            if visited[cy, cx]:
                continue
            current_color = img_array[cy, cx, :3]
            color_diff = np.abs(current_color.astype(int) - np.array(target_color))
            if not np.all(color_diff <= tolerance):
                continue
            visited[cy, cx] = True
            img_array[cy, cx, :3] = fill_color
            pixels_filled += 1
            stack.extend([(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)])
        if pixels_filled > 0:
            self.palette_image = Image.fromarray(img_array)
            self.display_canvas_image()
            self.save_to_history()

    def save_to_history(self):
        """OPTIMIZED: Memory-efficient history management"""
        # Remove future history if we're not at the end
        self.history = self.history[:self.history_index + 1]

        # Add new state
        self.history.append(self.palette_image.copy())

        # OPTIMIZED: Keep only last max_history items
        if len(self.history) > self.max_history:
            self.history.pop(0)
        else:
            self.history_index += 1

        self.update_status_bar()

        # Force garbage collection
        gc.collect()

    def save_changes(self):
        self.callback(self.palette_id, self.palette_image)

        if self.auto_save_manager:
            self.auto_save_manager.save_palette(f"{self.palette_id}_final", 
                                               self.palette_image, "palettes")

        messagebox.showinfo("Success", "Changes saved successfully!")
        self.window.destroy()


class LeafBoundaryTool:
    """Boundary extraction + local vein extraction"""
    def __init__(self, cv_image):
        self.original = cv_image
        self.original_rgb = cv2.cvtColor(self.original, cv2.COLOR_BGR2RGB)
        self.height, self.width = self.original_rgb.shape[:2]

        self.boundary_mask = self.extract_boundaries()

        self.boundary_img = np.ones((self.height, self.width, 3), dtype=np.uint8) * 255
        self.boundary_img[self.boundary_mask > 0] = [0, 0, 0]

        self.original_boundary_mask = self.boundary_mask.copy()
        self.original_boundary_img = self.boundary_img.copy()

    def extract_boundaries(self):
        gray = cv2.cvtColor(self.original, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boundary_mask = np.zeros((self.height, self.width), dtype=np.uint8)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            cv2.drawContours(boundary_mask, [largest], -1, 255, 2)
        return boundary_mask

    def extract_local_region(self, x, y):
        gray = cv2.cvtColor(self.original, cv2.COLOR_BGR2GRAY)
        seed_val = int(gray[y, x])
        tol = 15
        lower = max(0, seed_val - tol)
        upper = min(255, seed_val + tol)
        mask = cv2.inRange(gray, lower, upper)
        h, w = gray.shape
        flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
        cv2.floodFill(mask, flood_mask, (x, y), 255)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 10:
                    cv2.drawContours(self.boundary_img, [cnt], -1, (0, 0, 0), 1)
                    cv2.drawContours(self.boundary_mask, [cnt], -1, 255, 1)
            return True
        return False

    def reset_boundaries(self):
        self.boundary_mask = self.original_boundary_mask.copy()
        self.boundary_img = np.ones((self.height, self.width, 3), dtype=np.uint8) * 255
        self.boundary_img[self.boundary_mask > 0] = [0, 0, 0]


class LeafAnalysisTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Leaf Analysis Tool - Optimized & Stable")
        self.root.geometry("1600x900")
        self.root.configure(bg="#2b2b2b")

        self.auto_save_manager = AutoSaveManager()

        self.original_image = None
        self.cv_image = None
        self.zoom_level = 1.0
        self.selected_point = None
        self.selected_rgb = None

        self.palettes_tab1 = {}
        self.palette_counter_tab1 = 0
        self.current_palette_id_tab1 = None
        self.threshold_tab1 = 30
        self.color_separation_expanded = False
        self.selected_palettes = set()

        self.boundary_tool = None
        self.boundary_canvas = None
        self.boundary_photo = None

        self.setup_ui()

    def setup_ui(self):
        # Top menu bar
        menu_bar = tk.Frame(self.root, bg="#1565C0", relief=tk.RAISED, bd=2)
        menu_bar.pack(fill=tk.X, side=tk.TOP)

        tk.Button(menu_bar, text="📁 Setup Auto-Save Folder",
                 command=self.setup_auto_save,
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=10, pady=5)

        tk.Button(menu_bar, text="🔄 Change Save Folder",
                 command=self.change_save_folder,
                 bg="#FF9800", fg="white", font=("Arial", 10, "bold"),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=5, pady=5)

        tk.Button(menu_bar, text="📂 Open Save Folder",
                 command=self.open_save_folder,
                 bg="#2196F3", fg="white", font=("Arial", 10, "bold"),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=5, pady=5)

        self.auto_save_status_label = tk.Label(menu_bar, 
                                               text=self.auto_save_manager.get_status(),
                                               bg="#1565C0", fg="#FFD700",
                                               font=("Arial", 11, "bold"))
        self.auto_save_status_label.pack(side=tk.RIGHT, padx=20, pady=5)

        main_container = tk.Frame(self.root, bg="#2b2b2b")
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.left_panel = tk.Frame(main_container, bg="#363636", relief=tk.RAISED, bd=2, width=500)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5)
        self.left_panel.pack_propagate(False)

        self.setup_shared_left_panel()

        right_container = tk.Frame(main_container, bg="#2b2b2b")
        right_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        self.notebook = ttk.Notebook(right_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=[20, 10], font=('Arial', 11, 'bold'))

        self.tab1 = tk.Frame(self.notebook, bg="#363636")
        self.tab2 = tk.Frame(self.notebook, bg="#363636")

        self.notebook.add(self.tab1, text="🎨 Color Separation")
        self.notebook.add(self.tab2, text="🔍 Boundary Detection")

        self.setup_tab1_color_separation()
        self.setup_tab2_boundary_detection()

    def setup_auto_save(self):
        if self.auto_save_manager.setup_save_folder(self.root):
            self.auto_save_status_label.config(text=self.auto_save_manager.get_status())

    def change_save_folder(self):
        if self.auto_save_manager.change_save_folder(self.root):
            self.auto_save_status_label.config(text=self.auto_save_manager.get_status())

    def open_save_folder(self):
        if self.auto_save_manager.save_folder and os.path.exists(self.auto_save_manager.save_folder):
            if os.name == 'nt':
                os.startfile(self.auto_save_manager.save_folder)
            elif os.name == 'posix':
                os.system(f'open "{self.auto_save_manager.save_folder}"' if os.uname().sysname == 'Darwin' 
                         else f'xdg-open "{self.auto_save_manager.save_folder}"')
        else:
            messagebox.showwarning("No Folder", "Please setup auto-save folder first!")

    def setup_shared_left_panel(self):
        tk.Label(self.left_panel, text="Original Image", bg="#363636", fg="#00E676",
                font=("Arial", 14, "bold")).pack(pady=10)

        canvas_frame = tk.Frame(self.left_panel, bg="#363636")
        canvas_frame.pack(padx=10, pady=5)

        self.canvas = tk.Canvas(canvas_frame, bg="#1e1e1e", width=450, height=400)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_image_click)

        zoom_frame = tk.Frame(self.left_panel, bg="#363636")
        zoom_frame.pack(pady=5)

        tk.Label(zoom_frame, text="Zoom:", bg="#363636", fg="#FFD700",
                font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)

        tk.Button(zoom_frame, text="🔍+", command=self.zoom_in,
                 bg="#4CAF50", fg="white", font=("Arial", 9, "bold"),
                 padx=8, pady=4).pack(side=tk.LEFT, padx=2)

        tk.Button(zoom_frame, text="🔍-", command=self.zoom_out,
                 bg="#FF5722", fg="white", font=("Arial", 9, "bold"),
                 padx=8, pady=4).pack(side=tk.LEFT, padx=2)

        tk.Button(zoom_frame, text="Reset", command=self.zoom_reset,
                 bg="#2196F3", fg="white", font=("Arial", 9, "bold"),
                 padx=8, pady=4).pack(side=tk.LEFT, padx=2)

        self.zoom_label = tk.Label(self.left_panel, text="Zoom: 100%", bg="#363636",
                                   fg="#00E676", font=("Arial", 10, "bold"))
        self.zoom_label.pack(pady=2)

        button_frame = tk.Frame(self.left_panel, bg="#363636")
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="📷 Scan", command=self.scan_leaf,
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                 padx=12, pady=6).pack(side=tk.LEFT, padx=5)

        tk.Button(button_frame, text="📁 Upload", command=self.upload_image,
                 bg="#2196F3", fg="white", font=("Arial", 10, "bold"),
                 padx=12, pady=6).pack(side=tk.LEFT, padx=5)

        self.rgb_label = tk.Label(self.left_panel, text="RGB: Not Selected", bg="#363636",
                                 fg="#FFD700", font=("Arial", 11, "bold"))
        self.rgb_label.pack(pady=3)

        self.point_label = tk.Label(self.left_panel, text="Point: Not Selected", bg="#363636",
                                   fg="#00E676", font=("Arial", 10, "bold"))
        self.point_label.pack(pady=2)

    def setup_tab1_color_separation(self):
        control_header = tk.Frame(self.tab1, bg="#4CAF50")
        control_header.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(control_header, text="🎨 Color-Based Separation", bg="#4CAF50", fg="white",
                font=("Arial", 12, "bold")).pack(pady=8)

        dropdown_btn_frame = tk.Frame(self.tab1, bg="#f0f0f0")
        dropdown_btn_frame.pack(fill=tk.X, padx=10, pady=5)

        self.color_sep_toggle_btn = tk.Button(dropdown_btn_frame, 
                                              text="▶ Color Separation Controls (Click to Expand)",
                                              command=self.toggle_color_separation_controls,
                                              bg="#2196F3", fg="white", font=("Arial", 10, "bold"),
                                              anchor="w", padx=10, pady=8)
        self.color_sep_toggle_btn.pack(fill=tk.X)

        self.controls_frame = tk.Frame(self.tab1, bg="#f0f0f0")

        threshold_frame = tk.Frame(self.controls_frame, bg="#f0f0f0")
        threshold_frame.pack(pady=8, padx=10, fill=tk.X)

        tk.Label(threshold_frame, text="RGB Threshold:", bg="#f0f0f0", fg="#000000",
                font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=3)

        self.threshold_var_tab1 = tk.IntVar(value=30)
        threshold_slider = ttk.Scale(threshold_frame, from_=0, to=100,
                                    variable=self.threshold_var_tab1, orient=tk.HORIZONTAL,
                                    command=self.update_threshold_tab1)
        threshold_slider.pack(fill=tk.X, pady=3)

        self.threshold_label_tab1 = tk.Label(threshold_frame, text="Value: 30", bg="#f0f0f0",
                                       fg="#000000", font=("Arial", 9, "bold"))
        self.threshold_label_tab1.pack(anchor=tk.W)

        sep_frame = tk.Frame(self.controls_frame, bg="#f0f0f0")
        sep_frame.pack(pady=8, padx=10, fill=tk.X)

        tk.Button(sep_frame, text="🌍 Global Separation",
                 command=self.global_separation_tab1,
                 bg="#FF5722", fg="white", font=("Arial", 10, "bold"),
                 padx=10, pady=8).pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)

        tk.Button(sep_frame, text="📍 Local Separation",
                 command=self.local_separation_tab1,
                 bg="#9C27B0", fg="white", font=("Arial", 10, "bold"),
                 padx=10, pady=8).pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)

        ttk.Separator(self.tab1, orient='horizontal').pack(fill=tk.X, padx=5, pady=10)

        palette_ops_header = tk.Frame(self.tab1, bg="#363636")
        palette_ops_header.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(palette_ops_header, text="Color Palettes", bg="#363636",
                fg="#00E676", font=("Arial", 13, "bold")).pack(side=tk.LEFT)

        ops_btn_frame = tk.Frame(palette_ops_header, bg="#363636")
        ops_btn_frame.pack(side=tk.RIGHT)

        tk.Button(ops_btn_frame, text="🔗 Merge Selected",
                 command=self.merge_selected_palettes,
                 bg="#00BCD4", fg="white", font=("Arial", 8, "bold"),
                 padx=8, pady=4).pack(side=tk.LEFT, padx=2)

        tk.Button(ops_btn_frame, text="🔗 Merge All",
                 command=self.merge_all_palettes,
                 bg="#FF9800", fg="white", font=("Arial", 8, "bold"),
                 padx=8, pady=4).pack(side=tk.LEFT, padx=2)

        tk.Button(ops_btn_frame, text="⊕ XOR Selected",
                 command=self.xor_selected_palettes,
                 bg="#9C27B0", fg="white", font=("Arial", 8, "bold"),
                 padx=8, pady=4).pack(side=tk.LEFT, padx=2)

        tk.Button(ops_btn_frame, text="Clear All",
                 command=self.clear_all_palettes_tab1,
                 bg="#F44336", fg="white", font=("Arial", 8, "bold"),
                 padx=8, pady=4).pack(side=tk.LEFT, padx=2)

        palette_container = tk.Frame(self.tab1, bg="#2b2b2b")
        palette_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        palette_canvas = tk.Canvas(palette_container, bg="#2b2b2b")
        palette_scrollbar = ttk.Scrollbar(palette_container, orient="vertical",
                                         command=palette_canvas.yview)

        self.palette_frame_tab1 = tk.Frame(palette_canvas, bg="#2b2b2b")
        self.palette_frame_tab1.bind("<Configure>",
                               lambda e: palette_canvas.configure(scrollregion=palette_canvas.bbox("all")))

        palette_canvas.create_window((0, 0), window=self.palette_frame_tab1, anchor="nw")
        palette_canvas.configure(yscrollcommand=palette_scrollbar.set)

        palette_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        palette_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.palette_grid_row = 0
        self.palette_grid_col = 0

    def toggle_color_separation_controls(self):
        if self.color_separation_expanded:
            self.controls_frame.pack_forget()
            self.color_sep_toggle_btn.config(text="▶ Color Separation Controls (Click to Expand)")
            self.color_separation_expanded = False
        else:
            self.controls_frame.pack(fill=tk.X, padx=10, pady=5, after=self.color_sep_toggle_btn.master)
            self.color_sep_toggle_btn.config(text="▼ Color Separation Controls (Click to Collapse)")
            self.color_separation_expanded = True

    def setup_tab2_boundary_detection(self):
        control_header = tk.Frame(self.tab2, bg="#FF6F00")
        control_header.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(control_header, text="🔍 Leaf Boundary & Vein Extractor", 
                bg="#FF6F00", fg="white",
                font=("Arial", 12, "bold")).pack(pady=8)

        info_frame = tk.Frame(self.tab2, bg="#E3F2FD", relief=tk.RAISED, bd=2)
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        info_text = ("📝 WORKFLOW:\n" +
                    "1. Upload scanned leaf image\n" +
                    "2. Click 'Extract Boundaries' to get outer boundary\n" +
                    "3. Click on LEFT ORIGINAL IMAGE on vein/midrib/stem\n" +
                    "4. Click 'Local Extraction' to add that structure to boundary\n" +
                    "5. Repeat steps 3-4, then Save Result")
        tk.Label(info_frame, text=info_text, bg="#E3F2FD", fg="#000000",
                font=("Arial", 9), justify=tk.LEFT).pack(pady=10, padx=10)

        controls_frame = tk.Frame(self.tab2, bg="#f0f0f0")
        controls_frame.pack(fill=tk.X, padx=10, pady=10)

        btn_frame = tk.Frame(controls_frame, bg="#f0f0f0")
        btn_frame.pack(pady=5)

        tk.Button(btn_frame, text="🔍 Extract Boundaries",
                 command=self.extract_boundaries_tab2,
                 bg="#FF5722", fg="white", font=("Arial", 10, "bold"),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=3)

        tk.Button(btn_frame, text="📍 Local Extraction",
                 command=self.local_extraction_tab2,
                 bg="#03A9F4", fg="white", font=("Arial", 10, "bold"),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=3)

        tk.Button(btn_frame, text="🔄 Reset Boundaries",
                 command=self.reset_boundaries_tab2,
                 bg="#9C27B0", fg="white", font=("Arial", 10, "bold"),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=3)

        tk.Button(btn_frame, text="💾 Save Result",
                 command=self.save_boundary_result_tab2,
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                 padx=15, pady=8).pack(side=tk.LEFT, padx=3)

        ttk.Separator(self.tab2, orient='horizontal').pack(fill=tk.X, padx=5, pady=10)

        display_container = tk.Frame(self.tab2, bg="#2b2b2b")
        display_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        display_canvas = tk.Canvas(display_container, bg="#2b2b2b")
        v_scrollbar = ttk.Scrollbar(display_container, orient="vertical", command=display_canvas.yview)
        h_scrollbar = ttk.Scrollbar(display_container, orient="horizontal", command=display_canvas.xview)

        self.display_frame_tab2 = tk.Frame(display_canvas, bg="#2b2b2b")
        self.display_frame_tab2.bind("<Configure>",
                               lambda e: display_canvas.configure(scrollregion=display_canvas.bbox("all")))

        display_canvas.create_window((0, 0), window=self.display_frame_tab2, anchor="nw")
        display_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        display_canvas.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        display_container.grid_rowconfigure(0, weight=1)
        display_container.grid_columnconfigure(0, weight=1)

        result_frame = tk.LabelFrame(self.display_frame_tab2, text="Extracted Boundaries + Veins", 
                                    bg="#f0f0f0", fg="#000000",
                                    font=("Arial", 12, "bold"))
        result_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.boundary_canvas = tk.Canvas(result_frame, bg="#1e1e1e", width=900, height=700)
        self.boundary_canvas.pack(padx=20, pady=20)

    def upload_image(self):
        file_path = filedialog.askopenfilename(
            title="Select Leaf Image",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp"), ("All Files", "*.*")]
        )

        if file_path:
            self.original_image = Image.open(file_path)
            self.cv_image = cv2.cvtColor(np.array(self.original_image), cv2.COLOR_RGB2BGR)
            self.zoom_level = 1.0
            self.selected_point = None
            self.display_image_on_canvas()

    def scan_leaf(self):
        messagebox.showinfo("Scanner", "Scanner functionality - use Upload for now")
        self.upload_image()

    def display_image_on_canvas(self):
        if self.original_image:
            img_copy = self.original_image.copy()

            new_size = (int(img_copy.width * self.zoom_level),
                       int(img_copy.height * self.zoom_level))
            img_copy = img_copy.resize(new_size, Image.Resampling.LANCZOS)

            if self.selected_point:
                draw = ImageDraw.Draw(img_copy)
                x, y = self.selected_point

                x_scaled = int(x * self.zoom_level)
                y_scaled = int(y * self.zoom_level)

                pointer_size = 15
                line_width = 3

                draw.line([(x_scaled - pointer_size, y_scaled),
                          (x_scaled + pointer_size, y_scaled)],
                         fill='red', width=line_width)
                draw.line([(x_scaled, y_scaled - pointer_size),
                          (x_scaled, y_scaled + pointer_size)],
                         fill='red', width=line_width)

                draw.ellipse([(x_scaled - 8, y_scaled - 8),
                             (x_scaled + 8, y_scaled + 8)],
                            outline='yellow', width=2)

            img_copy.thumbnail((430, 380), Image.Resampling.LANCZOS)

            self.display_image = img_copy
            self.photo_image = ImageTk.PhotoImage(img_copy)

            self.canvas.delete("all")
            self.canvas.create_image(225, 200, image=self.photo_image)

            self.zoom_label.config(text=f"Zoom: {int(self.zoom_level * 100)}%")

    def on_image_click(self, event):
        if self.original_image is None:
            return

        x, y = event.x, event.y
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if self.display_image:
            img_width, img_height = self.display_image.size
            x_offset = (canvas_width - img_width) // 2
            y_offset = (canvas_height - img_height) // 2
            img_x = x - x_offset
            img_y = y - y_offset

            if 0 <= img_x < img_width and 0 <= img_y < img_height:
                scale_x = self.original_image.width / (img_width / self.zoom_level)
                scale_y = self.original_image.height / (img_height / self.zoom_level)

                orig_x = int((img_x / self.zoom_level) * scale_x)
                orig_y = int((img_y / self.zoom_level) * scale_y)

                orig_x = max(0, min(self.original_image.width - 1, orig_x))
                orig_y = max(0, min(self.original_image.height - 1, orig_y))

                self.selected_point = (orig_x, orig_y)

                pixel = self.original_image.getpixel((orig_x, orig_y))
                if isinstance(pixel, int):
                    self.selected_rgb = (pixel, pixel, pixel)
                else:
                    self.selected_rgb = pixel[:3]

                self.rgb_label.config(text=f"RGB: {self.selected_rgb}")
                self.point_label.config(text=f"Point: ({orig_x}, {orig_y})")

                self.display_image_on_canvas()

    def zoom_in(self):
        if self.original_image:
            self.zoom_level = min(3.0, self.zoom_level + 0.25)
            self.display_image_on_canvas()

    def zoom_out(self):
        if self.original_image:
            self.zoom_level = max(0.5, self.zoom_level - 0.25)
            self.display_image_on_canvas()

    def zoom_reset(self):
        if self.original_image:
            self.zoom_level = 1.0
            self.display_image_on_canvas()

    def update_threshold_tab1(self, value):
        self.threshold_tab1 = int(float(value))
        self.threshold_label_tab1.config(text=f"Value: {self.threshold_tab1}")

    def global_separation_tab1(self):
        if self.original_image is None or self.selected_rgb is None:
            messagebox.showwarning("Error", "Please upload image and select a color first.")
            return

        img_array = np.array(self.original_image)
        lower_bound = np.array([max(0, c - self.threshold_tab1) for c in self.selected_rgb])
        upper_bound = np.array([min(255, c + self.threshold_tab1) for c in self.selected_rgb])

        mask = cv2.inRange(img_array, lower_bound, upper_bound)
        separated = cv2.bitwise_and(img_array, img_array, mask=mask)

        white_bg = np.ones_like(img_array) * 255
        white_bg[mask > 0] = separated[mask > 0]

        self.palette_counter_tab1 += 1
        palette_id = f"RGB{self.selected_rgb}_Palette_{self.palette_counter_tab1}"
        self.palettes_tab1[palette_id] = Image.fromarray(white_bg.astype(np.uint8))
        self.current_palette_id_tab1 = palette_id

        if self.auto_save_manager:
            self.auto_save_manager.save_palette(palette_id, self.palettes_tab1[palette_id])

        self.add_palette_to_display_tab1(palette_id)
        messagebox.showinfo("Success", f"{palette_id} created!")

    def local_separation_tab1(self):
        if not self.palettes_tab1 or self.selected_rgb is None:
            messagebox.showwarning("Error", "Create a palette first and select a color.")
            return

        if self.current_palette_id_tab1 is None:
            self.current_palette_id_tab1 = list(self.palettes_tab1.keys())[-1]

        current_palette_array = np.array(self.palettes_tab1[self.current_palette_id_tab1])
        img_array = np.array(self.original_image)

        lower_bound = np.array([max(0, c - self.threshold_tab1) for c in self.selected_rgb])
        upper_bound = np.array([min(255, c + self.threshold_tab1) for c in self.selected_rgb])

        mask = cv2.inRange(img_array, lower_bound, upper_bound)
        new_separated = cv2.bitwise_and(img_array, img_array, mask=mask)
        current_palette_array[mask > 0] = new_separated[mask > 0]

        self.palettes_tab1[self.current_palette_id_tab1] = Image.fromarray(current_palette_array.astype(np.uint8))

        if self.auto_save_manager:
            self.auto_save_manager.save_palette(self.current_palette_id_tab1, 
                                               self.palettes_tab1[self.current_palette_id_tab1])

        self.refresh_palette_display_tab1()

    def add_palette_to_display_tab1(self, palette_id):
        palette_item = tk.Frame(self.palette_frame_tab1, bg="#363636", relief=tk.RAISED, bd=3)
        palette_item.grid(row=self.palette_grid_row, column=self.palette_grid_col, 
                         padx=5, pady=5, sticky="nsew")

        self.palette_frame_tab1.grid_columnconfigure(0, weight=1)
        self.palette_frame_tab1.grid_columnconfigure(1, weight=1)

        header = tk.Frame(palette_item, bg="#4CAF50")
        header.pack(fill=tk.X)

        var = tk.BooleanVar()
        checkbox = tk.Checkbutton(header, variable=var, bg="#4CAF50",
                                  command=lambda: self.toggle_palette_selection(palette_id, var))
        checkbox.pack(side=tk.LEFT, padx=5)

        tk.Label(header, text=palette_id, bg="#4CAF50", fg="white",
                font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5, pady=8)

        thumb = self.palettes_tab1[palette_id].copy()
        thumb.thumbnail((350, 250), Image.Resampling.LANCZOS)
        thumb_photo = ImageTk.PhotoImage(thumb)

        thumb_label = tk.Label(palette_item, image=thumb_photo, bg="#1e1e1e", bd=2, relief=tk.SUNKEN)
        thumb_label.image = thumb_photo
        thumb_label.pack(padx=10, pady=10)

        btn_frame = tk.Frame(palette_item, bg="#363636")
        btn_frame.pack(pady=8)

        tk.Button(btn_frame, text="✏️ Rename",
                 command=lambda: self.rename_palette_tab1(palette_id),
                 bg="#03A9F4", fg="white", font=("Arial", 8, "bold"),
                 padx=6, pady=4).pack(side=tk.LEFT, padx=2)

        tk.Button(btn_frame, text="🎨 Edit",
                 command=lambda: self.edit_palette_tab1(palette_id),
                 bg="#FF9800", fg="white", font=("Arial", 8, "bold"),
                 padx=6, pady=4).pack(side=tk.LEFT, padx=2)

        tk.Button(btn_frame, text="⬇ Download",
                 command=lambda: self.download_palette_tab1(palette_id),
                 bg="#2196F3", fg="white", font=("Arial", 8, "bold"),
                 padx=6, pady=4).pack(side=tk.LEFT, padx=2)

        tk.Button(btn_frame, text="🗑️ Delete",
                 command=lambda: self.delete_palette_tab1(palette_id),
                 bg="#F44336", fg="white", font=("Arial", 8, "bold"),
                 padx=6, pady=4).pack(side=tk.LEFT, padx=2)

        self.palette_grid_col += 1
        if self.palette_grid_col >= 2:
            self.palette_grid_col = 0
            self.palette_grid_row += 1

    def toggle_palette_selection(self, palette_id, var):
        if var.get():
            self.selected_palettes.add(palette_id)
        else:
            self.selected_palettes.discard(palette_id)

    def rename_palette_tab1(self, old_id):
        new_name = simpledialog.askstring("Rename Palette", 
                                          f"Enter new name for {old_id}:",
                                          initialvalue=old_id)
        if new_name and new_name != old_id:
            if new_name in self.palettes_tab1:
                messagebox.showerror("Error", f"Name '{new_name}' already exists!")
                return

            self.palettes_tab1[new_name] = self.palettes_tab1.pop(old_id)
            if self.current_palette_id_tab1 == old_id:
                self.current_palette_id_tab1 = new_name
            if old_id in self.selected_palettes:
                self.selected_palettes.remove(old_id)
                self.selected_palettes.add(new_name)

            self.refresh_palette_display_tab1()
            messagebox.showinfo("Success", f"Renamed to {new_name}")

    def delete_palette_tab1(self, palette_id):
        if messagebox.askyesno("Confirm Delete", f"Delete {palette_id}?"):
            del self.palettes_tab1[palette_id]
            self.selected_palettes.discard(palette_id)
            if self.current_palette_id_tab1 == palette_id:
                self.current_palette_id_tab1 = None
            self.refresh_palette_display_tab1()

    def download_palette_tab1(self, palette_id):
        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"{palette_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg")]
        )
        if save_path:
            self.palettes_tab1[palette_id].save(save_path)
            messagebox.showinfo("Success", "Saved!")

    def merge_selected_palettes(self):
        if len(self.selected_palettes) < 2:
            messagebox.showwarning("Error", "Select at least 2 palettes to merge!")
            return

        selected_list = list(self.selected_palettes)
        base_image = self.palettes_tab1[selected_list[0]]
        merged_array = np.array(base_image)

        for palette_id in selected_list[1:]:
            palette_array = np.array(self.palettes_tab1[palette_id])
            mask = ~np.all(palette_array == 255, axis=2)
            merged_array[mask] = palette_array[mask]

        self.palette_counter_tab1 += 1
        merged_id = f"Merged_Selected_{self.palette_counter_tab1}"
        self.palettes_tab1[merged_id] = Image.fromarray(merged_array.astype(np.uint8))

        if self.auto_save_manager:
            self.auto_save_manager.save_palette(merged_id, self.palettes_tab1[merged_id], "merged")

        self.selected_palettes.clear()
        self.refresh_palette_display_tab1()
        messagebox.showinfo("Success", f"✅ {merged_id} created from {len(selected_list)} selected palettes!")

    def merge_all_palettes(self):
        if len(self.palettes_tab1) < 2:
            messagebox.showwarning("Error", "Need at least 2 palettes to merge!")
            return

        first_id = list(self.palettes_tab1.keys())[0]
        base_image = self.palettes_tab1[first_id]
        merged_array = np.array(base_image)

        for palette_id in list(self.palettes_tab1.keys())[1:]:
            palette_array = np.array(self.palettes_tab1[palette_id])
            mask = ~np.all(palette_array == 255, axis=2)
            merged_array[mask] = palette_array[mask]

        self.palette_counter_tab1 += 1
        merged_id = f"Merged_All_{self.palette_counter_tab1}"
        self.palettes_tab1[merged_id] = Image.fromarray(merged_array.astype(np.uint8))

        if self.auto_save_manager:
            self.auto_save_manager.save_palette(merged_id, self.palettes_tab1[merged_id], "merged")

        self.refresh_palette_display_tab1()
        messagebox.showinfo("Success", f"✅ {merged_id} created from all palettes!")

    def xor_selected_palettes(self):
        if len(self.selected_palettes) < 1:
            messagebox.showwarning("Error", "Select at least 1 palette for XOR!")
            return

        if self.original_image is None:
            messagebox.showwarning("Error", "Need original image for XOR!")
            return

        selected_list = list(self.selected_palettes)
        merged_array = np.array(self.palettes_tab1[selected_list[0]])

        for palette_id in selected_list[1:]:
            palette_array = np.array(self.palettes_tab1[palette_id])
            mask = ~np.all(palette_array == 255, axis=2)
            merged_array[mask] = palette_array[mask]

        orig_array = np.array(self.original_image)
        merged_mask = ~np.all(merged_array == 255, axis=2)
        xor_array = orig_array.copy()
        xor_array[merged_mask] = [255, 255, 255]

        self.palette_counter_tab1 += 1
        xor_id = f"XOR_Selected_{self.palette_counter_tab1}"
        self.palettes_tab1[xor_id] = Image.fromarray(xor_array.astype(np.uint8))

        if self.auto_save_manager:
            self.auto_save_manager.save_palette(xor_id, self.palettes_tab1[xor_id], "merged")

        self.selected_palettes.clear()
        self.refresh_palette_display_tab1()
        messagebox.showinfo("Success", f"✅ {xor_id} created (original - selected palettes)")

    def edit_palette_tab1(self, palette_id):
        editor = PaletteEditor(self.root, self.palettes_tab1[palette_id], palette_id, 
                              lambda pid, img: self.update_palette_tab1(pid, img),
                              self.auto_save_manager)

    def update_palette_tab1(self, palette_id, updated_image):
        self.palettes_tab1[palette_id] = updated_image
        self.refresh_palette_display_tab1()

    def clear_all_palettes_tab1(self):
        if self.palettes_tab1 and messagebox.askyesno("Confirm", "Delete all palettes?"):
            self.palettes_tab1.clear()
            self.palette_counter_tab1 = 0
            self.current_palette_id_tab1 = None
            self.selected_palettes.clear()
            self.refresh_palette_display_tab1()

    def refresh_palette_display_tab1(self):
        for widget in self.palette_frame_tab1.winfo_children():
            widget.destroy()

        self.selected_palettes.clear()
        self.palette_grid_row = 0
        self.palette_grid_col = 0

        for palette_id in self.palettes_tab1.keys():
            self.add_palette_to_display_tab1(palette_id)

    def extract_boundaries_tab2(self):
        if self.cv_image is None:
            messagebox.showwarning("Error", "Please upload/scan a leaf image first.")
            return

        self.boundary_tool = LeafBoundaryTool(self.cv_image)
        self.update_boundary_display_tab2()

        if self.auto_save_manager:
            self.auto_save_manager.save_cv_image("boundary_initial", 
                                                 cv2.cvtColor(self.boundary_tool.boundary_img, cv2.COLOR_RGB2BGR))

    def local_extraction_tab2(self):
        if self.boundary_tool is None:
            return
        if self.selected_point is None:
            return

        x, y = self.selected_point
        ok = self.boundary_tool.extract_local_region(x, y)
        self.update_boundary_display_tab2()

        if self.auto_save_manager and ok:
            self.auto_save_manager.save_cv_image("boundary_local", 
                                                 cv2.cvtColor(self.boundary_tool.boundary_img, cv2.COLOR_RGB2BGR))

    def update_boundary_display_tab2(self):
        if self.boundary_tool is None:
            return

        boundary_img = Image.fromarray(self.boundary_tool.boundary_img)
        boundary_img.thumbnail((880, 680), Image.Resampling.LANCZOS)

        self.boundary_photo = ImageTk.PhotoImage(boundary_img)
        self.boundary_canvas.delete("all")
        self.boundary_canvas.create_image(450, 350, image=self.boundary_photo)

    def reset_boundaries_tab2(self):
        if self.boundary_tool is None:
            return
        self.boundary_tool.reset_boundaries()
        self.update_boundary_display_tab2()

    def save_boundary_result_tab2(self):
        if self.boundary_tool is None:
            messagebox.showwarning("Error", "Extract boundaries first.")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"leaf_boundaries_veins_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg")]
        )

        if save_path:
            cv2.imwrite(save_path, cv2.cvtColor(self.boundary_tool.boundary_img, cv2.COLOR_RGB2BGR))

            if self.auto_save_manager:
                self.auto_save_manager.save_cv_image("boundary_final", 
                                                     cv2.cvtColor(self.boundary_tool.boundary_img, cv2.COLOR_RGB2BGR))

            messagebox.showinfo("Success", f"✅ Saved to:\n{save_path}")


def main():
    root = tk.Tk()
    app = LeafAnalysisTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()