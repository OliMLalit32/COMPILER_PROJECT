import os
import subprocess
from lexer import Lexer
from parser import Parser
from codegen import CodeGenerator
import pprint

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, 'sample_input.txt')
    with open(input_path) as f: 
        code = f.read()

    # Lexical analysis
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    print("\n--- TOKENS ---")
    for token in tokens:
        print(token)

    # Parsing
    parser = Parser(tokens)
    ast = parser.parse()
    print("\n--- ABSTRACT SYNTAX TREE (AST) ---")
    pprint.pprint(ast)

    # Code generation
    cg = CodeGenerator()
    pycode = cg.generate(ast)

    # Print IR
    print("\n--- INTERMEDIATE REPRESENTATION (IR) ---")
    for line in cg.get_ir():
        print(line)

    # Write Python output
    output_path = os.path.join(script_dir, 'output.py')
    with open(output_path, 'w') as f:
        f.write(pycode)

    print("\n--- GENERATED PYTHON CODE ---")
    print(pycode)

    print("\n--- EXECUTING output.py ---\n", flush=True)
    completed = subprocess.run(
        ['python', output_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="")

if __name__ == "__main__":
    main()
