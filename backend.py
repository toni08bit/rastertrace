import time
import numpy
import serial
import potrace
from tkinter import messagebox, filedialog
from PIL import Image, ImageDraw

# Config
SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUD_RATE = 115200
SERIAL_TIMEOUT = 3
PX_PER_MM = 8
IMG_THRESHOLD = 127
G0_FEEDRATE = 1200
G1_FEEDRATE = 1000
STEPS_PER_MM = 1

BACKGROUND_COLORS = {
    "ok": "#217346",
    "warn": "#b7950b",
    "error": "#c0392b",
    "neutral": "#7f8c8d"
}
FOREGROUND_COLORS = {
    "ok": "#27ae60",
    "warn": "#f1c40f",
    "error": "#e74c3c",
    "neutral": "#7f8c8d"
}


# Memory
_ui_refs = None # set by main.py
plan_gcode = None
plan_img = None
serial_con = None
is_moving = False


# Exception
class SoftError(Exception):
    def __init__(self, *args):
        super().__init__(*args)

# Events
def _createPlanBtn():
    if plan_img:
        plan_img.show()
    else:
        createPlan()

def _connectSerialBtn():
    global serial_con

    if serial_con and serial_con.is_open:
        serial_con.close()
        serial_con = None
        setPlanStatus("serial", "Disconnected", "error")
    else:
        setPlanStatus("serial", "Reconnecting", "neutral")
        try:
            serial_con = serial.Serial(SERIAL_PORT, SERIAL_BAUD_RATE, timeout=None)
        except Exception as exception:
            setPlanStatus("serial", "Error", "error")
            messagebox.showerror("Serial Error", f"Unexpected error: {exception}")
            return
        
        serial_con.write("G6 P100")
        if "ok" not in serial_con.readline():
            setPlanStatus("serial", "Invalid", "error")
            messagebox.showerror("Serial Error", "Invalid device/firmware.")
            return
        
        setPlanStatus("serial", "Connected", "ok")

def _beginMotionBtn():
    global is_moving

    if is_moving:
        serial_con.write("M112".encode("utf-8"))
        messagebox.showwarning("Warning", "Emergency Stop.")
        time.sleep(2)
        serial_con.close()
        return
    
    if not plan_gcode:
        messagebox.showwarning("Warning", "Create a plan first.")
        return
    
    if not serial_con or not serial_con.is_open:
        messagebox.showwarning("Warning", "Connect serial first.")
        return
    
    is_moving = True
    setPlanButton(2, "Abort Motion")
    try:
        _ui_refs["app"].update()

        serial_con.write("G6 P100".encode("utf-8"))
        if "ok" not in serial_con.readline():
            setPlanStatus("serial", "Invalid", "error")
            messagebox.showerror("Serial Error", "Device reported busy.")
            return
        
        gcode_chunks = splitIntoChunks(plan_gcode.split("\n"))
        start_time = time.time()
        for chunk_i in range(len(gcode_chunks)):
            chunk = gcode_chunks[chunk_i]

            serial_con.write("\n".join(chunk).encode("utf-8"))
            ok_counter = 0
            while ok_counter != len(chunk):
                if serial_con.readline() == "ok\n":
                    ok_counter += 1
                else:
                    setPlanStatus("serial", "Invalid", "error")
                    messagebox.showerror("Serial Error", "Device reported issue.")
                    return
            
            progress = chunk_i / len(gcode_chunks)
            pps = progress / (time.time() - start_time)
            setPlanStatus("progress", f"{int(progress * 100)}%", "warn")
            setPlanStatus("progress_bar", progress, "ok")
            setPlanButton("eta", f"{seconds_to_string((1 - progress) / pps)}")
        
        setPlanStatus("progress_bar", 1, "ok")
        setPlanStatus("progress", "100%", "ok")
        return
    finally:
        is_moving = False
        setPlanButton(2, "Begin Motion")

def _saveGcodeBtn():
    if not plan_gcode:
        messagebox.showwarning("Warning", "Create a plan first.")
        return
    
    new_file = filedialog.asksaveasfile(
        mode = "w",
        confirmoverwrite = True,
        filetypes = [("G-Code", "*.gcode")]
    )

    if new_file:
        new_file.write(plan_gcode)
        new_file.close()

def _copyGcodeBtn():
    if not plan_gcode:
        messagebox.showwarning("Warning", "Create a plan first.")
        return

    _ui_refs["app"].root.clipboard_clear()
    _ui_refs["app"].root.clipboard_append(plan_gcode)
    _ui_refs["app"].root.update()

