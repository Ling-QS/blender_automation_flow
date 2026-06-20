import math

import bpy

try:
    import gpu
    from gpu_extras.batch import batch_for_shader
except Exception:
    gpu = None
    batch_for_shader = None


_DASHED_POLYLINE_SHADER = None
_SOFT_POLYLINE_SHADER = None


def _get_dashed_polyline_shader():
    global _DASHED_POLYLINE_SHADER
    if _DASHED_POLYLINE_SHADER is not None:
        return _DASHED_POLYLINE_SHADER
    if gpu is None or not hasattr(gpu, "types") or not hasattr(gpu.types, "GPUShaderCreateInfo"):
        return None
    try:
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        iface = gpu.types.GPUStageInterfaceInfo("af_dashed_polyline_iface")
        iface.smooth("VEC2", "v_uv")
        info.vertex_in(0, "VEC2", "pos")
        info.vertex_in(1, "VEC2", "uv")
        info.vertex_out(iface)
        info.push_constant("VEC4", "color")
        info.push_constant("FLOAT", "dash_length")
        info.push_constant("FLOAT", "gap_length")
        info.fragment_out(0, "VEC4", "fragColor")
        info.vertex_source(
            """
            void main()
            {
                gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);
                v_uv = uv;
            }
            """
        )
        info.fragment_source(
            """
            void main()
            {
                float cycle_length = max(0.0001, dash_length + gap_length);
                float cycle_position = mod(v_uv.x, cycle_length);
                if (cycle_position > dash_length) {
                    discard;
                }
                float side = abs(v_uv.y);
                float alpha = 1.0 - smoothstep(0.82, 1.0, side);
                fragColor = vec4(color.rgb, color.a * alpha);
            }
            """
        )
        _DASHED_POLYLINE_SHADER = gpu.shader.create_from_info(info)
    except Exception:
        _DASHED_POLYLINE_SHADER = None
    return _DASHED_POLYLINE_SHADER


def _get_soft_polyline_shader():
    global _SOFT_POLYLINE_SHADER
    if _SOFT_POLYLINE_SHADER is not None:
        return _SOFT_POLYLINE_SHADER
    if gpu is None or not hasattr(gpu, "types") or not hasattr(gpu.types, "GPUShaderCreateInfo"):
        return None
    try:
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        iface = gpu.types.GPUStageInterfaceInfo("af_soft_polyline_iface")
        iface.smooth("VEC2", "v_uv")
        info.vertex_in(0, "VEC2", "pos")
        info.vertex_in(1, "VEC2", "uv")
        info.vertex_out(iface)
        info.push_constant("VEC4", "color")
        info.fragment_out(0, "VEC4", "fragColor")
        info.vertex_source(
            """
            void main()
            {
                gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);
                v_uv = uv;
            }
            """
        )
        info.fragment_source(
            """
            void main()
            {
                float side = abs(v_uv.y);
                float alpha = 1.0 - smoothstep(0.58, 1.0, side);
                fragColor = vec4(color.rgb, color.a * alpha);
            }
            """
        )
        _SOFT_POLYLINE_SHADER = gpu.shader.create_from_info(info)
    except Exception:
        _SOFT_POLYLINE_SHADER = None
    return _SOFT_POLYLINE_SHADER


