import numpy
from xml.etree import cElementTree
from PIL import ImageOps

import potrace
import vtracer
import svg.path as svgpath


# Config
POTRACE_IMG_THRESHOLD = 127
POTRACE_INVERT = True
VTRACER_INVERT = False
VTRACER_FILTER_SPECKLE = 4
VTRACER_COLOR_PRECISION = 8
VTRACER_LAYER_DIFFERENCE = 10
VTRACER_PATH_PRECISION = 8

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
    """"""

    new_img = img.convert("L")

    if VTRACER_INVERT:
        new_img = ImageOps.invert(new_img)
    
    new_img = new_img.convert("RGBA")

    pixels: list[tuple[int, int, int, int]] = list(new_img.getdata())
    svg = vtracer.convert_pixels_to_svg(
        rgba_pixels=pixels,
        size=new_img.size,
        colormode="color",
        hierarchical="cutout",
        mode="spline",
        corner_threshold=60,
        length_threshold=4.0,
        max_iterations=10,
        splice_threshold=45,
        color_precision=VTRACER_COLOR_PRECISION,
        layer_difference=VTRACER_LAYER_DIFFERENCE,
        path_precision=VTRACER_PATH_PRECISION
    )
    xml_svg = cElementTree.fromstring(svg)

    bezier_curves = []
    for element in xml_svg:
        if not element.tag.endswith("path"):
            continue

        path_d = element.get("d")
        path_tf = _vtTransform_to_numpy(element.get("transform"))
        path_fill = element.get("fill")

        svg_path = svgpath.parse_path(path_d)
        for segment in svg_path:
            if type(segment) != svgpath.CubicBezier:
                continue

            bezier_curves.append([
                _spPoint_to_numpy(segment.start) + path_tf,
                _spPoint_to_numpy(segment.control1) + path_tf,
                _spPoint_to_numpy(segment.control2) + path_tf,
                _spPoint_to_numpy(segment.end) + path_tf
            ])
        # print(svg_path) # TODO don't forget to offset with path_tf


    return bezier_curves



def minimizeAir(bezier):
    """Optimize the order of bezier curves."""
    # TODO travelling salesman problem
    return bezier



def _ptPoint_to_numpy(ptPoint): # potrace
    return numpy.array((ptPoint.x, ptPoint.y))

def _spPoint_to_numpy(spPoint): # svg.path
    return numpy.array((spPoint.real, spPoint.imag))

def _vtTransform_to_numpy(spTransform): # vtracer
    split_tf = spTransform[len("transform("):-len(")")].split(",")
    return numpy.array((float(split_tf[0]), float(split_tf[1])))