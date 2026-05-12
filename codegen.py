class CodeGenerator:
    BIN_OP_MAP = {"&&": "and", "||": "or"}

    def __init__(self):
        self.ir = []
        self.uses_printf = False

    def generate(self, node):
        self.ir = []
        self.uses_printf = False
        lines = self._emit_program(node)

        if self.uses_printf:
            helper_lines = self._printf_helper_lines()
            lines = helper_lines + ([""] if lines else []) + lines

        return "\n".join(lines).strip()

    def _emit_program(self, node):
        if node[0] != "program":
            return self._emit_statement(node, 0)

        items = node[1]
        lines = []
        has_main = any(item[0] == "func" and item[2] == "main" for item in items)

        for index, item in enumerate(items):
            item_lines = self._emit_top_level(item)
            if not item_lines:
                continue
            if lines and item[0] == "func":
                lines.append("")
            lines.extend(item_lines)
            if item[0] == "func" and index != len(items) - 1:
                lines.append("")

        while lines and lines[-1] == "":
            lines.pop()

        if has_main:
            if lines:
                lines.append("")
            lines.append('if __name__ == "__main__":')
            lines.append("    main()")

        return lines

    def _emit_top_level(self, node):
        if node[0] == "func":
            return self._emit_function(node, 0)
        return self._emit_statement(node, 0)

    def _emit_function(self, node, indent):
        _, return_type, name, params, body, pointer_depth = node
        del return_type, pointer_depth
        param_names = [param[1] for param in params]
        self.ir.append(f"func {name}({', '.join(param_names)})")

        lines = [f"{self._indent(indent)}def {name}({', '.join(param_names)}):"]
        lines.extend(self._emit_block(body, indent + 1))
        return lines

    def _emit_statement(self, node, indent):
        kind = node[0]

        if kind == "empty":
            return []

        if kind == "block":
            lines = []
            for statement in node[1]:
                lines.extend(self._emit_statement(statement, indent))
            return lines

        if kind == "decl":
            _, base_type, name, dimensions, initializer, pointer_depth = node
            value = self._declaration_value(base_type, dimensions, initializer, pointer_depth)
            line = f"{name} = {value}"
            self.ir.append(line)
            return [f"{self._indent(indent)}{line}"]

        if kind == "expr_stmt":
            line = self._emit_expression_statement(node[1])
            self.ir.append(line)
            return [f"{self._indent(indent)}{line}"]

        if kind == "if":
            condition = self._emit_expr(node[1])
            self.ir.append(f"if {condition}")
            lines = [f"{self._indent(indent)}if {condition}:"]
            lines.extend(self._emit_block(node[2], indent + 1))
            if node[3] is not None:
                self.ir.append("else")
                lines.append(f"{self._indent(indent)}else:")
                lines.extend(self._emit_block(node[3], indent + 1))
            return lines

        if kind == "for":
            return self._emit_for_statement(node, indent)

        if kind == "while":
            condition = self._emit_expr(node[1])
            self.ir.append(f"while {condition}")
            lines = [f"{self._indent(indent)}while {condition}:"]
            lines.extend(self._emit_block(node[2], indent + 1))
            return lines

        if kind == "return":
            if node[1] is None:
                self.ir.append("return")
                return [f"{self._indent(indent)}return"]
            expr = self._emit_expr(node[1])
            self.ir.append(f"return {expr}")
            return [f"{self._indent(indent)}return {expr}"]

        raise SyntaxError(f"Unsupported statement node: {kind}")

    def _emit_block(self, node, indent, allow_empty=False):
        lines = self._emit_statement(node, indent)
        if lines or allow_empty:
            return lines
        return [f"{self._indent(indent)}pass"]

    def _emit_for_statement(self, node, indent):
        init, condition, update, body = node[1], node[2], node[3], node[4]
        range_loop = self._match_range_loop(init, condition, update)

        if range_loop is not None:
            var_name, range_code = range_loop
            self.ir.append(f"for {var_name} in {range_code}")
            lines = [f"{self._indent(indent)}for {var_name} in {range_code}:"]
            body_lines = self._emit_block(body, indent + 1, allow_empty=True)
            lines.extend(body_lines if body_lines else [f"{self._indent(indent + 1)}pass"])
            return lines

        lines = []
        if init is not None:
            lines.extend(self._emit_statement(init, indent))
        cond_code = self._emit_expr(condition) if condition is not None else "True"
        self.ir.append(f"for (...; {cond_code}; ...)")
        lines.append(f"{self._indent(indent)}while {cond_code}:")
        body_lines = self._emit_block(body, indent + 1, allow_empty=True)
        update_lines = self._emit_statement(update, indent + 1) if update is not None else []
        loop_lines = body_lines + update_lines
        if not loop_lines:
            loop_lines = [f"{self._indent(indent + 1)}pass"]
        lines.extend(loop_lines)
        return lines

    def _emit_expression_statement(self, expr):
        if expr[0] == "assign_expr":
            return self._emit_assignment(expr[2], expr[1], expr[3])
        if expr[0] == "update_expr":
            return self._emit_update(expr)
        return self._emit_expr(expr)

    def _emit_assignment(self, target, operator, value):
        target_code = self._emit_lvalue(target)
        value_code = self._emit_expr(value)
        if operator == "=":
            return f"{target_code} = {value_code}"
        return f"{target_code} {operator} {value_code}"

    def _emit_update(self, expr):
        _, position, operator, target = expr
        del position
        target_code = self._emit_lvalue(target)
        assignment_op = "+=" if operator == "++" else "-="
        return f"{target_code} {assignment_op} 1"

    def _emit_lvalue(self, node):
        if node[0] == "var":
            return node[1]
        if node[0] == "index":
            return f"{self._emit_expr(node[1])}[{self._emit_expr(node[2])}]"
        raise SyntaxError(f"Unsupported assignment target: {node}")

    def _emit_expr(self, node):
        kind = node[0]

        if kind == "num":
            return node[1]

        if kind in {"str", "char"}:
            return repr(node[1])

        if kind == "var":
            return node[1]

        if kind == "index":
            return f"{self._emit_expr(node[1])}[{self._emit_expr(node[2])}]"

        if kind == "binop":
            op = self.BIN_OP_MAP.get(node[1], node[1])
            left = self._emit_expr(node[2])
            right = self._emit_expr(node[3])
            return f"({left} {op} {right})"

        if kind == "unary":
            op = node[1]
            value = self._emit_expr(node[2])
            if op == "!":
                return f"(not {value})"
            return f"({op}{value})"

        if kind == "call":
            callee = node[1]
            if callee[0] == "var" and callee[1] == "printf":
                return self._emit_printf_call(node[2])
            args = ", ".join(self._emit_expr(arg) for arg in node[2])
            return f"{self._emit_expr(callee)}({args})"

        if kind in {"assign_expr", "update_expr"}:
            raise SyntaxError(
                "Assignments and ++/-- are only supported as standalone statements or for-loop updates."
            )

        if kind == "array_init":
            return self._emit_array_initializer(node)

        raise SyntaxError(f"Unsupported expression node: {kind}")

    def _declaration_value(self, base_type, dimensions, initializer, pointer_depth):
        if pointer_depth and not dimensions:
            if initializer is None:
                return "None"
            return self._emit_expr(initializer)

        if not dimensions:
            if initializer is None:
                return self._default_scalar(base_type)
            return self._emit_expr(initializer)

        return self._emit_array_declaration(base_type, dimensions, initializer)

    def _emit_array_declaration(self, base_type, dimensions, initializer):
        size_codes = [self._emit_expr(size) if size is not None else None for size in dimensions]
        default_value = self._default_array_value(base_type)

        if initializer is None:
            if any(size is None for size in size_codes):
                return "[]"
            return self._nested_default_array(size_codes, default_value)

        if base_type == "char" and initializer[0] == "str":
            literal = [repr(ch) for ch in initializer[1]]
            init_code = f"[{', '.join(literal)}]"
            if size_codes[0] is None:
                return init_code
            return f"({init_code} + [{default_value}] * max(0, {size_codes[0]} - len({init_code})))[:{size_codes[0]}]"

        if initializer[0] == "array_init":
            init_code = self._emit_array_initializer(initializer)
            if len(size_codes) == 1 and size_codes[0] is not None:
                return f"({init_code} + [{default_value}] * max(0, {size_codes[0]} - len({init_code})))[:{size_codes[0]}]"
            return init_code

        value_code = self._emit_expr(initializer)
        if size_codes[0] is None:
            return f"[{value_code}]"
        return f"[{value_code}] * {size_codes[0]}"

    def _emit_array_initializer(self, node):
        values = []
        for item in node[1]:
            if item[0] == "array_init":
                values.append(self._emit_array_initializer(item))
            else:
                values.append(self._emit_expr(item))
        return f"[{', '.join(values)}]"

    def _nested_default_array(self, sizes, default_value):
        if len(sizes) == 1:
            return f"[{default_value}] * {sizes[0]}"
        inner = self._nested_default_array(sizes[1:], default_value)
        return f"[{inner} for _ in range({sizes[0]})]"

    def _default_scalar(self, base_type):
        if "float" in base_type or "double" in base_type:
            return "0.0"
        if "char" in base_type:
            return repr("\0")
        return "0"

    def _default_array_value(self, base_type):
        if "float" in base_type or "double" in base_type:
            return "0.0"
        if "char" in base_type:
            return repr("\0")
        return "0"

    def _printf_helper_lines(self):
        return [
            "def _normalize_c_format(fmt):",
            "    replacements = [",
            "        ('%lld', '%d'),",
            "        ('%llu', '%d'),",
            "        ('%ld', '%d'),",
            "        ('%li', '%d'),",
            "        ('%lu', '%d'),",
            "        ('%lf', '%f'),",
            "        ('%i', '%d'),",
            "        ('%u', '%d'),",
            "    ]",
            "    for source, target in replacements:",
            "        fmt = fmt.replace(source, target)",
            "    return fmt",
            "",
            "def _coerce_c_printf_arg(value):",
            "    if isinstance(value, list) and all(isinstance(ch, str) and len(ch) == 1 for ch in value):",
            "        chars = []",
            "        for ch in value:",
            "            if ch == '\\0':",
            "                break",
            "            chars.append(ch)",
            "        return ''.join(chars)",
            "    return value",
            "",
            "def _c_printf(fmt, *args):",
            "    fmt = _normalize_c_format(fmt)",
            "    values = tuple(_coerce_c_printf_arg(arg) for arg in args)",
            "    text = fmt % values if values else fmt",
            "    print(text, end='')",
        ]

    def _emit_printf_call(self, args):
        if not args:
            return "print('', end='')"

        if args[0][0] == "str":
            format_text = self._normalize_c_format_literal(args[0][1])
            specifiers = self._extract_printf_specifiers(format_text)

            if not specifiers:
                return f"print({format_text!r}, end='')"

            if "s" not in specifiers:
                rendered_args = [self._emit_expr(arg) for arg in args[1:]]
                if len(rendered_args) == 1:
                    formatted = f"({format_text!r} % {rendered_args[0]})"
                else:
                    formatted = f"({format_text!r} % ({', '.join(rendered_args)}))"
                return f"print({formatted}, end='')"

        self.uses_printf = True
        rendered_args = ", ".join(self._emit_expr(arg) for arg in args)
        return f"_c_printf({rendered_args})"

    def _normalize_c_format_literal(self, fmt):
        replacements = [
            ("%lld", "%d"),
            ("%llu", "%d"),
            ("%ld", "%d"),
            ("%li", "%d"),
            ("%lu", "%d"),
            ("%lf", "%f"),
            ("%i", "%d"),
            ("%u", "%d"),
        ]
        for source, target in replacements:
            fmt = fmt.replace(source, target)
        return fmt

    def _extract_printf_specifiers(self, fmt):
        specifiers = []
        index = 0
        length = len(fmt)

        while index < length:
            if fmt[index] != "%":
                index += 1
                continue

            if index + 1 < length and fmt[index + 1] == "%":
                index += 2
                continue

            index += 1
            while index < length and fmt[index] in "-+ #0":
                index += 1
            while index < length and fmt[index].isdigit():
                index += 1
            if index < length and fmt[index] == ".":
                index += 1
                while index < length and fmt[index].isdigit():
                    index += 1
            while index < length and fmt[index] in "hlLzjt":
                index += 1
            if index < length:
                specifiers.append(fmt[index])
            index += 1

        return specifiers

    def _match_range_loop(self, init, condition, update):
        init_match = self._parse_for_init(init)
        condition_match = self._parse_for_condition(condition)
        update_match = self._parse_for_update(update)

        if init_match is None or condition_match is None or update_match is None:
            return None

        init_var, start_expr = init_match
        cond_var, operator, stop_expr = condition_match
        update_var, step_value = update_match

        if init_var != cond_var or init_var != update_var:
            return None

        if operator == "<" and step_value > 0:
            return init_var, self._build_range_code(start_expr, stop_expr, step_value)
        if operator == ">" and step_value < 0:
            return init_var, self._build_range_code(start_expr, stop_expr, step_value)
        if operator == "<=" and step_value > 0:
            return init_var, self._build_range_code(start_expr, f"(({stop_expr}) + 1)", step_value)
        if operator == ">=" and step_value < 0:
            return init_var, self._build_range_code(start_expr, f"(({stop_expr}) - 1)", step_value)

        return None

    def _parse_for_init(self, init):
        if init is None:
            return None

        if init[0] == "decl":
            name = init[2]
            initializer = init[4]
            if initializer is None or init[3]:
                return None
            return name, self._emit_expr(initializer)

        if init[0] == "expr_stmt" and init[1][0] == "assign_expr" and init[1][1] == "=":
            target = init[1][2]
            if target[0] != "var":
                return None
            return target[1], self._emit_expr(init[1][3])

        return None

    def _parse_for_condition(self, condition):
        if condition is None or condition[0] != "binop":
            return None

        operator = condition[1]
        left = condition[2]
        right = condition[3]

        if operator not in {"<", "<=", ">", ">="}:
            return None
        if left[0] != "var":
            return None

        return left[1], operator, self._emit_expr(right)

    def _parse_for_update(self, update):
        if update is None or update[0] != "expr_stmt":
            return None

        expr = update[1]

        if expr[0] == "update_expr":
            target = expr[3]
            if target[0] != "var":
                return None
            return target[1], 1 if expr[2] == "++" else -1

        if expr[0] != "assign_expr":
            return None

        operator = expr[1]
        target = expr[2]
        value = expr[3]

        if target[0] != "var":
            return None

        if operator == "+=":
            step = self._literal_int(value)
            return None if step is None else (target[1], step)
        if operator == "-=":
            step = self._literal_int(value)
            return None if step is None else (target[1], -step)
        if operator == "=":
            step = self._step_from_assignment(target[1], value)
            return None if step is None else (target[1], step)

        return None

    def _step_from_assignment(self, var_name, value):
        if value[0] != "binop" or value[1] not in {"+", "-"}:
            return None
        if value[2][0] != "var" or value[2][1] != var_name:
            return None
        delta = self._literal_int(value[3])
        if delta is None:
            return None
        return delta if value[1] == "+" else -delta

    def _literal_int(self, node):
        if node[0] != "num":
            return None
        if "." in node[1]:
            return None
        return int(node[1])

    def _build_range_code(self, start_expr, stop_expr, step_value):
        if step_value == 1:
            return f"range({start_expr}, {stop_expr})"
        return f"range({start_expr}, {stop_expr}, {step_value})"

    def _indent(self, level):
        return "    " * level

    def get_ir(self):
        return self.ir