def _build_polyline_strip_geometry(region_points, line_width):
    if len(region_points) < 2:
        return [], []

    half_width = max(0.5, float(line_width) * 0.5)
    points = [(float(point[0]), float(point[1])) for point in region_points]
    cumulative_lengths = [0.0]
    total_length = 0.0
    for start_point, end_point in zip(points[:-1], points[1:]):
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        total_length += (dx ** 2 + dy ** 2) ** 0.5
        cumulative_lengths.append(total_length)

    def _normalized(dx, dy):
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length <= 1e-6:
            return None
        return dx / length, dy / length

    positions = []
    uvs = []
    point_count = len(points)
    for index, point in enumerate(points):
        if index == 0:
            tangent = _normalized(points[1][0] - point[0], points[1][1] - point[1])
        elif index == point_count - 1:
            tangent = _normalized(point[0] - points[index - 1][0], point[1] - points[index - 1][1])
        else:
            prev_tangent = _normalized(point[0] - points[index - 1][0], point[1] - points[index - 1][1])
            next_tangent = _normalized(points[index + 1][0] - point[0], points[index + 1][1] - point[1])
            if prev_tangent is None:
                tangent = next_tangent
            elif next_tangent is None:
                tangent = prev_tangent
            else:
                tangent = _normalized(prev_tangent[0] + next_tangent[0], prev_tangent[1] + next_tangent[1])
                if tangent is None:
                    tangent = next_tangent
        if tangent is None:
            continue

        normal_x = -tangent[1] * half_width
        normal_y = tangent[0] * half_width
        distance = cumulative_lengths[index]
        positions.append((point[0] + normal_x, point[1] + normal_y))
        positions.append((point[0] - normal_x, point[1] - normal_y))
        uvs.append((distance, 1.0))
        uvs.append((distance, -1.0))

    return positions, uvs


def _clip_text_to_width(font_id, text, max_width, ellipsis="..."):
    from .chips import _clip_text_to_width as clip_text_to_width

    return clip_text_to_width(font_id, text, max_width, ellipsis=ellipsis)


def _node_bounds(node, pad=4.0):
    node_loc = getattr(node, "location_absolute", None)
    if node_loc is None:
        node_loc = node.location
    ui_scale = 1.0
    preferences = getattr(bpy.context, "preferences", None)
    system = getattr(preferences, "system", None) if preferences is not None else None
    if system is not None:
        ui_scale = max(0.1, float(getattr(system, "ui_scale", 1.0)))

    width = node.dimensions.x if getattr(node, "dimensions", None) and node.dimensions.x > 1.0 else getattr(node, "width", 140.0)
    height = node.dimensions.y if getattr(node, "dimensions", None) and node.dimensions.y > 1.0 else getattr(node, "height", 100.0)
    return (
        (node_loc.x * ui_scale) - pad,
        (node_loc.y * ui_scale) + pad,
        (node_loc.x * ui_scale) + width + pad,
        (node_loc.y * ui_scale) - height - pad,
    )


def _paired_zone_node_bounds(node, pad=8.0):
    x1, y1, x2, y2 = _node_bounds(node, pad=pad)
    node_type = str(getattr(node, "bl_idname", "") or "")
    clip_width = max(0.0, float(pad) * 3.0)
    available_width = max(0.0, x2 - x1)
    clip_width = min(clip_width, available_width * 0.75)
    if node_type in {"AFNodeStart", "AFNodeTaskStart", "AFNodeRepeatStart", "AFNodeSubflowStart", "AFNodeBranchStart"}:
        x1 += clip_width
    elif node_type in {"AFNodeEnd", "AFNodeTaskOutput", "AFNodeRepeatEnd", "AFNodeSubflowJoin", "AFNodeBranchEnd"}:
        x2 -= clip_width
    return (x1, y1, x2, y2)


def _repeat_zone_node_bounds(node, pad=8.0):
    return _paired_zone_node_bounds(node, pad=pad)


def _draw_outline_bounds(bounds, color, line_width):
    if gpu is None or batch_for_shader is None:
        return
    region = bpy.context.region
    if region is None or getattr(region, "type", "") != "WINDOW":
        return
    view2d = getattr(region, "view2d", None)
    if view2d is None:
        return

    x1, y1, x2, y2 = bounds
    coords = [
        view2d.view_to_region(x1, y1, clip=False),
        view2d.view_to_region(x2, y1, clip=False),
        view2d.view_to_region(x2, y2, clip=False),
        view2d.view_to_region(x1, y2, clip=False),
        view2d.view_to_region(x1, y1, clip=False),
    ]

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "LINE_STRIP", {"pos": coords})
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(line_width)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set("NONE")


