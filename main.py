import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

import backend

class RasterTraceEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("RasterTrace Editor")
        self.root.geometry("1200x800")
        self.root.minsize(850, 750)
        
        # Theme
        self.root.tk.call("source", "themes/forest-light.tcl")
        ttk.Style().theme_use("forest-light")
        
        # Memory
        self.zoom = 1.0
        self.offset_x = self.offset_y = 0
        self.current_image = None
        self.image_tk = None
        self.img_x = self.img_y = 0
        self.img_w = self.img_h = 100
        self.drag_start = None
        self.drag_mode = None
        self.resize_handle = None
        self.handles = []
        
        # User Config Variables
        self.bed_x = tk.StringVar(value="200")
        self.bed_y = tk.StringVar(value="150")
        self.pen_x = tk.StringVar(value="0")
        self.pen_y = tk.StringVar(value="0")
        self.pen_down = tk.StringVar(value="1.0")
        self.pen_up = tk.StringVar(value="2.0")
        self.pen_thickness = tk.StringVar(value="1")
        self.pen_safety = tk.StringVar(value="10")
        
        self.bed_x.trace_add("write", lambda *a: (self.draw(), backend._resetPlan()))
        self.bed_y.trace_add("write", lambda *a: (self.draw(), backend._resetPlan()))
        
        self.setup_ui()
        
    def setup_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Sidebar Left
        left = ttk.LabelFrame(main, text="Image Selection", padding=10)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left.configure(width=200)
        left.pack_propagate(False)
        
        ttk.Button(left, text="Load Image", command=self.load_image).pack(fill=tk.X, pady=(0, 10))
        
        info = ttk.LabelFrame(left, text="Image Info", padding=5)
        info.pack(fill=tk.X, pady=(0, 10))
        self.img_name = ttk.Label(info, text="No image loaded")
        self.img_name.pack(anchor=tk.W)
        self.img_size = ttk.Label(info, text="")
        self.img_size.pack(anchor=tk.W)
        
        ttk.Button(left, text="Clear Image", command=self.clear_image).pack(fill=tk.X)
        
        copyright_frame = ttk.Frame(left)
        copyright_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        copyright_label = ttk.Label(copyright_frame, text="github.com/toni08bit",
                                   font=("TkDefaultFont", 8),
                                   foreground="#7f8c8d")
        copyright_label.pack(anchor=tk.CENTER)
        
        # Main Canvas Center
        center = ttk.Frame(main)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.canvas = tk.Canvas(center, bg="#f0f0f0")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Configure>", lambda e: self.draw())
        
        # Center Zoom
        zoom = ttk.Frame(center)
        zoom.pack(fill=tk.X, pady=(5, 0))
        
        zoom_info = ttk.Frame(zoom)
        zoom_info.pack(side=tk.LEFT)
        ttk.Label(zoom_info, text="Zoom:", font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT)
        self.zoom_label = ttk.Label(zoom_info, text="100%", font=("TkDefaultFont", 9),
                                   foreground=backend.BACKGROUND_COLORS["ok"], padding=(5, 0))
        self.zoom_label.pack(side=tk.LEFT)
        
        btn_frame = ttk.Frame(zoom)
        btn_frame.pack(side=tk.LEFT, padx=(10, 0))
        
        zoom_out_btn = ttk.Button(btn_frame, text="🔍 -", command=self.zoom_out, width=4)
        zoom_out_btn.pack(side=tk.LEFT, padx=(0, 1))
        
        zoom_in_btn = ttk.Button(btn_frame, text="🔍 +", command=self.zoom_in, width=4)
        zoom_in_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        ttk.Button(zoom, text="Fit", command=self.fit_bed, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom, text="Reset", command=self.reset_zoom, width=8).pack(side=tk.LEFT, padx=2)
        
        # Sidebar Right
        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right.configure(width=250)
        right.pack_propagate(False)
        
        # Right Config
        config = ttk.LabelFrame(right, text="Configuration", padding=10)
        config.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(config, text="Bed Size (mm):").pack(anchor=tk.W)
        bed = ttk.Frame(config)
        bed.pack(fill=tk.X, pady=(2, 8))
        ttk.Label(bed, text="X:").pack(side=tk.LEFT)
        ttk.Entry(bed, textvariable=self.bed_x, width=8).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(bed, text="Y:").pack(side=tk.LEFT)
        ttk.Entry(bed, textvariable=self.bed_y, width=8).pack(side=tk.LEFT, padx=2)

        self.bed_x.trace_add("write", lambda *a: backend._resetPlan())
        self.bed_y.trace_add("write", lambda *a: backend._resetPlan())
        
        ttk.Label(config, text="Pen Offset (mm):").pack(anchor=tk.W)
        pen_offset = ttk.Frame(config)
        pen_offset.pack(fill=tk.X, pady=(2, 8))
        ttk.Label(pen_offset, text="X:").pack(side=tk.LEFT)
        ttk.Entry(pen_offset, textvariable=self.pen_x, width=8).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(pen_offset, text="Y:").pack(side=tk.LEFT)
        ttk.Entry(pen_offset, textvariable=self.pen_y, width=8).pack(side=tk.LEFT, padx=2)
        
        self.pen_x.trace_add("write", lambda *a: backend._resetPlan())
        self.pen_y.trace_add("write", lambda *a: backend._resetPlan())
        
        ttk.Label(config, text="Pen Z (mm):").pack(anchor=tk.W)
        pen_z_frame = ttk.Frame(config)
        pen_z_frame.pack(fill=tk.X, pady=(2, 8))
        ttk.Label(pen_z_frame, text="U:").pack(side=tk.LEFT)
        ttk.Entry(pen_z_frame, textvariable=self.pen_up, width=8).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(pen_z_frame, text="D:").pack(side=tk.LEFT)
        ttk.Entry(pen_z_frame, textvariable=self.pen_down, width=8).pack(side=tk.LEFT, padx=2)
        
        self.pen_up.trace_add("write", lambda *a: backend._resetPlan())
        self.pen_down.trace_add("write", lambda *a: backend._resetPlan())

        ttk.Label(config, text="Pen Boundary (mm):").pack(anchor=tk.W)
        pen_boundary_frame = ttk.Frame(config)
        pen_boundary_frame.pack(fill=tk.X, pady=(2, 8))
        ttk.Label(pen_boundary_frame, text="T:").pack(side=tk.LEFT)
        ttk.Entry(pen_boundary_frame, textvariable=self.pen_thickness, width=8).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(pen_boundary_frame, text="S:").pack(side=tk.LEFT)
        ttk.Entry(pen_boundary_frame, textvariable=self.pen_safety, width=8).pack(side=tk.LEFT, padx=2)
        
        self.pen_thickness.trace_add("write", lambda *a: backend._resetPlan())
        self.pen_safety.trace_add("write", lambda *a: backend._resetPlan())

        # Right Planning
        planning = ttk.LabelFrame(right, text="Planning", padding=10)
        planning.pack(fill=tk.BOTH, expand=True)
        
        status_box = ttk.LabelFrame(planning, text="Status", padding=8)
        status_box.pack(fill=tk.X, pady=(0, 10))
        
        status_items = ttk.Frame(status_box)
        status_items.pack(fill=tk.X)
        
        planned_frame = ttk.Frame(status_items)
        planned_frame.pack(fill=tk.X, pady=1)
        ttk.Label(planned_frame, text="Planned:", font=("TkDefaultFont", 9)).pack(side=tk.LEFT)
        self.planned_label = ttk.Label(planned_frame, text="No", font=("TkDefaultFont", 9, "bold"),
                                      foreground=backend.FOREGROUND_COLORS["error"])
        self.planned_label.pack(side=tk.RIGHT)
        
        serial_frame = ttk.Frame(status_items)
        serial_frame.pack(fill=tk.X, pady=1)
        ttk.Label(serial_frame, text="Serial:", font=("TkDefaultFont", 9)).pack(side=tk.LEFT)
        self.serial_label = ttk.Label(serial_frame, text="Not Connected", font=("TkDefaultFont", 9, "bold"),
                                     foreground=backend.FOREGROUND_COLORS["neutral"])
        self.serial_label.pack(side=tk.RIGHT)
        
        self.progress = ttk.Progressbar(status_box, value=0)
        self.progress.pack(fill=tk.X, pady=(8, 4))
        
        progress_frame = ttk.Frame(status_box)
        progress_frame.pack(fill=tk.X, pady=1)
        ttk.Label(progress_frame, text="Progress:", font=("TkDefaultFont", 9)).pack(side=tk.LEFT)
        self.progress_label = ttk.Label(progress_frame, text="0%", font=("TkDefaultFont", 9, "bold"),
                                       foreground=backend.FOREGROUND_COLORS["neutral"])
        self.progress_label.pack(side=tk.RIGHT)
        
        eta_frame = ttk.Frame(status_box)
        eta_frame.pack(fill=tk.X, pady=1)
        ttk.Label(eta_frame, text="ETA:", font=("TkDefaultFont", 9)).pack(side=tk.LEFT)
        self.eta_label = ttk.Label(eta_frame, text="-", font=("TkDefaultFont", 9, "bold"),
                                  foreground=backend.FOREGROUND_COLORS["neutral"])
        self.eta_label.pack(side=tk.RIGHT)
        
        self.create_plan_btn = ttk.Button(planning, text="Create Plan",
                                         command=backend._createPlanBtn, style="Accent.TButton")
        self.create_plan_btn.pack(fill=tk.X, pady=(0, 5))
        
        self.connect_serial_btn = ttk.Button(planning, text="Connect Serial",
                                           command=backend._connectSerialBtn)
        self.connect_serial_btn.pack(fill=tk.X, pady=(0, 5))
        
        self.begin_motion_btn = ttk.Button(planning, text="Begin Motion",
                                         command=backend._beginMotionBtn, style="Accent.TButton")
        self.begin_motion_btn.pack(fill=tk.X)
        
        # Right G-Code Buttons
        ttk.Button(planning, text="Save G-Code",
                  command=backend._saveGcodeBtn).pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(planning, text="Copy G-Code",
                  command=backend._copyGcodeBtn).pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 5))
        

        # Backend References
        backend._ui_refs = {
            "planned_label": self.planned_label,
            "serial_label": self.serial_label,
            "progress_bar": self.progress,
            "progress_label": self.progress_label,
            "eta_label": self.eta_label,
            "create_plan_btn": self.create_plan_btn,
            "connect_serial_btn": self.connect_serial_btn,
            "begin_motion_btn": self.begin_motion_btn,
            "canvas": self.canvas,
            "app": self
        }
        
        self.root.after(100, self.draw)
        
    def to_canvas(self, x, y):
        """Workspace -> Canvas Coordinates"""
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        return (x * self.zoom + w/2 + self.offset_x, y * self.zoom + h/2 + self.offset_y)
    
    def to_workspace(self, cx, cy):
        """Canvas -> Workspace Coordinates"""
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        return ((cx - w/2 - self.offset_x) / self.zoom, (cy - h/2 - self.offset_y) / self.zoom)
    
    def get_bed_size(self):
        """Bed Dimensions + Fallback"""
        try:
            return max(float(self.bed_x.get()), 10), max(float(self.bed_y.get()), 10)
        except:
            return 200, 200
    
    def draw(self):
        self.canvas.delete("all")
        self.draw_bed()
        if self.current_image:
            self.draw_image()
            self.draw_handles()

    
    def draw_bed(self):
        bx, by = self.get_bed_size()
        x1, y1 = self.to_canvas(-bx/2, -by/2)
        x2, y2 = self.to_canvas(bx/2, by/2)
        
        self.canvas.create_rectangle(x1, y1, x2, y2, outline="#666", width=2, dash=(8, 4))
        
        # Center crosshair
        cx, cy = self.to_canvas(0, 0)
        self.canvas.create_line(cx-10, cy, cx+10, cy, fill="#999")
        self.canvas.create_line(cx, cy-10, cx, cy+10, fill="#999")
        
    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff")])
        
        if path:
            try:
                self.current_image = Image.open(path)
                self.img_x = self.img_y = 0
                
                # Auto-size to fit bed
                bx, by = self.get_bed_size()
                ratio = self.current_image.width / self.current_image.height
                if ratio > 1:
                    self.img_w = min(bx * 0.8, 100)
                    self.img_h = self.img_w / ratio
                else:
                    self.img_h = min(by * 0.8, 100)
                    self.img_w = self.img_h * ratio
                
                name = os.path.basename(path)
                self.img_name.config(text=f"File: {name}")
                self.img_size.config(text=f"Size: {self.current_image.width}x{self.current_image.height}")

                self.draw()
                backend._resetPlan()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load: {e}")
    
    def clear_image(self):
        self.current_image = None
        self.image_tk = None
        self.handles = []
        self.img_name.config(text="No image loaded")
        self.img_size.config(text="")

        self.draw()
        backend._resetPlan()
    
    def draw_image(self):
        w = int(self.img_w * self.zoom)
        h = int(self.img_h * self.zoom)
        
        if w > 0 and h > 0:
            img = self.current_image.resize((w, h), Image.Resampling.LANCZOS)
            self.image_tk = ImageTk.PhotoImage(img)
            cx, cy = self.to_canvas(self.img_x, self.img_y)
            self.canvas.create_image(cx, cy, image=self.image_tk, anchor=tk.CENTER, tags="image")
    
    def draw_handles(self):
        self.handles = []
        hw, hh = self.img_w/2, self.img_h/2
        
        positions = [
            (self.img_x-hw, self.img_y-hh, "nw"), (self.img_x+hw, self.img_y-hh, "ne"),
            (self.img_x-hw, self.img_y+hh, "sw"), (self.img_x+hw, self.img_y+hh, "se"),
            (self.img_x, self.img_y-hh, "n"), (self.img_x, self.img_y+hh, "s"),
            (self.img_x-hw, self.img_y, "w"), (self.img_x+hw, self.img_y, "e")
        ]
        
        for wx, wy, cursor in positions:
            cx, cy = self.to_canvas(wx, wy)
            h = self.canvas.create_rectangle(cx-6, cy-6, cx+6, cy+6,
                                           fill="#ffffff", outline="#217346", width=2,
                                           activefill="#f0f8f0", activeoutline="#1a5c37")
            self.handles.append((h, cursor))
    
    def resize_image(self, dx, dy):
        if not self.resize_handle or not self.current_image:
            return
            
        dx_ws = dx / self.zoom
        dy_ws = dy / self.zoom
        old_w, old_h = self.img_w, self.img_h
        old_x, old_y = self.img_x, self.img_y
        ratio = self.current_image.width / self.current_image.height
        
        if self.resize_handle == "nw":
            new_w = max(10, old_w - dx_ws)
            new_h = new_w / ratio
            self.img_x = old_x + old_w/2 - new_w/2
            self.img_y = old_y + old_h/2 - new_h/2
            
        elif self.resize_handle == "ne":
            new_w = max(10, old_w + dx_ws)
            new_h = new_w / ratio
            self.img_x = old_x - old_w/2 + new_w/2
            self.img_y = old_y + old_h/2 - new_h/2
            
        elif self.resize_handle == "sw":
            new_w = max(10, old_w - dx_ws)
            new_h = new_w / ratio
            self.img_x = old_x + old_w/2 - new_w/2
            self.img_y = old_y - old_h/2 + new_h/2
            
        elif self.resize_handle == "se":
            new_w = max(10, old_w + dx_ws)
            new_h = new_w / ratio
            self.img_x = old_x - old_w/2 + new_w/2
            self.img_y = old_y - old_h/2 + new_h/2
            
        elif self.resize_handle == "n":
            new_h = max(10, old_h - dy_ws)
            new_w = new_h * ratio
            self.img_x = old_x
            self.img_y = old_y + old_h/2 - new_h/2
            
        elif self.resize_handle == "s":
            new_h = max(10, old_h + dy_ws)
            new_w = new_h * ratio
            self.img_x = old_x
            self.img_y = old_y - old_h/2 + new_h/2
            
        elif self.resize_handle == "w":
            new_w = max(10, old_w - dx_ws)
            new_h = new_w / ratio
            self.img_x = old_x + old_w/2 - new_w/2
            self.img_y = old_y
            
        elif self.resize_handle == "e":
            new_w = max(10, old_w + dx_ws)
            new_h = new_w / ratio
            self.img_x = old_x - old_w/2 + new_w/2
            self.img_y = old_y
        
        self.img_w = new_w
        self.img_h = new_h
        self.draw()
        backend._resetPlan()
    
    def zoom_in(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        center_x, center_y = w/2, h/2
        old_wx, old_wy = self.to_workspace(center_x, center_y)
        
        self.zoom = min(self.zoom * 1.2, 10.0)
        
        new_cx, new_cy = self.to_canvas(old_wx, old_wy)
        self.offset_x += center_x - new_cx
        self.offset_y += center_y - new_cy
        
        self.zoom_label.config(text=f"{int(self.zoom * 100)}%")
        self.draw()
    
    def zoom_out(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        center_x, center_y = w/2, h/2
        old_wx, old_wy = self.to_workspace(center_x, center_y)
        
        self.zoom = max(self.zoom / 1.2, 0.1)
        
        new_cx, new_cy = self.to_canvas(old_wx, old_wy)
        self.offset_x += center_x - new_cx
        self.offset_y += center_y - new_cy
        
        self.zoom_label.config(text=f"{int(self.zoom * 100)}%")
        self.draw()
    
    def reset_zoom(self):
        self.zoom = 1.0
        self.offset_x = self.offset_y = 0
        self.zoom_label.config(text="100%")
        self.draw()
    
    def fit_bed(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w > 1 and h > 1:
            bx, by = self.get_bed_size()
            scale = min((w-100)/bx, (h-100)/by)
            self.zoom = scale
            self.offset_x = self.offset_y = 0
            self.zoom_label.config(text=f"{int(scale * 100)}%")
            self.draw()    
    
    # Events
    def _click(self, e):
        self.drag_start = (e.x, e.y)
        item = self.canvas.find_closest(e.x, e.y)[0]
        
        for handle, cursor in self.handles:
            if item == handle:
                self.drag_mode = "resize"
                self.resize_handle = cursor
                cursor_map = {"nw": "top_left_corner", "ne": "top_right_corner",
                             "sw": "bottom_left_corner", "se": "bottom_right_corner",
                             "n": "top_side", "s": "bottom_side", "w": "left_side", "e": "right_side"}
                try:
                    self.canvas.config(cursor=cursor_map.get(cursor, "sizing"))
                except:
                    self.canvas.config(cursor="sizing")
                return
        
        if self.current_image:
            tags = self.canvas.gettags(item)
            if "image" in tags:
                self.drag_mode = "image"
                self.canvas.config(cursor="fleur")
            else:
                self.drag_mode = "workspace"
                self.canvas.config(cursor="hand2")
        else:
            self.drag_mode = "workspace"
            self.canvas.config(cursor="hand2")
    
    def _drag(self, e):
        if not self.drag_start:
            return
            
        dx = e.x - self.drag_start[0]
        dy = e.y - self.drag_start[1]
        
        if self.drag_mode == "resize":
            self.resize_image(dx, dy)
        elif self.drag_mode == "image":
            self.img_x += dx / self.zoom
            self.img_y += dy / self.zoom
            self.draw()
            backend._resetPlan()
        elif self.drag_mode == "workspace":
            self.offset_x += dx
            self.offset_y += dy
            self.draw()
            
        self.drag_start = (e.x, e.y)
    
    def _release(self, e):
        self.drag_start = None
        self.drag_mode = None
        self.resize_handle = None
        self.canvas.config(cursor="")


if __name__ == "__main__":
    root = tk.Tk()
    app = RasterTraceEditor(root)
    root.mainloop()
