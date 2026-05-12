import re


TOPICS = [
    {
        "name": "compiler phases",
        "keywords": {"phase", "phases", "compiler", "design", "process", "flow"},
        "phrases": ["phases of compiler", "compiler phases", "compiler design"],
        "answer": (
            "The main phases of a compiler are lexical analysis, syntax analysis, "
            "semantic analysis, intermediate code generation, optimization, and code generation. "
            "Symbol table management and error handling support these phases throughout the pipeline."
        ),
    },
    {
        "name": "lexer",
        "keywords": {"lexer", "lexical", "scanner", "token", "tokens"},
        "phrases": ["lexical analysis", "what is lexer", "what is token"],
        "answer": (
            "The lexer, or lexical analyzer, reads the source program character by character "
            "and groups it into tokens such as identifiers, keywords, numbers, and operators. "
            "It removes whitespace and helps the parser work with a cleaner token stream."
        ),
    },
    {
        "name": "parser",
        "keywords": {"parser", "parsing", "syntax", "grammar", "parse"},
        "phrases": ["syntax analysis", "what is parser", "parse tree"],
        "answer": (
            "The parser performs syntax analysis. It checks whether the token stream follows "
            "the grammar of the language and builds a parse tree or an abstract syntax tree."
        ),
    },
    {
        "name": "ast",
        "keywords": {"ast", "abstract", "syntax", "tree"},
        "phrases": ["abstract syntax tree", "what is ast"],
        "answer": (
            "An AST, or Abstract Syntax Tree, is a simplified tree representation of the program structure. "
            "It keeps the important syntactic meaning of statements and expressions while dropping unnecessary punctuation."
        ),
    },
    {
        "name": "semantic analysis",
        "keywords": {"semantic", "semantics", "type", "checking", "scope"},
        "phrases": ["semantic analysis", "type checking"],
        "answer": (
            "Semantic analysis checks the meaning of the program after parsing. "
            "It verifies rules such as type compatibility, declared-before-use variables, function arguments, and valid scopes."
        ),
    },
    {
        "name": "symbol table",
        "keywords": {"symbol", "table", "identifier", "scope", "entry"},
        "phrases": ["symbol table", "what is symbol table"],
        "answer": (
            "A symbol table stores information about identifiers such as variable names, data types, scopes, and memory details. "
            "The compiler uses it during semantic analysis, optimization, and code generation."
        ),
    },
    {
        "name": "intermediate code",
        "keywords": {"intermediate", "ir", "three", "address", "tac", "code"},
        "phrases": ["intermediate representation", "three address code", "three-address code"],
        "answer": (
            "Intermediate code is a machine-independent form generated between the source program and final target code. "
            "A common example is three-address code, where each instruction uses a small number of operands and is easy to optimize."
        ),
    },
    {
        "name": "optimization",
        "keywords": {"optimization", "optimize", "optimized", "speed", "improve"},
        "phrases": ["code optimization", "compiler optimization"],
        "answer": (
            "Code optimization improves the intermediate or target code so that it runs faster, uses less memory, or becomes smaller. "
            "Examples include constant folding, dead code elimination, common subexpression elimination, and loop optimization."
        ),
    },
    {
        "name": "code generation",
        "keywords": {"codegen", "generation", "target", "machine", "assembly"},
        "phrases": ["code generation", "target code"],
        "answer": (
            "Code generation is the final compiler phase that converts the optimized intermediate code into target code, "
            "such as assembly, machine code, or in your project, Python code."
        ),
    },
    {
        "name": "compiler vs interpreter",
        "keywords": {"compiler", "interpreter", "difference", "compare"},
        "phrases": ["compiler vs interpreter", "difference between compiler and interpreter"],
        "answer": (
            "A compiler translates the whole program before execution, while an interpreter executes the program statement by statement. "
            "Compiled programs usually run faster, while interpreted execution is often easier for quick testing and debugging."
        ),
    },
    {
        "name": "first and follow",
        "keywords": {"first", "follow", "ll1", "predictive", "parsing"},
        "phrases": ["first and follow", "first follow", "ll(1)"],
        "answer": (
            "FIRST and FOLLOW sets are used in predictive parsing. "
            "FIRST tells which terminals can appear at the start of a derivation, and FOLLOW tells which terminals can appear immediately after a non-terminal."
        ),
    },
    {
        "name": "left recursion",
        "keywords": {"left", "recursion", "factoring", "grammar"},
        "phrases": ["left recursion", "left factoring"],
        "answer": (
            "Left recursion happens when a grammar rule calls itself on the left side, such as A -> A alpha. "
            "It must be removed for predictive top-down parsers. Left factoring restructures grammar rules to defer decisions until enough input is seen."
        ),
    },
    {
        "name": "ll vs lr",
        "keywords": {"ll", "lr", "top", "down", "bottom", "up", "parser"},
        "phrases": ["ll parser", "lr parser", "top down", "bottom up"],
        "answer": (
            "LL parsers are top-down parsers that build the parse from the start symbol toward the input. "
            "LR parsers are bottom-up parsers that reduce input symbols back to the start symbol. "
            "LR parsing is more powerful but usually more complex to build."
        ),
    },
    {
        "name": "error handling",
        "keywords": {"error", "errors", "handling", "recover", "diagnostic"},
        "phrases": ["error handling", "error recovery"],
        "answer": (
            "Compiler error handling means detecting mistakes and reporting them clearly while trying to continue analysis when possible. "
            "Common recovery methods include panic mode recovery, phrase-level recovery, and inserting or deleting tokens."
        ),
    },
    {
        "name": "project explanation",
        "keywords": {"project", "transpiler", "python", "c", "working"},
        "phrases": ["what does this project do", "how does this project work"],
        "answer": (
            "Your project is a small C-to-Python transpiler. "
            "It tokenizes C-like code with a lexer, builds an AST with a parser, and generates runnable Python code with a code generator."
        ),
    },
]


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "can",
    "do",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "please",
    "tell",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
}


def normalize_words(text):
    words = re.findall(r"[a-zA-Z0-9+()_-]+", text.lower())
    return {word for word in words if word not in STOP_WORDS}


def answer_compiler_question(question):
    question_text = question.strip()
    if not question_text:
        return "Ask a compiler design question, and I will explain it in simple language."

    lowered = question_text.lower()
    words = normalize_words(question_text)

    best_topic = None
    best_score = 0

    for topic in TOPICS:
        score = len(words & topic["keywords"]) * 2
        for phrase in topic["phrases"]:
            if phrase in lowered:
                score += 5
        if topic["name"] in lowered:
            score += 3
        if score > best_score:
            best_score = score
            best_topic = topic

    if best_topic is not None and best_score > 0:
        return best_topic["answer"]

    return (
        "I can help with compiler design topics like compiler phases, lexer, parser, AST, "
        "semantic analysis, symbol table, intermediate code, optimization, code generation, "
        "LL vs LR, FIRST and FOLLOW, and compiler vs interpreter. Ask one of those topics in a short sentence."
    )
