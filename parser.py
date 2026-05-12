import ast


class Parser:
    TYPE_KEYWORDS = {
        "char",
        "double",
        "float",
        "int",
        "long",
        "short",
        "signed",
        "unsigned",
        "void",
    }
    ASSIGNMENT_OPERATORS = {"=", "+=", "-=", "*=", "/=", "%="}

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current(self, offset=0):
        index = self.pos + offset
        if index < len(self.tokens):
            return self.tokens[index]
        return ("EOF", "")

    def eat(self, expected_type=None, expected_value=None):
        token = self.current()
        if expected_type and token[0] != expected_type:
            raise SyntaxError(f"Expected {expected_type}, got {token}")
        if expected_value and token[1] != expected_value:
            raise SyntaxError(f"Expected {expected_value}, got {token}")
        self.pos += 1
        return token

    def match(self, expected_type=None, expected_value=None):
        token = self.current()
        if expected_type and token[0] != expected_type:
            return False
        if expected_value and token[1] != expected_value:
            return False
        return True

    def parse(self):
        items = []
        while not self.match("EOF"):
            if self.is_function_definition():
                items.append(self.function_definition())
            else:
                items.append(self.statement())
        return ("program", items)

    def is_type_start(self, offset=0):
        token = self.current(offset)
        return token[0] == "ID" and token[1] in self.TYPE_KEYWORDS

    def is_function_definition(self):
        if not self.is_type_start():
            return False

        index = self.pos
        while index < len(self.tokens) and self.tokens[index][0] == "ID" and self.tokens[index][1] in self.TYPE_KEYWORDS:
            index += 1
        while index < len(self.tokens) and self.tokens[index] == ("OP", "*"):
            index += 1

        if index >= len(self.tokens) or self.tokens[index][0] != "ID":
            return False
        index += 1
        return index < len(self.tokens) and self.tokens[index] == ("PUNC", "(")

    def statement(self):
        token = self.current()
        if token == ("PUNC", "{"):
            return self.block()
        if token == ("PUNC", ";"):
            self.eat("PUNC", ";")
            return ("empty",)
        if self.is_type_start():
            return self.declaration()
        if token == ("ID", "if"):
            return self.if_stmt()
        if token == ("ID", "for"):
            return self.for_stmt()
        if token == ("ID", "while"):
            return self.while_stmt()
        if token == ("ID", "return"):
            return self.return_stmt()

        expr = self.expression()
        self.eat("PUNC", ";")
        return ("expr_stmt", expr)

    def block(self):
        self.eat("PUNC", "{")
        statements = []
        while not self.match("PUNC", "}"):
            statements.append(self.statement())
        self.eat("PUNC", "}")
        return ("block", statements)

    def block_or_statement(self):
        if self.match("PUNC", "{"):
            return self.block()
        return ("block", [self.statement()])

    def parse_type(self):
        if not self.is_type_start():
            raise SyntaxError(f"Expected a type, got {self.current()}")

        parts = []
        while self.is_type_start():
            parts.append(self.eat("ID")[1])
        return " ".join(parts)

    def declaration(self, require_semicolon=True):
        base_type = self.parse_type()
        declarations = [self.declarator(base_type)]

        while self.match("PUNC", ","):
            self.eat("PUNC", ",")
            declarations.append(self.declarator(base_type))

        if require_semicolon:
            self.eat("PUNC", ";")

        if len(declarations) == 1:
            return declarations[0]
        return ("block", declarations)

    def declarator(self, base_type):
        pointer_depth = 0
        while self.match("OP", "*"):
            self.eat("OP", "*")
            pointer_depth += 1

        name = self.eat("ID")[1]
        dimensions = []
        while self.match("PUNC", "["):
            self.eat("PUNC", "[")
            size = None
            if not self.match("PUNC", "]"):
                size = self.expression()
            self.eat("PUNC", "]")
            dimensions.append(size)

        initializer = None
        if self.match("OP", "="):
            self.eat("OP", "=")
            if self.match("PUNC", "{"):
                initializer = self.initializer_list()
            else:
                initializer = self.expression()

        return ("decl", base_type, name, dimensions, initializer, pointer_depth)

    def initializer_list(self):
        self.eat("PUNC", "{")
        items = []

        while not self.match("PUNC", "}"):
            if self.match("PUNC", "{"):
                items.append(self.initializer_list())
            else:
                items.append(self.expression())

            if self.match("PUNC", ","):
                self.eat("PUNC", ",")
                if self.match("PUNC", "}"):
                    break
            else:
                break

        self.eat("PUNC", "}")
        return ("array_init", items)

    def if_stmt(self):
        self.eat("ID", "if")
        self.eat("PUNC", "(")
        condition = self.expression()
        self.eat("PUNC", ")")
        then_block = self.block_or_statement()

        else_block = None
        if self.match("ID", "else"):
            self.eat("ID", "else")
            else_block = self.block_or_statement()

        return ("if", condition, then_block, else_block)

    def for_stmt(self):
        self.eat("ID", "for")
        self.eat("PUNC", "(")

        init = None
        if not self.match("PUNC", ";"):
            if self.is_type_start():
                init = self.declaration(require_semicolon=False)
            else:
                init = ("expr_stmt", self.expression())
        self.eat("PUNC", ";")

        condition = None
        if not self.match("PUNC", ";"):
            condition = self.expression()
        self.eat("PUNC", ";")

        update = None
        if not self.match("PUNC", ")"):
            update = ("expr_stmt", self.expression())
        self.eat("PUNC", ")")

        body = self.block_or_statement()
        return ("for", init, condition, update, body)

    def while_stmt(self):
        self.eat("ID", "while")
        self.eat("PUNC", "(")
        condition = self.expression()
        self.eat("PUNC", ")")
        body = self.block_or_statement()
        return ("while", condition, body)

    def return_stmt(self):
        self.eat("ID", "return")
        expr = None
        if not self.match("PUNC", ";"):
            expr = self.expression()
        self.eat("PUNC", ";")
        return ("return", expr)

    def function_definition(self):
        return_type = self.parse_type()
        pointer_depth = 0
        while self.match("OP", "*"):
            self.eat("OP", "*")
            pointer_depth += 1

        name = self.eat("ID")[1]
        self.eat("PUNC", "(")
        params = []

        if not self.match("PUNC", ")"):
            if self.match("ID", "void") and self.current(1) == ("PUNC", ")"):
                self.eat("ID", "void")
            else:
                while True:
                    param_type = self.parse_type()
                    param_pointer = 0
                    while self.match("OP", "*"):
                        self.eat("OP", "*")
                        param_pointer += 1

                    param_name = self.eat("ID")[1]
                    param_dimensions = []
                    while self.match("PUNC", "["):
                        self.eat("PUNC", "[")
                        if not self.match("PUNC", "]"):
                            param_dimensions.append(self.expression())
                        else:
                            param_dimensions.append(None)
                        self.eat("PUNC", "]")

                    params.append((param_type, param_name, param_dimensions, param_pointer))
                    if not self.match("PUNC", ","):
                        break
                    self.eat("PUNC", ",")

        self.eat("PUNC", ")")
        body = self.block()
        return ("func", return_type, name, params, body, pointer_depth)

    def expression(self):
        return self.assignment()

    def assignment(self):
        left = self.logical_or()
        if self.match("OP") and self.current()[1] in self.ASSIGNMENT_OPERATORS:
            op = self.eat("OP")[1]
            right = self.assignment()
            return ("assign_expr", op, left, right)
        return left

    def logical_or(self):
        left = self.logical_and()
        while self.match("OP", "||"):
            op = self.eat("OP")[1]
            right = self.logical_and()
            left = ("binop", op, left, right)
        return left

    def logical_and(self):
        left = self.equality()
        while self.match("OP", "&&"):
            op = self.eat("OP")[1]
            right = self.equality()
            left = ("binop", op, left, right)
        return left

    def equality(self):
        left = self.relational()
        while self.match("OP") and self.current()[1] in {"==", "!="}:
            op = self.eat("OP")[1]
            right = self.relational()
            left = ("binop", op, left, right)
        return left

    def relational(self):
        left = self.additive()
        while self.match("OP") and self.current()[1] in {"<", ">", "<=", ">="}:
            op = self.eat("OP")[1]
            right = self.additive()
            left = ("binop", op, left, right)
        return left

    def additive(self):
        left = self.term()
        while self.match("OP") and self.current()[1] in {"+", "-"}:
            op = self.eat("OP")[1]
            right = self.term()
            left = ("binop", op, left, right)
        return left

    def term(self):
        left = self.unary()
        while self.match("OP") and self.current()[1] in {"*", "/", "%"}:
            op = self.eat("OP")[1]
            right = self.unary()
            left = ("binop", op, left, right)
        return left

    def unary(self):
        if self.match("OP") and self.current()[1] in {"+", "-", "!"}:
            op = self.eat("OP")[1]
            return ("unary", op, self.unary())
        if self.match("OP") and self.current()[1] in {"++", "--"}:
            op = self.eat("OP")[1]
            return ("update_expr", "prefix", op, self.unary())
        return self.postfix()

    def postfix(self):
        node = self.primary()

        while True:
            if self.match("PUNC", "["):
                self.eat("PUNC", "[")
                index = self.expression()
                self.eat("PUNC", "]")
                node = ("index", node, index)
                continue

            if self.match("PUNC", "("):
                self.eat("PUNC", "(")
                args = []
                if not self.match("PUNC", ")"):
                    while True:
                        args.append(self.expression())
                        if not self.match("PUNC", ","):
                            break
                        self.eat("PUNC", ",")
                self.eat("PUNC", ")")
                node = ("call", node, args)
                continue

            if self.match("OP") and self.current()[1] in {"++", "--"}:
                op = self.eat("OP")[1]
                node = ("update_expr", "postfix", op, node)
                continue

            break

        return node

    def primary(self):
        token = self.current()

        if token[0] == "NUMBER":
            self.eat("NUMBER")
            return ("num", token[1])
        if token[0] == "STRING":
            self.eat("STRING")
            return ("str", ast.literal_eval(token[1]))
        if token[0] == "CHAR":
            self.eat("CHAR")
            return ("char", ast.literal_eval(token[1]))
        if token[0] == "ID":
            self.eat("ID")
            return ("var", token[1])
        if token == ("PUNC", "("):
            self.eat("PUNC", "(")
            expr = self.expression()
            self.eat("PUNC", ")")
            return expr

        raise SyntaxError(f"Unexpected token {token}")