def _resetPlan():
    global plan_img
    global plan_gcode

    if not plan_img:
        return

    plan_img = None
    plan_gcode = None
    setPlanButton(0, "Create Plan")
    setPlanStatus("planned", "No", "error")


# Utility
def setPlanStatus(key, value, color_key):
    color = FOREGROUND_COLORS.get(color_key, FOREGROUND_COLORS["neutral"])
    
    if key == "planned":
        _ui_refs["planned_label"].config(text=str(value), foreground=color)
    elif key == "serial":
        _ui_refs["serial_label"].config(text=str(value), foreground=color)
    elif key == "progress_bar":
        _ui_refs["progress_bar"]["value"] = value * 100
    elif key == "progress":
        _ui_refs["progress_label"].config(text=f"{value}%", foreground=color)
    elif key == "eta":
        _ui_refs["eta_label"].config(text=str(value), foreground=color)
    
    _ui_refs["app"].root.update()

def setPlanButton(id, newText):
    if id == 0:
        _ui_refs["create_plan_btn"].config(text=newText)
    elif id == 1:
        _ui_refs["connect_serial_btn"].config(text=newText)
    elif id == 2:
        _ui_refs["begin_motion_btn"].config(text=newText)

    _ui_refs["app"].root.update()


# Planning
def createPlan():
    global plan_img
    global plan_gcode

    setPlanStatus("planned", "(1/7) Reading...", "warn")

    try:
        bed_x = int(_ui_refs["app"].bed_x.get())
        bed_y = int(_ui_refs["app"].bed_y.get())
        img_w = _ui_refs["app"].img_w
        img_h = _ui_refs["app"].img_h
        img_x = _ui_refs["app"].img_x
        img_y = _ui_refs["app"].img_y
        pen_safety = int(float(_ui_refs["app"].pen_safety.get()) * PX_PER_MM)

        if not _ui_refs["app"].current_image:
            messagebox.showwarning("Warning", "No image selected!")
            raise SoftError()

        new_img = Image.new("1", (bed_x * PX_PER_MM, bed_y * PX_PER_MM))

        setPlanStatus("planned", "(2/7) Converting...", "warn")
        converted_image = _ui_refs["app"].current_image.resize(
            (
                int(img_w * PX_PER_MM),
                int(img_h * PX_PER_MM)
            ),
            Image.Resampling.BICUBIC
        ).convert("L").point(lambda x: 255 if x < IMG_THRESHOLD else 0, mode="1")

        setPlanStatus("planned", "(3/7) Moving...", "warn")
        new_img.paste(converted_image, (
            int((img_x + bed_x / 2 - img_w / 2) * PX_PER_MM),
            int((img_y + bed_y / 2 - img_h / 2) * PX_PER_MM)
        ))

        draw = ImageDraw.Draw(new_img)
        width, height = new_img.size
        margin = int(pen_safety)
        draw.rectangle([0, 0, width, margin], fill=0)
        draw.rectangle([0, height - margin, width, height], fill=0)
        draw.rectangle([0, 0, margin, height], fill=0)
        draw.rectangle([width - margin, 0, width, height], fill=0)

        bitmap = potrace.Bitmap(numpy.array(new_img, dtype=numpy.uint8))

        setPlanStatus("planned", "(4/7) Tracing...", "warn")
        trace = bitmap.trace()

        setPlanStatus("planned", "(5/7) Minimizing...", "warn")
        bezier = minimizeAir(potraceToBezier(trace))
        setPlanStatus("planned", "(6/7) Viewing...", "warn")
        plan_img = bezierToImg(bezier, new_img.size)
        setPlanStatus("planned", "(7/7) Coding...", "warn")
        plan_gcode = generateGcode(bezier, new_img.size)
    
    except SoftError:
        plan_gcode = None
        plan_img = None
        setPlanStatus("planned", "Warning", "warn")
    
    except Exception as exception:
        plan_gcode = None
        plan_img = None
        setPlanStatus("planned", "Error", "error")
        messagebox.showerror("Error", f"Unexpected error: {exception.__class__.__name__}")
    
    else:
        setPlanButton(0, "View Plan")
        setPlanStatus("planned", "Yes", "ok")


def potraceToBezier(path):
    bezier_curves = []
    
    for curve in path:
        prev_point = curve.start_point
        
        for segment in curve:
            if segment.is_corner:
                # CornerSegment: force sharp turn
                c = segment.c

                bezier_curves.append([
                    prev_point, prev_point, c, c
                ])

                bezier_curves.append([
                    c, c,
                    segment.end_point, segment.end_point
                ])
            else:
                # BezierSegment: direct conversion
                bezier_curves.append([
                    prev_point,
                    segment.c1,
                    segment.c2,
                    segment.end_point
                ])
            
            prev_point = segment.end_point
    
    return bezier_curves

