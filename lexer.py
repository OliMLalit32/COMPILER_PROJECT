import re


class Lexer:
    def __init__(self, code):
        self.code = code

    def tokenize(self):
        token_specification = [
            ("COMMENT", r"//[^\n]*|/\*.*?\*/"),
            ("PREPROCESSOR", r"#[^\n]*"),
            ("STRING", r'"(?:\\.|[^"\\])*"'),
            ("CHAR", r"'(?:\\.|[^'\\])'"),
            ("NUMBER", r"\d+\.\d+|\d+"),
            ("ID", r"[A-Za-z_]\w*"),
            ("OP", r"\+\+|--|\+=|-=|\*=|/=|%=|==|!=|<=|>=|&&|\|\||[+\-*/%=&|!<>]"),
            ("PUNC", r"[{}\[\]();,]"),
            ("SKIP", r"[ \t\r\n]+"),
            ("MISMATCH", r"."),
        ]
        tok_regex = "|".join("(?P<%s>%s)" % pair for pair in token_specification)
        tokens = []

        for match in re.finditer(tok_regex, self.code, flags=re.DOTALL):
            kind = match.lastgroup
            value = match.group()

            if kind in {"COMMENT", "PREPROCESSOR", "SKIP"}:
                continue
            if kind in {"NUMBER", "STRING", "CHAR", "ID", "OP", "PUNC"}:
                tokens.append((kind, value))
                continue
            raise SyntaxError(f"Unexpected character {value}")

        return tokens