def _draw_dashed_polyline(region_points, color, line_width=1.0, dash_length=6.0, gap_length=12.0):
    if gpu is None or batch_for_shader is None or len(region_points) < 2:
        return

    dash_length = max(0.5, float(dash_length))
    gap_length = max(0.0, float(gap_length))
    cycle_length = dash_length + gap_length
    if cycle_length <= 1e-6:
        cycle_length = dash_length

    total_length = 0.0
    for start_point, end_point in zip(region_points[:-1], region_points[1:]):
        x1, y1 = float(start_point[0]), float(start_point[1])
        x2, y2 = float(end_point[0]), float(end_point[1])
        total_length += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if total_length > 12000.0:
            return

    shader = _get_dashed_polyline_shader()
    if shader is not None:
        positions, uvs = _build_polyline_strip_geometry(region_points, line_width)
        if positions and uvs:
            batch = batch_for_shader(shader, "TRI_STRIP", {"pos": positions, "uv": uvs})
            gpu.state.blend_set("ALPHA")
            shader.bind()
            shader.uniform_float("color", color)
            shader.uniform_float("dash_length", dash_length)
            shader.uniform_float("gap_length", gap_length)
            batch.draw(shader)
            gpu.state.blend_set("NONE")
            return

    max_segment_pairs = 2048
    segments = []
    cycle_offset = 0.0
    for start_point, end_point in zip(region_points[:-1], region_points[1:]):
        x1, y1 = float(start_point[0]), float(start_point[1])
        x2, y2 = float(end_point[0]), float(end_point[1])
        delta_x = x2 - x1
        delta_y = y2 - y1
        segment_length = (delta_x ** 2 + delta_y ** 2) ** 0.5
        if segment_length <= 1e-6:
            continue

        direction_x = delta_x / segment_length
        direction_y = delta_y / segment_length
        local_distance = 0.0
        while local_distance < segment_length - 1e-6:
            cycle_position = (cycle_offset + local_distance) % cycle_length
            if cycle_position < dash_length:
                dash_remaining = dash_length - cycle_position
                draw_length = min(dash_remaining, segment_length - local_distance)
                draw_start = local_distance
                draw_end = local_distance + draw_length
                segments.append(
                    (
                        (x1 + (direction_x * draw_start), y1 + (direction_y * draw_start)),
                        (x1 + (direction_x * draw_end), y1 + (direction_y * draw_end)),
                    )
                )
                if len(segments) >= max_segment_pairs:
                    break
                local_distance = draw_end
            else:
                gap_remaining = cycle_length - cycle_position
                local_distance += min(gap_remaining, segment_length - local_distance)
        if len(segments) >= max_segment_pairs:
            break
        cycle_offset = (cycle_offset + segment_length) % cycle_length

    if not segments:
        return

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    half_width = max(0.5, float(line_width) * 0.5)
    triangle_positions = []
    for start_point, end_point in segments:
        x1, y1 = float(start_point[0]), float(start_point[1])
        x2, y2 = float(end_point[0]), float(end_point[1])
        delta_x = x2 - x1
        delta_y = y2 - y1
        segment_length = (delta_x ** 2 + delta_y ** 2) ** 0.5
        if segment_length <= 1e-6:
            continue

        normal_x = -(delta_y / segment_length) * half_width
        normal_y = (delta_x / segment_length) * half_width
        quad_a = (x1 + normal_x, y1 + normal_y)
        quad_b = (x1 - normal_x, y1 - normal_y)
        quad_c = (x2 + normal_x, y2 + normal_y)
        quad_d = (x2 - normal_x, y2 - normal_y)
        triangle_positions.extend((quad_a, quad_b, quad_c, quad_c, quad_b, quad_d))

    if not triangle_positions:
        return

    batch = batch_for_shader(shader, "TRIS", {"pos": triangle_positions})
    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")