def bezierToImg(bezier, bitmap_size):
    img = Image.new("1", bitmap_size, 1)
    draw = ImageDraw.Draw(img)

    thickness_px = int(float(_ui_refs["app"].pen_thickness.get()) * PX_PER_MM)
    
    for p0, c1, c2, p3 in bezier:
        steps = 30
        points = []
        for t in numpy.linspace(0, 1, steps):
            x = (1-t)**3*p0[0] + 3*(1-t)**2*t*c1[0] + 3*(1-t)*t**2*c2[0] + t**3*p3[0]
            y = (1-t)**3*p0[1] + 3*(1-t)**2*t*c1[1] + 3*(1-t)*t**2*c2[1] + t**3*p3[1]
            points.append((int(x), int(y)))
        
        if len(points) > 1:
            for i in range(len(points) - 1):
                draw.line([points[i], points[i + 1]], fill=0, width=thickness_px)
    
    return img

def minimizeAir(bezier):
    # TODO: travelling salesman problem!!!
    return bezier

_gcode_draft = ""
def generateGcode(plan_lines, bitmap_size):
    global _gcode_draft
    _gcode_draft = ""

    def instr(instruction):
        global _gcode_draft
        _gcode_draft += instruction + "\n"

    
    bed_x = int(_ui_refs["app"].bed_x.get())
    bed_y = int(_ui_refs["app"].bed_y.get())
    pen_up = float(_ui_refs["app"].pen_up.get())
    pen_down = float(_ui_refs["app"].pen_down.get())
    pen_x = float(_ui_refs["app"].pen_x.get())
    pen_y = float(_ui_refs["app"].pen_y.get())

    pos_factor = numpy.array((
        1 / bitmap_size[0] * bed_x,
        1 / bitmap_size[1] * bed_y
    ))


    instr("G21") # Unit: mm
    instr("G90") # Absolute Positioning
    instr("G28") # Calibrate Steppers
    instr(f"G0 F{G0_FEEDRATE}") # G0 Speed
    instr(f"G1 F{G1_FEEDRATE}") # G1 Speed

    instr(f"G0 X{bed_x / 2} Y{bed_y / 2} Z150") # top center

    continuous_transition = False
    for curve_i in range(len(plan_lines)):
        curve = plan_lines[curve_i]

        steps_n = int(bezierLength(curve) / STEPS_PER_MM)

        start_pos = curve[0] * pos_factor
        end_pos = curve[3] * pos_factor
        if not continuous_transition:
            instr(f"G0 X{start_pos[0] - pen_x} Y{start_pos[1] - pen_y} Z{pen_up}")

        for step_i in range(steps_n + 1):
            if continuous_transition:
                continuous_transition = False
                continue
            else:
                pos = bezierPos(
                    step_i / steps_n,
                    curve[0], curve[1], curve[2], curve[3]
                ) * pos_factor
                instr(f"G1 X{pos[0] - pen_x} Y{pos[1] - pen_y} Z{pen_down}")

        if curve_i + 1 != len(plan_lines) and numpy.array_equal(plan_lines[curve_i + 1][0] * pos_factor, end_pos):
            continuous_transition = True
        else:
            instr(f"G0 X{end_pos[0] - pen_x} Y{end_pos[1] - pen_y} Z{pen_up}")

    instr(f"G0 X{bed_x / 2} Y{bed_y / 2} Z150") # top center

    return _gcode_draft

# Math
def bezierPos(t, p0, c1, c2, p3):
    p0, c1, c2, p3 = numpy.array(p0), numpy.array(c1), numpy.array(c2), numpy.array(p3)
    return (1-t)**3 * p0 + 3*(1-t)**2*t * c1 + 3*(1-t)*t**2 * c2 + t**3 * p3

def bezierLength(control_points, samples=100):
    t_values = numpy.linspace(0, 1, samples)
    p0, c1, c2, p3 = control_points
    
    curve_points = numpy.array([bezierPos(t, p0, c1, c2, p3) for t in t_values])
    
    return numpy.sum(numpy.linalg.norm(numpy.diff(curve_points, axis=0), axis=1))

def splitIntoChunks(lst, x):
    chunk_size = len(lst) // x
    remainder = len(lst) % x
    
    chunks = []
    start = 0
    
    for i in range(x):
        end = start + chunk_size + (1 if i < remainder else 0)
        chunks.append(lst[start:end])
        start = end
    
    return chunks

def seconds_to_string(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}h {m}m {s}s"
