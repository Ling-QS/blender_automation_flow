import bpy


def build_math_node_classes(
    *,
    AFBaseNode,
    BOOLEAN_MATH_OPERATION_ITEMS,
    COMPARE_MODE_ITEMS,
    COMPARE_OPERATION_ITEMS,
    COMPARE_VECTOR_MODE_ITEMS,
    CONVERSION_MODE_ITEMS,
    CONVERSION_SOCKET_MAP,
    FLOAT_MATH_OPERATION_ITEMS,
    INDEX_SWITCH_MODE_ITEMS,
    INTEGER_MATH_OPERATION_ITEMS,
    MIX_MODE_ITEMS,
    MAP_RANGE_MODE_ITEMS,
    RANDOM_TYPE_ITEMS,
    ROTATION_AXIS_ITEMS,
    ROTATION_PIVOT_AXIS_ITEMS,
    ROTATION_SPACE_ITEMS,
    STRING_COMPARE_OPERATION_ITEMS,
    SWITCH_MODE_ITEMS,
    VECTOR_BOOL_MODE_ITEMS,
    VECTOR_COMPONENT_MODE_ITEMS,
    VECTOR_MATH_OPERATION_ITEMS,
    _enum_property_label,
    _set_default_node_width,
    _set_node_color,
    _switch_socket_idname_for_mode,
    _sync_node_sockets_in_place,
    _sync_index_switch_sockets,
):
    COMPARE_EPSILON_DEFAULT = 1e-6
    COMPARE_EPSILON_STORAGE_KEY = "af_compare_epsilon_default"

    def _sync_compare_node_sockets(node):
        mode = str(getattr(node, "mode", "FLOAT") or "FLOAT")
        operation = str(getattr(node, "operation", "EQUAL") or "EQUAL")
        vector_mode = str(getattr(node, "vector_mode", "ELEMENT") or "ELEMENT")
        previous_epsilon_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Epsilon")
        stored_epsilon = COMPARE_EPSILON_DEFAULT
        if previous_epsilon_socket is not None and hasattr(previous_epsilon_socket, "default_value"):
            try:
                stored_epsilon = max(0.0, float(getattr(previous_epsilon_socket, "default_value", COMPARE_EPSILON_DEFAULT)))
            except Exception:
                stored_epsilon = COMPARE_EPSILON_DEFAULT
        else:
            try:
                stored_epsilon = max(0.0, float(node.get(COMPARE_EPSILON_STORAGE_KEY, COMPARE_EPSILON_DEFAULT)))
            except Exception:
                stored_epsilon = COMPARE_EPSILON_DEFAULT
        try:
            node[COMPARE_EPSILON_STORAGE_KEY] = stored_epsilon
        except Exception:
            pass

        if mode == "VECTOR":
            input_specs = [("NodeSocketVector", "A"), ("NodeSocketVector", "B")]
            if vector_mode == "DOT_PRODUCT":
                input_specs.append(("NodeSocketFloat", "C"))
            elif vector_mode == "DIRECTION":
                input_specs.append(("NodeSocketFloat", "Angle"))
            input_specs.append(("NodeSocketFloat", "Epsilon"))
        elif mode == "INTEGER":
            input_specs = [("NodeSocketInt", "A"), ("NodeSocketInt", "B")]
        elif mode == "STRING":
            input_specs = [("AFSocketString", "A"), ("AFSocketString", "B")]
        else:
            input_specs = [("NodeSocketFloat", "A"), ("NodeSocketFloat", "B")]
            if operation in {"EQUAL", "NOT_EQUAL"}:
                input_specs.append(("NodeSocketFloat", "Epsilon"))

        sync_result = _sync_node_sockets_in_place(node, input_specs, [("NodeSocketBool", "Result")])

        epsilon_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Epsilon")
        if (
            epsilon_socket is not None
            and hasattr(epsilon_socket, "default_value")
            and "Epsilon" in set(sync_result.get("created_input_names", set()) or set())
        ):
            try:
                epsilon_socket.default_value = stored_epsilon
            except Exception:
                pass

    def _sync_mix_node_sockets(node):
        mode = str(getattr(node, "mode", "FLOAT") or "FLOAT")
        if mode == "VECTOR":
            input_specs = [("NodeSocketFloat", "Factor"), ("NodeSocketVector", "A"), ("NodeSocketVector", "B")]
            output_specs = [("NodeSocketVector", "Result")]
        elif mode == "ROTATION":
            input_specs = [("NodeSocketFloat", "Factor"), ("NodeSocketRotation", "A"), ("NodeSocketRotation", "B")]
            output_specs = [("NodeSocketRotation", "Result")]
        else:
            input_specs = [("NodeSocketFloat", "Factor"), ("NodeSocketFloat", "A"), ("NodeSocketFloat", "B")]
            output_specs = [("NodeSocketFloat", "Result")]
        _sync_node_sockets_in_place(node, input_specs, output_specs)

    def _sync_map_range_node_sockets(node):
        mode = str(getattr(node, "mode", "FLOAT") or "FLOAT")
        if mode == "VECTOR":
            input_specs = [
                ("NodeSocketVector", "Value"),
                ("NodeSocketVector", "From Min"),
                ("NodeSocketVector", "From Max"),
                ("NodeSocketVector", "To Min"),
                ("NodeSocketVector", "To Max"),
            ]
            output_specs = [("NodeSocketVector", "Result")]
        else:
            input_specs = [
                ("NodeSocketFloat", "Value"),
                ("NodeSocketFloat", "From Min"),
                ("NodeSocketFloat", "From Max"),
                ("NodeSocketFloat", "To Min"),
                ("NodeSocketFloat", "To Max"),
            ]
            output_specs = [("NodeSocketFloat", "Result")]
        _sync_node_sockets_in_place(node, input_specs, output_specs)

    def _sync_switch_node_sockets(node):
        socket_idname = _switch_socket_idname_for_mode(getattr(node, "mode", "FLOAT"))
        _sync_node_sockets_in_place(
            node,
            [("NodeSocketBool", "Switch"), (socket_idname, "False"), (socket_idname, "True")],
            [(socket_idname, "Output")],
        )

    def _sync_convert_value_node_sockets(node):
        input_socket_type, output_socket_type = CONVERSION_SOCKET_MAP[getattr(node, "conversion_mode", "FLOAT_TO_INT")]
        _sync_node_sockets_in_place(node, [(input_socket_type, "Value")], [(output_socket_type, "Value")])

    def _sync_math_node_sockets(node):
        operation = str(getattr(node, "operation", "ADD") or "ADD")
        unary_input_names = {
            "SQRT": ("Value",),
            "INVERSE_SQRT": ("Value",),
            "ABSOLUTE": ("Value",),
            "EXPONENT": ("Value",),
            "SIGN": ("Value",),
            "ROUND": ("Value",),
            "FLOOR": ("Value",),
            "CEIL": ("Value",),
            "TRUNC": ("Value",),
            "FRACT": ("Value",),
            "SINE": ("Value",),
            "COSINE": ("Value",),
            "TANGENT": ("Value",),
            "ARCSINE": ("Value",),
            "ARCCOSINE": ("Value",),
            "ARCTANGENT": ("Value",),
            "SINH": ("Value",),
            "COSH": ("Value",),
            "TANH": ("Value",),
            "RADIANS": ("Value",),
            "DEGREES": ("Value",),
        }
        binary_input_names = {
            "POWER": ("Base", "Exponent"),
            "LOGARITHM": ("Value", "Base"),
            "LESS_THAN": ("Value", "Threshold"),
            "GREATER_THAN": ("Value", "Threshold"),
            "SNAP": ("Value", "Increment"),
            "PINGPONG": ("Value", "Scale"),
        }
        ternary_input_names = {
            "MULTIPLY_ADD": ("Value", "Multiplier", "Addend"),
            "COMPARE": ("A", "B", "Epsilon"),
            "SMOOTH_MIN": ("A", "B", "Distance"),
            "SMOOTH_MAX": ("A", "B", "Distance"),
            "WRAP": ("Value", "Min", "Max"),
        }

        if operation in unary_input_names:
            input_specs = [("NodeSocketFloat", name) for name in unary_input_names[operation]]
        elif operation in ternary_input_names:
            input_specs = [("NodeSocketFloat", name) for name in ternary_input_names[operation]]
        else:
            input_names = binary_input_names.get(operation, ("A", "B"))
            input_specs = [("NodeSocketFloat", name) for name in input_names]
        _sync_node_sockets_in_place(node, input_specs, [("NodeSocketFloat", "Value")])

    def _sync_integer_math_node_sockets(node):
        operation = str(getattr(node, "operation", "ADD") or "ADD")
        if operation in {"ABSOLUTE", "NEGATE", "SIGN"}:
            input_specs = [("NodeSocketInt", "Value")]
        elif operation == "MULTIPLY_ADD":
            input_specs = [
                ("NodeSocketInt", "Value"),
                ("NodeSocketInt", "Multiplier"),
                ("NodeSocketInt", "Addend"),
            ]
        elif operation == "POWER":
            input_specs = [("NodeSocketInt", "Base"), ("NodeSocketInt", "Exponent")]
        else:
            input_specs = [("NodeSocketInt", "A"), ("NodeSocketInt", "B")]
        _sync_node_sockets_in_place(node, input_specs, [("NodeSocketInt", "Value")])

    def _sync_boolean_math_node_sockets(node):
        operation = str(getattr(node, "operation", "AND") or "AND")
        if operation == "NOT":
            _sync_node_sockets_in_place(node, [("NodeSocketBool", "Boolean")], [("NodeSocketBool", "Boolean")])
            return
        _sync_node_sockets_in_place(node, [("NodeSocketBool", "A"), ("NodeSocketBool", "B")], [("NodeSocketBool", "Boolean")])

    def _sync_vector_math_node_sockets(node):
        operation = str(getattr(node, "operation", "ADD") or "ADD")
        if operation == "LENGTH":
            _sync_node_sockets_in_place(node, [("NodeSocketVector", "Vector")], [("NodeSocketFloat", "Value")])
            return
        if operation in {"NORMALIZE", "ABSOLUTE", "SIGN", "ROUND", "FLOOR", "CEIL", "FRACTION", "SINE", "COSINE", "TANGENT"}:
            _sync_node_sockets_in_place(node, [("NodeSocketVector", "Vector")], [("NodeSocketVector", "Vector")])
            return
        if operation == "SCALE":
            _sync_node_sockets_in_place(
                node,
                [("NodeSocketVector", "Vector"), ("NodeSocketFloat", "Scale")],
                [("NodeSocketVector", "Vector")],
            )
            return
        if operation in {"DISTANCE", "DOT_PRODUCT"}:
            _sync_node_sockets_in_place(
                node,
                [("NodeSocketVector", "A"), ("NodeSocketVector", "B")],
                [("NodeSocketFloat", "Value")],
            )
            return
        if operation == "PROJECT":
            _sync_node_sockets_in_place(
                node,
                [("NodeSocketVector", "Vector"), ("NodeSocketVector", "On")],
                [("NodeSocketVector", "Vector")],
            )
            return
        if operation == "REFLECT":
            _sync_node_sockets_in_place(
                node,
                [("NodeSocketVector", "Vector"), ("NodeSocketVector", "Normal")],
                [("NodeSocketVector", "Vector")],
            )
            return
        if operation == "REFRACT":
            _sync_node_sockets_in_place(
                node,
                [("NodeSocketVector", "Vector"), ("NodeSocketVector", "Normal"), ("NodeSocketFloat", "IOR")],
                [("NodeSocketVector", "Vector")],
            )
            return
        if operation == "FACEFORWARD":
            _sync_node_sockets_in_place(
                node,
                [("NodeSocketVector", "Vector"), ("NodeSocketVector", "Incident"), ("NodeSocketVector", "Reference")],
                [("NodeSocketVector", "Vector")],
            )
            return
        if operation == "MULTIPLY_ADD":
            _sync_node_sockets_in_place(
                node,
                [("NodeSocketVector", "Vector"), ("NodeSocketVector", "Multiplier"), ("NodeSocketVector", "Addend")],
                [("NodeSocketVector", "Vector")],
            )
            return
        if operation == "POWER":
            _sync_node_sockets_in_place(
                node,
                [("NodeSocketVector", "Base"), ("NodeSocketVector", "Exponent")],
                [("NodeSocketVector", "Vector")],
            )
            return
        if operation == "WRAP":
            _sync_node_sockets_in_place(
                node,
                [("NodeSocketVector", "Vector"), ("NodeSocketVector", "Min"), ("NodeSocketVector", "Max")],
                [("NodeSocketVector", "Vector")],
            )
            return
        if operation == "SNAP":
            _sync_node_sockets_in_place(
                node,
                [("NodeSocketVector", "Vector"), ("NodeSocketVector", "Increment")],
                [("NodeSocketVector", "Vector")],
            )
            return
        _sync_node_sockets_in_place(node, [("NodeSocketVector", "A"), ("NodeSocketVector", "B")], [("NodeSocketVector", "Vector")])

    class AFNodeMath(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeMath"
        bl_label = "Math"
        bl_icon = "BLANK1"

        operation: bpy.props.EnumProperty(
            name="Operation",
            items=FLOAT_MATH_OPERATION_ITEMS,
            default="ADD",
            update=lambda self, context: self._sync_sockets(),
        )
        use_clamp: bpy.props.BoolProperty(name="Clamp", default=False)

        def init(self, context):
            self._sync_sockets()
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            layout.prop(self, "operation", text="")
            layout.prop(self, "use_clamp")

        def draw_label(self):
            return _enum_property_label(self, "operation", self.bl_label)

        def _sync_sockets(self):
            _sync_math_node_sockets(self)

    class AFNodeIntegerMath(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeIntegerMath"
        bl_label = "Integer Math"
        bl_icon = "BLANK1"

        operation: bpy.props.EnumProperty(
            name="Operation",
            items=INTEGER_MATH_OPERATION_ITEMS,
            default="ADD",
            update=lambda self, context: self._sync_sockets(),
        )

        def init(self, context):
            self._sync_sockets()
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            layout.prop(self, "operation", text="")

        def draw_label(self):
            return _enum_property_label(self, "operation", self.bl_label)

        def _sync_sockets(self):
            _sync_integer_math_node_sockets(self)

    class AFNodeBooleanMath(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeBooleanMath"
        bl_label = "Boolean Math"
        bl_icon = "BLANK1"

        operation: bpy.props.EnumProperty(
            name="Operation",
            items=BOOLEAN_MATH_OPERATION_ITEMS,
            default="AND",
            update=lambda self, context: self._sync_sockets(),
        )

        def init(self, context):
            self._sync_sockets()
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            layout.prop(self, "operation", text="")

        def draw_label(self):
            return _enum_property_label(self, "operation", self.bl_label)

        def _sync_sockets(self):
            _sync_boolean_math_node_sockets(self)

    class AFNodeVectorMath(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeVectorMath"
        bl_label = "Vector Math"
        bl_icon = "BLANK1"

        operation: bpy.props.EnumProperty(
            name="Operation",
            items=VECTOR_MATH_OPERATION_ITEMS,
            default="ADD",
            update=lambda self, context: self._sync_sockets(),
        )

        def init(self, context):
            self._sync_sockets()
            _set_node_color(self, "VECTOR")

        def draw_buttons(self, context, layout):
            layout.prop(self, "operation", text="")

        def draw_label(self):
            return _enum_property_label(self, "operation", self.bl_label)

        def _sync_sockets(self):
            _sync_vector_math_node_sockets(self)

    class AFNodeMix(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeMix"
        bl_label = "Mix"
        bl_icon = "BLANK1"

        mode: bpy.props.EnumProperty(
            name="Mode",
            items=MIX_MODE_ITEMS,
            default="FLOAT",
            update=lambda self, context: self._sync_sockets(),
        )
        clamp_factor: bpy.props.BoolProperty(name="Clamp Factor", default=True)

        def init(self, context):
            self._sync_sockets()
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            layout.prop(self, "mode", text="")
            layout.prop(self, "clamp_factor")

        def _sync_sockets(self):
            _sync_mix_node_sockets(self)

    class AFNodeSwitch(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSwitch"
        bl_label = "Switch"
        bl_icon = "BLANK1"

        mode: bpy.props.EnumProperty(
            name="Mode",
            items=SWITCH_MODE_ITEMS,
            default="FLOAT",
            update=lambda self, context: self._sync_sockets(),
        )

        def init(self, context):
            self._sync_sockets()
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            layout.prop(self, "mode", text="")

        def _sync_sockets(self):
            _sync_switch_node_sockets(self)

    class AFNodeIndexSwitch(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeIndexSwitch"
        bl_label = "Index Switch"
        bl_icon = "BLANK1"

        mode: bpy.props.EnumProperty(
            name="Mode",
            items=INDEX_SWITCH_MODE_ITEMS,
            default="FLOAT",
            update=lambda self, context: self._sync_sockets(),
        )

        def init(self, context):
            del context
            self._sync_sockets()
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "mode", text="")

        def _sync_sockets(self):
            _sync_index_switch_sockets(self)

        def update(self):
            _sync_index_switch_sockets(self)

    class AFNodeCompare(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeCompare"
        bl_label = "Compare"
        bl_icon = "BLANK1"

        mode: bpy.props.EnumProperty(
            name="Mode",
            items=COMPARE_MODE_ITEMS,
            default="FLOAT",
            update=lambda self, context: self._sync_sockets(),
        )
        operation: bpy.props.EnumProperty(
            name="Operation",
            items=COMPARE_OPERATION_ITEMS,
            default="EQUAL",
            update=lambda self, context: self._sync_sockets(),
        )
        string_operation: bpy.props.EnumProperty(name="String Operation", items=STRING_COMPARE_OPERATION_ITEMS, default="EQUAL")
        vector_mode: bpy.props.EnumProperty(
            name="Vector Mode",
            items=COMPARE_VECTOR_MODE_ITEMS,
            default="ELEMENT",
            update=lambda self, context: self._sync_sockets(),
        )
        threshold: bpy.props.FloatProperty(name="Threshold", default=0.001, min=0.0)

        def init(self, context):
            self._sync_sockets()
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            layout.prop(self, "mode", text="")
            if self.mode == "VECTOR":
                layout.prop(self, "vector_mode", text="")
            if self.mode == "STRING":
                layout.prop(self, "string_operation", text="")
                return
            layout.prop(self, "operation", text="")

        def draw_label(self):
            if self.mode == "STRING":
                return _enum_property_label(self, "string_operation", self.bl_label)
            return _enum_property_label(self, "operation", self.bl_label)

        def _sync_sockets(self):
            _sync_compare_node_sockets(self)

    class AFNodeConvertValue(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeConvertValue"
        bl_label = "Convert"
        bl_icon = "BLANK1"

        conversion_mode: bpy.props.EnumProperty(
            name="Mode",
            items=CONVERSION_MODE_ITEMS,
            default="FLOAT_TO_INT",
            update=lambda self, context: self._sync_sockets(),
        )
        vector_component_mode: bpy.props.EnumProperty(name="Vector Component", items=VECTOR_COMPONENT_MODE_ITEMS, default="X")
        vector_bool_mode: bpy.props.EnumProperty(name="Vector Boolean", items=VECTOR_BOOL_MODE_ITEMS, default="ANY_NONZERO")
        epsilon: bpy.props.FloatProperty(name="Epsilon", default=1e-6, min=0.0)

        def init(self, context):
            del context
            self._sync_sockets()
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "conversion_mode", text="")
            if self.conversion_mode.startswith("VECTOR_TO_"):
                if self.conversion_mode == "VECTOR_TO_BOOL":
                    layout.prop(self, "vector_bool_mode", text="")
                else:
                    layout.prop(self, "vector_component_mode", text="")
                layout.prop(self, "epsilon")

        def _sync_sockets(self):
            _sync_convert_value_node_sockets(self)

    class AFNodeClamp(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeClamp"
        bl_label = "Clamp"
        bl_icon = "BLANK1"

        def init(self, context):
            self.inputs.new("NodeSocketFloat", "Value")
            self.inputs.new("NodeSocketFloat", "Min")
            self.inputs.new("NodeSocketFloat", "Max")
            self.outputs.new("NodeSocketFloat", "Result")
            _set_node_color(self, "CONVERTER")

    class AFNodeMapRange(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeMapRange"
        bl_label = "Map Range"
        bl_icon = "BLANK1"

        mode: bpy.props.EnumProperty(
            name="Mode",
            items=MAP_RANGE_MODE_ITEMS,
            default="FLOAT",
            update=lambda self, context: self._sync_sockets(),
        )
        clamp: bpy.props.BoolProperty(name="Clamp", default=True)

        def init(self, context):
            self._sync_sockets()
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            layout.prop(self, "mode", text="")
            layout.prop(self, "clamp")

        def _sync_sockets(self):
            _sync_map_range_node_sockets(self)

    class AFNodeCombineVector(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeCombineVector"
        bl_label = "Combine Vector"
        bl_icon = "BLANK1"

        def init(self, context):
            self.inputs.new("NodeSocketFloat", "X")
            self.inputs.new("NodeSocketFloat", "Y")
            self.inputs.new("NodeSocketFloat", "Z")
            self.outputs.new("NodeSocketVector", "Vector")
            _set_node_color(self, "VECTOR")

    class AFNodeSeparateVector(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSeparateVector"
        bl_label = "Separate Vector"
        bl_icon = "BLANK1"

        def init(self, context):
            self.inputs.new("NodeSocketVector", "Vector")
            self.outputs.new("NodeSocketFloat", "X")
            self.outputs.new("NodeSocketFloat", "Y")
            self.outputs.new("NodeSocketFloat", "Z")
            _set_node_color(self, "VECTOR")

    class AFNodeVectorRotate(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeVectorRotate"
        bl_label = "Vector Rotate"
        bl_icon = "BLANK1"

        def init(self, context):
            self.inputs.new("NodeSocketVector", "Vector")
            self.inputs.new("NodeSocketVector", "Axis")
            self.inputs.new("NodeSocketFloat", "Angle")
            self.outputs.new("NodeSocketVector", "Vector")
            _set_node_color(self, "VECTOR")

    class AFNodeRotateVector(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRotateVector"
        bl_label = "Rotate Vector"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketVector", "Vector")
            self.inputs.new("NodeSocketRotation", "Rotation")
            self.outputs.new("NodeSocketVector", "Vector")
            _set_node_color(self, "VECTOR")

    class AFNodeEulerToRotation(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeEulerToRotation"
        bl_label = "Euler to Rotation"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketVector", "Euler")
            self.outputs.new("NodeSocketRotation", "Rotation")
            _set_node_color(self, "CONVERTER")

    class AFNodeQuaternionToRotation(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeQuaternionToRotation"
        bl_label = "Quaternion to Rotation"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketFloat", "W")
            self.inputs.new("NodeSocketFloat", "X")
            self.inputs.new("NodeSocketFloat", "Y")
            self.inputs.new("NodeSocketFloat", "Z")
            self.outputs.new("NodeSocketRotation", "Rotation")
            _set_node_color(self, "CONVERTER")

    class AFNodeAxisAngleToRotation(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeAxisAngleToRotation"
        bl_label = "Axis Angle to Rotation"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketVector", "Axis")
            self.inputs.new("NodeSocketFloat", "Angle")
            self.outputs.new("NodeSocketRotation", "Rotation")
            _set_node_color(self, "CONVERTER")

    class AFNodeInvertRotation(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeInvertRotation"
        bl_label = "Invert Rotation"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketRotation", "Rotation")
            self.outputs.new("NodeSocketRotation", "Rotation")
            _set_node_color(self, "CONVERTER")

    class AFNodeRotateRotation(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRotateRotation"
        bl_label = "Rotate Rotation"
        bl_icon = "BLANK1"

        rotation_space: bpy.props.EnumProperty(name="Rotation Space", items=ROTATION_SPACE_ITEMS, default="GLOBAL")

        def init(self, context):
            del context
            self.inputs.new("NodeSocketRotation", "Rotation")
            self.inputs.new("NodeSocketRotation", "Rotate By")
            self.outputs.new("NodeSocketRotation", "Rotation")
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "rotation_space", text="")

    class AFNodeRotationToEuler(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRotationToEuler"
        bl_label = "Rotation to Euler"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketRotation", "Rotation")
            self.outputs.new("NodeSocketVector", "Euler")
            _set_node_color(self, "CONVERTER")

    class AFNodeRotationToQuaternion(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRotationToQuaternion"
        bl_label = "Rotation to Quaternion"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketRotation", "Rotation")
            self.outputs.new("NodeSocketFloat", "W")
            self.outputs.new("NodeSocketFloat", "X")
            self.outputs.new("NodeSocketFloat", "Y")
            self.outputs.new("NodeSocketFloat", "Z")
            _set_node_color(self, "CONVERTER")

    class AFNodeRotationToAxisAngle(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRotationToAxisAngle"
        bl_label = "Rotation to Axis Angle"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketRotation", "Rotation")
            self.outputs.new("NodeSocketVector", "Axis")
            self.outputs.new("NodeSocketFloat", "Angle")
            _set_node_color(self, "CONVERTER")

    class AFNodeAxesToRotation(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeAxesToRotation"
        bl_label = "Axes to Rotation"
        bl_icon = "BLANK1"

        primary_axis: bpy.props.EnumProperty(name="Primary Axis", items=ROTATION_AXIS_ITEMS, default="Z")
        secondary_axis: bpy.props.EnumProperty(name="Secondary Axis", items=ROTATION_AXIS_ITEMS, default="X")

        def init(self, context):
            del context
            self.inputs.new("NodeSocketVector", "Primary Axis")
            self.inputs.new("NodeSocketVector", "Secondary Axis")
            self.outputs.new("NodeSocketRotation", "Rotation")
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "primary_axis", text="")
            layout.prop(self, "secondary_axis", text="")

    class AFNodeAlignRotationToVector(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeAlignRotationToVector"
        bl_label = "Align Rotation to Vector"
        bl_icon = "BLANK1"

        axis: bpy.props.EnumProperty(name="Axis", items=ROTATION_AXIS_ITEMS, default="Z")
        pivot_axis: bpy.props.EnumProperty(name="Pivot Axis", items=ROTATION_PIVOT_AXIS_ITEMS, default="AUTO")

        def init(self, context):
            del context
            self.inputs.new("NodeSocketRotation", "Rotation")
            self.inputs.new("NodeSocketFloat", "Factor")
            self.inputs.new("NodeSocketVector", "Vector")
            self.outputs.new("NodeSocketRotation", "Rotation")
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "axis", text="")
            layout.prop(self, "pivot_axis", text="")

    def _matrix_input_specs():
        specs = []
        for column in range(1, 5):
            for row in range(1, 5):
                specs.append(("NodeSocketFloat", f"Column {column} Row {row}"))
        return specs

    def _matrix_output_specs():
        specs = []
        for column in range(1, 5):
            for row in range(1, 5):
                specs.append(("NodeSocketFloat", f"Column {column} Row {row}"))
        return specs

    class AFNodeCombineMatrix(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeCombineMatrix"
        bl_label = "Combine Matrix"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            _sync_node_sockets_in_place(self, _matrix_input_specs(), [("NodeSocketMatrix", "Matrix")])
            _set_default_node_width(self, multiplier=(4.0 / 3.0))
            _set_node_color(self, "CONVERTER")

    class AFNodeSeparateMatrix(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSeparateMatrix"
        bl_label = "Separate Matrix"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            _sync_node_sockets_in_place(self, [("NodeSocketMatrix", "Matrix")], _matrix_output_specs())
            _set_default_node_width(self, multiplier=(4.0 / 3.0))
            _set_node_color(self, "CONVERTER")

    class AFNodeMatrixMultiply(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeMatrixMultiply"
        bl_label = "Multiply Matrices"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketMatrix", "Matrix A")
            self.inputs.new("NodeSocketMatrix", "Matrix B")
            self.outputs.new("NodeSocketMatrix", "Matrix")
            _set_node_color(self, "CONVERTER")

    class AFNodeInvertMatrix(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeInvertMatrix"
        bl_label = "Invert Matrix"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketMatrix", "Matrix")
            self.outputs.new("NodeSocketMatrix", "Matrix")
            self.outputs.new("NodeSocketBool", "Invertible")
            _set_node_color(self, "CONVERTER")

    class AFNodeTransposeMatrix(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeTransposeMatrix"
        bl_label = "Transpose Matrix"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketMatrix", "Matrix")
            self.outputs.new("NodeSocketMatrix", "Matrix")
            _set_node_color(self, "CONVERTER")

    class AFNodeMatrixDeterminant(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeMatrixDeterminant"
        bl_label = "Matrix Determinant"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketMatrix", "Matrix")
            self.outputs.new("NodeSocketFloat", "Determinant")
            _set_node_color(self, "CONVERTER")

    class AFNodeCombineTransform(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeCombineTransform"
        bl_label = "Combine Transform"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketVector", "Translation")
            self.inputs.new("NodeSocketRotation", "Rotation")
            scale_socket = self.inputs.new("NodeSocketVector", "Scale")
            try:
                scale_socket.default_value = (1.0, 1.0, 1.0)
            except Exception:
                pass
            self.outputs.new("NodeSocketMatrix", "Matrix")
            _set_node_color(self, "CONVERTER")

    class AFNodeSeparateTransform(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSeparateTransform"
        bl_label = "Separate Transform"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketMatrix", "Matrix")
            self.outputs.new("NodeSocketVector", "Translation")
            self.outputs.new("NodeSocketRotation", "Rotation")
            self.outputs.new("NodeSocketVector", "Scale")
            _set_node_color(self, "CONVERTER")

    class AFNodeTransformPoint(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeTransformPoint"
        bl_label = "Transform Point"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketVector", "Point")
            self.inputs.new("NodeSocketMatrix", "Matrix")
            self.outputs.new("NodeSocketVector", "Point")
            _set_node_color(self, "CONVERTER")

    class AFNodeTransformDirection(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeTransformDirection"
        bl_label = "Transform Direction"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketVector", "Direction")
            self.inputs.new("NodeSocketMatrix", "Matrix")
            self.outputs.new("NodeSocketVector", "Direction")
            _set_node_color(self, "CONVERTER")

    class AFNodeProjectPoint(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeProjectPoint"
        bl_label = "Project Point"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("NodeSocketVector", "Point")
            self.inputs.new("NodeSocketMatrix", "Matrix")
            self.outputs.new("NodeSocketVector", "Point")
            _set_node_color(self, "CONVERTER")

    class AFNodeSmoothstep(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSmoothstep"
        bl_label = "Smoothstep"
        bl_icon = "BLANK1"

        def init(self, context):
            self.inputs.new("NodeSocketFloat", "Value")
            self.inputs.new("NodeSocketFloat", "Edge0")
            self.inputs.new("NodeSocketFloat", "Edge1")
            self.outputs.new("NodeSocketFloat", "Result")
            _set_node_color(self, "CONVERTER")

    class AFNodeRandomValue(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRandomValue"
        bl_label = "Random Value"
        bl_icon = "BLANK1"

        value_type: bpy.props.EnumProperty(
            name="Type",
            items=RANDOM_TYPE_ITEMS,
            default="FLOAT",
            update=lambda self, context: self._sync_sockets(),
        )

        def init(self, context):
            self._sync_sockets()
            _set_node_color(self, "CONVERTER")

        def draw_buttons(self, context, layout):
            layout.prop(self, "value_type")

        def _sync_sockets(self):
            if self.value_type == "VECTOR":
                _sync_node_sockets_in_place(
                    self,
                    [("NodeSocketInt", "Seed"), ("NodeSocketVector", "Min"), ("NodeSocketVector", "Max")],
                    [("NodeSocketVector", "Value")],
                )
            elif self.value_type == "BOOLEAN":
                _sync_node_sockets_in_place(
                    self,
                    [("NodeSocketInt", "Seed")],
                    [("NodeSocketBool", "Value")],
                )
            else:
                _sync_node_sockets_in_place(
                    self,
                    [("NodeSocketInt", "Seed"), ("NodeSocketFloat", "Min"), ("NodeSocketFloat", "Max")],
                    [("NodeSocketFloat", "Value")],
                )

    return {
        "AFNodeMath": AFNodeMath,
        "AFNodeIntegerMath": AFNodeIntegerMath,
        "AFNodeBooleanMath": AFNodeBooleanMath,
        "AFNodeVectorMath": AFNodeVectorMath,
        "AFNodeMix": AFNodeMix,
        "AFNodeSwitch": AFNodeSwitch,
        "AFNodeIndexSwitch": AFNodeIndexSwitch,
        "AFNodeCompare": AFNodeCompare,
        "AFNodeConvertValue": AFNodeConvertValue,
        "AFNodeClamp": AFNodeClamp,
        "AFNodeMapRange": AFNodeMapRange,
        "AFNodeCombineVector": AFNodeCombineVector,
        "AFNodeSeparateVector": AFNodeSeparateVector,
        "AFNodeVectorRotate": AFNodeVectorRotate,
        "AFNodeRotateVector": AFNodeRotateVector,
        "AFNodeEulerToRotation": AFNodeEulerToRotation,
        "AFNodeQuaternionToRotation": AFNodeQuaternionToRotation,
        "AFNodeAxisAngleToRotation": AFNodeAxisAngleToRotation,
        "AFNodeInvertRotation": AFNodeInvertRotation,
        "AFNodeRotateRotation": AFNodeRotateRotation,
        "AFNodeRotationToEuler": AFNodeRotationToEuler,
        "AFNodeRotationToQuaternion": AFNodeRotationToQuaternion,
        "AFNodeRotationToAxisAngle": AFNodeRotationToAxisAngle,
        "AFNodeAxesToRotation": AFNodeAxesToRotation,
        "AFNodeAlignRotationToVector": AFNodeAlignRotationToVector,
        "AFNodeCombineMatrix": AFNodeCombineMatrix,
        "AFNodeSeparateMatrix": AFNodeSeparateMatrix,
        "AFNodeMatrixMultiply": AFNodeMatrixMultiply,
        "AFNodeInvertMatrix": AFNodeInvertMatrix,
        "AFNodeTransposeMatrix": AFNodeTransposeMatrix,
        "AFNodeMatrixDeterminant": AFNodeMatrixDeterminant,
        "AFNodeCombineTransform": AFNodeCombineTransform,
        "AFNodeSeparateTransform": AFNodeSeparateTransform,
        "AFNodeTransformPoint": AFNodeTransformPoint,
        "AFNodeTransformDirection": AFNodeTransformDirection,
        "AFNodeProjectPoint": AFNodeProjectPoint,
        "AFNodeSmoothstep": AFNodeSmoothstep,
        "AFNodeRandomValue": AFNodeRandomValue,
    }