def _draw_polyline_strip(region_points, color, line_width=1.0):
    if gpu is None or batch_for_shader is None or len(region_points) < 2:
        return
    positions, uvs = _build_polyline_strip_geometry(region_points, line_width)
    if not positions:
        return

    shader = _get_soft_polyline_shader()
    if shader is not None and uvs:
        batch = batch_for_shader(shader, "TRI_STRIP", {"pos": positions, "uv": uvs})
        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.blend_set("NONE")
        return

    fallback_shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(fallback_shader, "TRI_STRIP", {"pos": positions})
    gpu.state.blend_set("ALPHA")
    fallback_shader.bind()
    fallback_shader.uniform_float("color", color)
    batch.draw(fallback_shader)
    gpu.state.blend_set("NONE")


def _convex_hull(points):
    unique_points = sorted({(float(x), float(y)) for x, y in points})
    if len(unique_points) <= 1:
        return unique_points

    def cross(origin, point_a, point_b):
        return ((point_a[0] - origin[0]) * (point_b[1] - origin[1])) - ((point_a[1] - origin[1]) * (point_b[0] - origin[0]))

    lower = []
    for point in unique_points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)

    upper = []
    for point in reversed(unique_points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)

    return lower[:-1] + upper[:-1]


def _polygon_signed_area(points):
    if len(points) < 3:
        return 0.0
    area = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        area += (float(point[0]) * float(next_point[1])) - (float(next_point[0]) * float(point[1]))
    return area * 0.5


def _rounded_polygon_points(points, radius, segments=5):
    if len(points) < 3:
        return list(points)

    orientation = 1.0 if _polygon_signed_area(points) >= 0.0 else -1.0
    radius = max(0.0, float(radius))
    rounded = []

    def normalize(vector_x, vector_y):
        length = (vector_x ** 2 + vector_y ** 2) ** 0.5
        if length <= 1e-6:
            return None
        return (vector_x / length, vector_y / length, length)

    for index, current_point in enumerate(points):
        previous_point = points[index - 1]
        next_point = points[(index + 1) % len(points)]

        in_vector = normalize(float(previous_point[0]) - float(current_point[0]), float(previous_point[1]) - float(current_point[1]))
        out_vector = normalize(float(next_point[0]) - float(current_point[0]), float(next_point[1]) - float(current_point[1]))
        if in_vector is None or out_vector is None:
            rounded.append((float(current_point[0]), float(current_point[1])))
            continue

        in_x, in_y, in_length = in_vector
        out_x, out_y, out_length = out_vector
        dot = max(-0.9999, min(0.9999, (in_x * out_x) + (in_y * out_y)))
        angle = math.acos(dot)
        if angle <= 1e-3:
            rounded.append((float(current_point[0]), float(current_point[1])))
            continue

        tangent = math.tan(angle * 0.5)
        if abs(tangent) <= 1e-6:
            rounded.append((float(current_point[0]), float(current_point[1])))
            continue

        max_radius = min(in_length, out_length) * tangent * 0.5
        corner_radius = min(radius, max_radius)
        if corner_radius <= 0.5:
            rounded.append((float(current_point[0]), float(current_point[1])))
            continue

        offset = corner_radius / tangent
        start_point = (float(current_point[0]) + (in_x * offset), float(current_point[1]) + (in_y * offset))
        end_point = (float(current_point[0]) + (out_x * offset), float(current_point[1]) + (out_y * offset))

        bisector_x = in_x + out_x
        bisector_y = in_y + out_y
        bisector = normalize(bisector_x, bisector_y)
        if bisector is None:
            rounded.extend((start_point, end_point))
            continue

        center_distance = corner_radius / max(math.sin(angle * 0.5), 1e-6)
        center_x = float(current_point[0]) + (bisector[0] * center_distance)
        center_y = float(current_point[1]) + (bisector[1] * center_distance)

        start_angle = math.atan2(start_point[1] - center_y, start_point[0] - center_x)
        end_angle = math.atan2(end_point[1] - center_y, end_point[0] - center_x)
        if orientation >= 0.0:
            while end_angle <= start_angle:
                end_angle += math.tau
        else:
            while end_angle >= start_angle:
                end_angle -= math.tau

        step_count = max(2, int(segments))
        for step in range(step_count + 1):
            factor = step / float(step_count)
            angle_value = start_angle + ((end_angle - start_angle) * factor)
            rounded.append(
                (
                    center_x + (math.cos(angle_value) * corner_radius),
                    center_y + (math.sin(angle_value) * corner_radius),
                )
            )

    return rounded


