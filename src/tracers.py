import numpy
from PIL import ImageOps

import potrace


# Config
POTRACE_IMG_THRESHOLD = 127
POTRACE_INVERT = True

def tracePotracer(img):
    """Classic but less reliable"""

    new_img = img.convert("L").point(lambda x: 255 if x < POTRACE_IMG_THRESHOLD else 0, mode="1")

    if POTRACE_INVERT:
        new_img = ImageOps.invert(new_img)

    bitmap = potrace.Bitmap(numpy.array(new_img, dtype=numpy.bool))
    trace = bitmap.trace()

    bezier_curves = []
    
    for curve in trace:
        prev_point = _ptPoint_to_numpy(curve.start_point)
        
        for segment in curve.segments:
            end_point = _ptPoint_to_numpy(segment.end_point)
            if segment.is_corner:
                # CornerSegment: force sharp turn
                c = _ptPoint_to_numpy(segment.c)

                bezier_curves.append([
                    prev_point, prev_point, c, c
                ])

                bezier_curves.append([
                    c, c,
                    end_point, end_point
                ])
            else:
                # BezierSegment: direct conversion
                c1 = _ptPoint_to_numpy(segment.c1)
                c2 = _ptPoint_to_numpy(segment.c2)

                bezier_curves.append([
                    prev_point,
                    c1,
                    c2,
                    end_point
                ])
            
            prev_point = end_point
    
    return bezier_curves

def traceVTracer(img):
    pass



def minimizeAir(bezier):
    """Optimize the order of bezier curves."""
    # TODO travelling salesman problem
    return bezier



def _ptPoint_to_numpy(ptPoint):
    return numpy.array((ptPoint.x, ptPoint.y))