def _draw_region_polygon(region_points, fill_color=None, outline_color=None, line_width=1.0):
    if gpu is None or batch_for_shader is None or len(region_points) < 2:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")

    if fill_color is not None and len(region_points) >= 3:
        triangles = []
        for index in range(1, len(region_points) - 1):
            triangles.extend((region_points[0], region_points[index], region_points[index + 1]))
        fill_batch = batch_for_shader(shader, "TRIS", {"pos": triangles})
        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", fill_color)
        fill_batch.draw(shader)

    if outline_color is not None:
        outline_points = list(region_points)
        if len(outline_points) >= 3:
            outline_points.append(outline_points[0])
        outline_batch = batch_for_shader(shader, "LINE_STRIP", {"pos": outline_points})
        gpu.state.blend_set("ALPHA")
        gpu.state.line_width_set(line_width)
        shader.bind()
        shader.uniform_float("color", outline_color)
        outline_batch.draw(shader)
        gpu.state.line_width_set(1.0)

    gpu.state.blend_set("NONE")


def _draw_polygon(points, fill_color=None, outline_color=None, line_width=1.0, radius=0.0, segments=5):
    if gpu is None or batch_for_shader is None or len(points) < 2:
        return
    region = bpy.context.region
    if region is None or getattr(region, "type", "") != "WINDOW":
        return
    view2d = getattr(region, "view2d", None)
    if view2d is None:
        return

    region_points = [view2d.view_to_region(float(x), float(y), clip=False) for x, y in points]
    if radius > 0.0 and len(region_points) >= 3:
        region_points = _rounded_polygon_points(region_points, radius, segments=segments)
    _draw_region_polygon(region_points, fill_color=fill_color, outline_color=outline_color, line_width=line_width)


def _draw_pixel_rect(x1, y1, x2, y2, fill_color, outline_color=None, line_width=1.0):
    if gpu is None or batch_for_shader is None:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    fill_coords = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    fill_tris = [fill_coords[0], fill_coords[1], fill_coords[2], fill_coords[0], fill_coords[2], fill_coords[3]]
    fill_batch = batch_for_shader(shader, "TRIS", {"pos": fill_tris})
    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", fill_color)
    fill_batch.draw(shader)
    if outline_color is not None:
        outline_coords = [fill_coords[0], fill_coords[1], fill_coords[2], fill_coords[3], fill_coords[0]]
        outline_batch = batch_for_shader(shader, "LINE_STRIP", {"pos": outline_coords})
        gpu.state.line_width_set(line_width)
        shader.bind()
        shader.uniform_float("color", outline_color)
        outline_batch.draw(shader)
        gpu.state.line_width_set(1.0)
    gpu.state.blend_set("NONE")


def _rounded_pixel_rect_points(x1, y1, x2, y2, radius, segments=6):
    width = max(0.0, float(x2) - float(x1))
    height = max(0.0, float(y2) - float(y1))
    if width <= 0.0 or height <= 0.0:
        return []
    radius = max(0.0, min(float(radius), width * 0.5, height * 0.5))
    if radius <= 0.5:
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    segments = max(2, int(segments))
    corners = (
        ((x2 - radius), (y1 + radius), -0.5 * math.pi, 0.0),
        ((x2 - radius), (y2 - radius), 0.0, 0.5 * math.pi),
        ((x1 + radius), (y2 - radius), 0.5 * math.pi, math.pi),
        ((x1 + radius), (y1 + radius), math.pi, 1.5 * math.pi),
    )
    points = []
    for center_x, center_y, angle_start, angle_end in corners:
        for index in range(segments + 1):
            factor = index / float(segments)
            angle = angle_start + ((angle_end - angle_start) * factor)
            points.append((center_x + (math.cos(angle) * radius), center_y + (math.sin(angle) * radius)))
    return points


def _draw_pixel_rounded_rect(x1, y1, x2, y2, fill_color, outline_color=None, line_width=1.0, radius=8.0):
    if gpu is None or batch_for_shader is None:
        return
    points = _rounded_pixel_rect_points(x1, y1, x2, y2, radius)
    if len(points) < 3:
        _draw_pixel_rect(x1, y1, x2, y2, fill_color, outline_color=outline_color, line_width=line_width)
        return

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    center_x = sum(point[0] for point in points) / len(points)
    center_y = sum(point[1] for point in points) / len(points)
    triangles = []
    for index in range(len(points)):
        triangles.extend(((center_x, center_y), points[index], points[(index + 1) % len(points)]))

    fill_batch = batch_for_shader(shader, "TRIS", {"pos": triangles})
    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", fill_color)
    fill_batch.draw(shader)

    if outline_color is not None:
        outline_points = list(points)
        outline_points.append(points[0])
        outline_batch = batch_for_shader(shader, "LINE_STRIP", {"pos": outline_points})
        gpu.state.line_width_set(line_width)
        shader.bind()
        shader.uniform_float("color", outline_color)
        outline_batch.draw(shader)
        gpu.state.line_width_set(1.0)

    gpu.state.blend_set("NONE")


def _top_rounded_pixel_rect_points(x1, y1, x2, y2, radius, segments=6):
    width = max(0.0, float(x2) - float(x1))
    height = max(0.0, float(y2) - float(y1))
    if width <= 0.0 or height <= 0.0:
        return []

    radius = max(0.0, min(float(radius), width * 0.5, height))
    if radius <= 0.5:
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    segments = max(2, int(segments))
    points = [(float(x1), float(y1)), (float(x2), float(y1)), (float(x2), float(y2 - radius))]

    top_right_center_x = float(x2) - radius
    top_right_center_y = float(y2) - radius
    for index in range(segments + 1):
        factor = index / float(segments)
        angle = 0.0 + ((0.5 * math.pi) * factor)
        points.append(
            (
                top_right_center_x + (math.cos(angle) * radius),
                top_right_center_y + (math.sin(angle) * radius),
            )
        )

    top_left_center_x = float(x1) + radius
    top_left_center_y = float(y2) - radius
    for index in range(segments + 1):
        factor = index / float(segments)
        angle = (0.5 * math.pi) + ((0.5 * math.pi) * factor)
        points.append(
            (
                top_left_center_x + (math.cos(angle) * radius),
                top_left_center_y + (math.sin(angle) * radius),
            )
        )

    points.append((float(x1), float(y1)))
    return points


def _draw_top_rounded_pixel_rect(x1, y1, x2, y2, fill_color, outline_color=None, line_width=1.0, radius=8.0):
    if gpu is None or batch_for_shader is None:
        return
    points = _top_rounded_pixel_rect_points(x1, y1, x2, y2, radius)
    if len(points) < 3:
        _draw_pixel_rect(x1, y1, x2, y2, fill_color, outline_color=outline_color, line_width=line_width)
        return
    _draw_region_polygon(points, fill_color=fill_color, outline_color=outline_color, line_width=line_width)


def _inflate_polygon(points, amount):
    if not points or amount <= 0.0:
        return tuple(points)
    center_x = sum(float(point[0]) for point in points) / len(points)
    center_y = sum(float(point[1]) for point in points) / len(points)
    inflated = []
    for point_x, point_y in points:
        delta_x = float(point_x) - center_x
        delta_y = float(point_y) - center_y
        length = (delta_x ** 2 + delta_y ** 2) ** 0.5
        if length <= 1e-6:
            inflated.append((float(point_x), float(point_y)))
            continue
        scale = (length + float(amount)) / length
        inflated.append((center_x + (delta_x * scale), center_y + (delta_y * scale)))
    return tuple(inflated)
