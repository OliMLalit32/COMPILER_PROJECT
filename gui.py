from pathlib import Path
import contextlib
import html
import io
import pprint

import streamlit as st

from codegen import CodeGenerator
from compiler_chatbot import answer_compiler_question
from lexer import Lexer
from murf_falcon import MurfFalconError, generate_falcon_wav_bytes
from parser import Parser


MAX_SPOKEN_OUTPUT_CHARS = 220
MAX_CHAT_HISTORY = 12


def fragment_passthrough(func):
    return func


fragment = getattr(st, "fragment", fragment_passthrough)


def load_sample_code() -> str:
    sample_path = Path(__file__).with_name("sample_input.txt")
    if sample_path.exists():   
        return sample_path.read_text(encoding="utf-8")
    return ""


def compile_source(source_code: str) -> dict:
    lexer = Lexer(source_code)
    tokens = lexer.tokenize()

    parser = Parser(tokens)
    ast = parser.parse()

    codegen = CodeGenerator()
    pycode = codegen.generate(ast)
    ir = codegen.get_ir()

    output_buffer = io.StringIO()
    runtime_error = None
    namespace = {"__builtins__": __builtins__, "__name__": "__main__"}

    try:
        with contextlib.redirect_stdout(output_buffer):
            exec(pycode, namespace, namespace)
    except Exception as exc:
        runtime_error = {
            "type": type(exc).__name__,
            "message": str(exc),
        }

    execution_output = output_buffer.getvalue().strip()
    if not execution_output and runtime_error is None:
        execution_output = "Program executed successfully with no output."

    return {
        "tokens": tokens,
        "ast": ast,
        "ir": ir,
        "pycode": pycode,
        "execution_output": execution_output,
        "runtime_error": runtime_error,
    }


def build_voice_message(execution_output: str) -> str:
    cleaned_lines = [line.strip() for line in execution_output.splitlines() if line.strip()]
    if not cleaned_lines:
        return "Your program executed successfully with no output."
    spoken_output = " ".join(cleaned_lines)
    if len(spoken_output) > MAX_SPOKEN_OUTPUT_CHARS:
        truncated = spoken_output[:MAX_SPOKEN_OUTPUT_CHARS].rsplit(" ", 1)[0].strip()
        spoken_output = (truncated or spoken_output[:MAX_SPOKEN_OUTPUT_CHARS]).rstrip(".,;:") + " ..."
    return f"Your output is {spoken_output}."


@st.cache_data(show_spinner=False, ttl=3600, max_entries=32)
def get_cached_voice_audio(
    text: str,
    voice_id: str,
    locale: str,
    region: str,
    api_key: str,
) -> bytes:
    return generate_falcon_wav_bytes(
        text,
        voice_id=voice_id,
        locale=locale,
        region=region,
        api_key=api_key or None,
    )


def create_voice_output(result: dict, api_key: str, voice_id: str, locale: str, region: str) -> tuple[bytes | None, str | None]:
    if result["runtime_error"] is not None:
        return None, None

    spoken_text = build_voice_message(result["execution_output"])
    return create_voice_clip(spoken_text, api_key, voice_id, locale, region)


def create_voice_clip(text: str, api_key: str, voice_id: str, locale: str, region: str) -> tuple[bytes, str]:
    audio_bytes = get_cached_voice_audio(text, voice_id, locale, region, api_key)
    return audio_bytes, text


@st.cache_data(show_spinner=False, ttl=3600, max_entries=64)
def get_cached_chat_answer(question: str) -> str:
    return answer_compiler_question(question)


def clear_compile_voice_state() -> None:
    st.session_state.voice_audio = None
    st.session_state.voice_text = None
    st.session_state.voice_error = None


def clear_chat_voice_state() -> None:
    st.session_state.chat_voice_audio = None
    st.session_state.chat_voice_text = None
    st.session_state.chat_voice_error = None


def get_voice_settings() -> tuple[str, str, str, str]:
    return (
        st.session_state.murf_api_key.strip(),
        st.session_state.murf_voice_id.strip() or "Matthew",
        st.session_state.murf_locale.strip() or "en-US",
        st.session_state.murf_region,
    )


def render_voice_player(audio_bytes: bytes) -> None:
    st.audio(audio_bytes, format="audio/wav")


def generate_compile_voice() -> None:
    if not st.session_state.voice_text:
        return

    api_key, voice_id, locale, region = get_voice_settings()
    try:
        with st.spinner("Generating voice output..."):
            audio_bytes, spoken_text = create_voice_clip(
                st.session_state.voice_text,
                api_key,
                voice_id,
                locale,
                region,
            )
        st.session_state.voice_audio = audio_bytes
        st.session_state.voice_text = spoken_text
        st.session_state.voice_error = None
    except MurfFalconError as exc:
        st.session_state.voice_audio = None
        st.session_state.voice_error = str(exc)
    except Exception as exc:
        st.session_state.voice_audio = None
        st.session_state.voice_error = f"Voice generation failed: {exc}"


def generate_chat_voice() -> None:
    if not st.session_state.chat_voice_text:
        return

    api_key, voice_id, locale, region = get_voice_settings()
    try:
        with st.spinner("Generating chatbot voice..."):
            audio_bytes, spoken_text = create_voice_clip(
                st.session_state.chat_voice_text,
                api_key,
                voice_id,
                locale,
                region,
            )
        st.session_state.chat_voice_audio = audio_bytes
        st.session_state.chat_voice_text = spoken_text
        st.session_state.chat_voice_error = None
    except MurfFalconError as exc:
        st.session_state.chat_voice_audio = None
        st.session_state.chat_voice_error = str(exc)
    except Exception as exc:
        st.session_state.chat_voice_audio = None
        st.session_state.chat_voice_error = f"Chatbot voice failed: {exc}"


def token_html(tokens: list[tuple[str, str]]) -> str:
    return "".join(
        f'<div class="token-item">{html.escape(str(token))}</div>' for token in tokens
    )


@fragment
def render_chatbot_panel() -> None:
    with st.expander("Compiler Design Chatbot", expanded=True):
        st.caption("Ask theory questions about compiler design and get a simple explanation.")
        st.checkbox(
            "Enable chatbot voice output",
            key="enable_chat_voice_output",
            value=False,
        )

        with st.form("compiler_chat_form", clear_on_submit=True):
            st.caption("Press Enter to submit or click ASK CHATBOT.")
            chat_question = st.text_input(
                "Ask a compiler design question",
                placeholder="Type your question here and press Enter...",
            )
            ask_chatbot = st.form_submit_button("ASK CHATBOT", use_container_width=True)

        if ask_chatbot:
            cleaned_question = chat_question.strip()
            clear_chat_voice_state()

            if cleaned_question:
                answer = get_cached_chat_answer(cleaned_question)
                st.session_state.chat_history = (
                    st.session_state.chat_history
                    + [
                        {
                            "question": cleaned_question,
                            "answer": answer,
                        }
                    ]
                )[-MAX_CHAT_HISTORY:]
                if st.session_state.enable_chat_voice_output:
                    st.session_state.chat_voice_text = answer

        if st.session_state.chat_history:
            st.markdown("**Chat History**")
            for item in reversed(st.session_state.chat_history[-4:]):
                st.markdown(f"**You:** {item['question']}")
                st.markdown(f"**Assistant:** {item['answer']}")

            if (
                st.session_state.enable_chat_voice_output
                and st.session_state.chat_voice_text
                and not st.session_state.chat_voice_audio
            ):
                if st.button(
                    "GENERATE CHATBOT VOICE",
                    key="generate_chat_voice",
                    use_container_width=True,
                ):
                    generate_chat_voice()

            if st.session_state.chat_voice_audio:
                render_voice_player(st.session_state.chat_voice_audio)
            elif st.session_state.chat_voice_error:
                st.info(f"Chatbot Voice Unavailable: {st.session_state.chat_voice_error}")


def render_results(result: dict) -> None:
    st.success("Compilation completed successfully.")
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="panel-title">TOKENS</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="scroll-panel">{token_html(result["tokens"])}</div>',
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            '<div class="panel-title">ABSTRACT SYNTAX TREE</div>',
            unsafe_allow_html=True,
        )
        st.code(pprint.pformat(result["ast"]), language="python")

    st.markdown("<br>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown(
            '<div class="panel-title">INTERMEDIATE REPRESENTATION</div>',
            unsafe_allow_html=True,
        )
        st.code("\n".join(result["ir"]), language="python")

    with col4:
        st.markdown(
            '<div class="panel-title">FINAL PYTHON CODE</div>',
            unsafe_allow_html=True,
        )
        st.code(result["pycode"], language="python")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="panel-title">EXECUTION OUTPUT</div>', unsafe_allow_html=True)

    if result["runtime_error"] is None:
        safe_output = html.escape(result["execution_output"])
        st.markdown(
            f"""
            <div class="execution-output">
                <pre>{safe_output}</pre>
                <br>
                <strong>Execution Status:</strong> SUCCESS
                <br>
                <strong>Return Code:</strong> 0
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        safe_type = html.escape(result["runtime_error"]["type"])
        safe_message = html.escape(result["runtime_error"]["message"])
        st.markdown(
            f"""
            <div class="execution-output error-output">
                <pre>{safe_type}: {safe_message}</pre>
                <br>
                <strong>Execution Status:</strong> FAILED
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown('<div class="panel-title">COMPILATION STATISTICS</div>', unsafe_allow_html=True)

    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)

    with stats_col1:
        st.metric("Tokens Generated", len(result["tokens"]), delta="lexer")

    with stats_col2:
        st.metric("AST Nodes", len(str(result["ast"]).split()), delta="parser")

    with stats_col3:
        st.metric("IR Instructions", len(result["ir"]), delta="codegen")

    with stats_col4:
        st.metric("Python Lines", len(result["pycode"].splitlines()), delta="output")


def load_sample_into_editor() -> None:
    st.session_state.code_input = load_sample_code()
    st.session_state.compile_result = None
    st.session_state.compile_error = None
    clear_compile_voice_state()


st.set_page_config(
    page_title="Extraordinary C/C++ Transpiler",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "code_input" not in st.session_state:
    st.session_state.code_input = load_sample_code()

if "compile_result" not in st.session_state:
    st.session_state.compile_result = None

if "compile_error" not in st.session_state:
    st.session_state.compile_error = None

if "voice_audio" not in st.session_state:
    st.session_state.voice_audio = None

if "voice_text" not in st.session_state:
    st.session_state.voice_text = None

if "voice_error" not in st.session_state:
    st.session_state.voice_error = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "chat_voice_audio" not in st.session_state:
    st.session_state.chat_voice_audio = None

if "chat_voice_text" not in st.session_state:
    st.session_state.chat_voice_text = None

if "chat_voice_error" not in st.session_state:
    st.session_state.chat_voice_error = None

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

        .stApp {
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%);
            font-family: 'Inter', sans-serif;
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        .main-title {
            font-size: 3.5rem !important;
            font-weight: 800 !important;
            text-align: center !important;
            background: linear-gradient(135deg, #00d4ff, #ff6b6b, #ffe66d);
            background-size: 300% 300%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            animation: gradientShift 4s ease-in-out infinite;
            margin-bottom: 0.5rem !important;
        }

        @keyframes gradientShift {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
        }

        .subtitle {
            text-align: center;
            color: rgba(255, 255, 255, 0.75);
            font-size: 1.1rem;
            font-weight: 300;
            margin-bottom: 2rem;
        }

        .particles {
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: -1;
            opacity: 0.3;
        }

        .particle {
            position: absolute;
            background: rgba(0, 255, 255, 0.25);
            border-radius: 50%;
            animation: float 6s ease-in-out infinite;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0) rotate(0deg); opacity: 0.3; }
            50% { transform: translateY(-20px) rotate(180deg); opacity: 0.7; }
        }

        div[data-testid="stTextArea"] textarea {
            background: rgba(0, 0, 0, 0.60) !important;
            border: 2px solid rgba(0, 212, 255, 0.35) !important;
            border-radius: 16px !important;
            color: #ffffff !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 14px !important;
            line-height: 1.6 !important;
            backdrop-filter: blur(10px);
        }

        div[data-testid="stTextArea"] textarea:focus {
            border-color: #00d4ff !important;
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.28) !important;
        }

        .stButton > button {
            background: linear-gradient(135deg, #ff6b6b, #00d4ff) !important;
            border: none !important;
            border-radius: 999px !important;
            color: white !important;
            font-size: 1rem !important;
            font-weight: 700 !important;
            padding: 0.9rem 2.5rem !important;
            transition: all 0.25s ease !important;
            box-shadow: 0 14px 30px rgba(255, 107, 107, 0.20) !important;
        }

        .stButton > button:hover {
            transform: translateY(-2px) scale(1.02) !important;
            box-shadow: 0 18px 36px rgba(0, 212, 255, 0.24) !important;
        }

        .panel-title {
            color: #00d4ff !important;
            font-size: 1.15rem !important;
            font-weight: 700 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            margin-bottom: 0.9rem !important;
        }

        .metric-container {
            background: rgba(0, 0, 0, 0.35);
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 16px;
            padding: 1rem;
            text-align: center;
            backdrop-filter: blur(12px);
            min-height: 110px;
        }

        .metric-value {
            font-size: 1.9rem;
            font-weight: 800;
            color: #00d4ff;
            margin-bottom: 0.15rem;
        }

        .metric-label {
            color: rgba(255, 255, 255, 0.72);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .token-item {
            background: rgba(0, 212, 255, 0.10);
            border: 1px solid rgba(0, 212, 255, 0.26);
            border-radius: 8px;
            padding: 0.55rem 0.9rem;
            margin: 0.35rem 0;
            color: #ffffff;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
        }

        .scroll-panel {
            max-height: 420px;
            overflow-y: auto;
            padding-right: 0.2rem;
        }

        .execution-output {
            background: rgba(0, 0, 0, 0.78) !important;
            border: 2px solid rgba(0, 255, 0, 0.28) !important;
            border-radius: 14px !important;
            padding: 1.4rem !important;
            color: #00ff88 !important;
            font-family: 'JetBrains Mono', monospace !important;
            line-height: 1.6 !important;
        }

        .execution-output pre {
            margin: 0;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .error-output {
            border-color: rgba(255, 107, 107, 0.35) !important;
            color: #ff8a8a !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="particles">
        <div class="particle" style="width: 4px; height: 4px; left: 10%; top: 20%; animation-delay: 0s;"></div>
        <div class="particle" style="width: 3px; height: 3px; left: 20%; top: 80%; animation-delay: 1s;"></div>
        <div class="particle" style="width: 2px; height: 2px; left: 60%; top: 30%; animation-delay: 2s;"></div>
        <div class="particle" style="width: 5px; height: 5px; left: 80%; top: 70%; animation-delay: 0.5s;"></div>
        <div class="particle" style="width: 3px; height: 3px; left: 30%; top: 10%; animation-delay: 1.5s;"></div>
        <div class="particle" style="width: 4px; height: 4px; left: 70%; top: 90%; animation-delay: 2.5s;"></div>
        <div class="particle" style="width: 2px; height: 2px; left: 90%; top: 40%; animation-delay: 3s;"></div>
        <div class="particle" style="width: 6px; height: 6px; left: 15%; top: 60%; animation-delay: 0.8s;"></div>
        <div class="particle" style="width: 3px; height: 3px; left: 45%; top: 85%; animation-delay: 1.8s;"></div>
        <div class="particle" style="width: 4px; height: 4px; left: 75%; top: 15%; animation-delay: 2.2s;"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<h1 class="main-title">C/C++ Transpiler</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Transform your code through lexer, parser, IR, and final Python output.</p>',
    unsafe_allow_html=True,
)

metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

with metric_col1:
    st.markdown(
        """
        <div class="metric-container">
            <div class="metric-value">LEX</div>
            <div class="metric-label">Token Stream</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with metric_col2:
    st.markdown(
        """
        <div class="metric-container">
            <div class="metric-value">AST</div>
            <div class="metric-label">Parse Tree</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with metric_col3:
    st.markdown(
        """
        <div class="metric-container">
            <div class="metric-value">IR</div>
            <div class="metric-label">Intermediate Code</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with metric_col4:
    st.markdown(
        """
        <div class="metric-container">
            <div class="metric-value">PY</div>
            <div class="metric-label">Final Output</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="panel-title">SOURCE CODE INPUT</div>', unsafe_allow_html=True)

st.text_area(
    "Source code",
    key="code_input",
    height=350,
    label_visibility="collapsed",
    help="Use the sample code or paste a small C program here.",
    placeholder="Enter your C code here...",
)

with st.expander("Voice Output (Murf Falcon)", expanded=True):
    st.caption("Voice is generated on demand so compile results appear immediately and audio can be retried safely.")
    st.checkbox(
        "Enable execution voice output",
        key="enable_voice_output",
        value=True,
    )
    st.text_input(
        "Murf API Key",
        key="murf_api_key",
        type="password",
        help="Optional here if you already set MURF_API_KEY in PowerShell.",
    )
    voice_col1, voice_col2, voice_col3 = st.columns(3)
    with voice_col1:
        st.text_input("Voice ID", key="murf_voice_id", value="Matthew")
    with voice_col2:
        st.text_input("Locale", key="murf_locale", value="en-US")
    with voice_col3:
        st.selectbox("Region", key="murf_region", options=["in", "global"], index=0)

generate_execution_voice_clicked = False

render_chatbot_panel()

button_col1, button_col2, button_col3 = st.columns([1, 1, 1])

with button_col2:
    compile_button = st.button("COMPILE AND EXECUTE", type="primary", use_container_width=True)

with button_col3:
    st.button(
        "LOAD SAMPLE",
        use_container_width=True,
        on_click=load_sample_into_editor,
    )

if compile_button:
    source = st.session_state.code_input.strip()
    if not source:
        st.session_state.compile_result = None
        st.session_state.compile_error = "Please enter some code to compile."
        clear_compile_voice_state()
    else:
        with st.spinner("Compiling your code..."):
            try:
                st.session_state.compile_result = compile_source(source)
                st.session_state.compile_error = None
                clear_compile_voice_state()
                if st.session_state.enable_voice_output and st.session_state.compile_result["runtime_error"] is None:
                    st.session_state.voice_text = build_voice_message(
                        st.session_state.compile_result["execution_output"]
                    )
            except Exception as exc:
                st.session_state.compile_result = None
                st.session_state.compile_error = str(exc)
                clear_compile_voice_state()

st.markdown("<br>", unsafe_allow_html=True)

if st.session_state.compile_error:
    st.error(f"Compilation Error: {st.session_state.compile_error}")
elif st.session_state.compile_result is not None:
    render_results(st.session_state.compile_result)
    if (
        st.session_state.enable_voice_output
        and st.session_state.compile_result["runtime_error"] is None
        and st.session_state.voice_text
        and not st.session_state.voice_audio
    ):
        st.markdown("<br>", unsafe_allow_html=True)
        generate_execution_voice_clicked = st.button(
            "GENERATE EXECUTION VOICE",
            key="generate_execution_voice",
            type="secondary",
            use_container_width=True,
        )
        if generate_execution_voice_clicked:
            generate_compile_voice()
    if st.session_state.voice_audio:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="panel-title">VOICE OUTPUT</div>', unsafe_allow_html=True)
        if st.session_state.voice_text:
            st.caption(st.session_state.voice_text)
        render_voice_player(st.session_state.voice_audio)
    elif st.session_state.voice_error:
        st.info(f"Voice Output Unavailable: {st.session_state.voice_error}")

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("---")

footer_col1, footer_col2, footer_col3 = st.columns(3)

with footer_col1:
    st.markdown("**Features**")
    st.markdown("- Lexical analysis")
    st.markdown("- Syntax tree generation")
    st.markdown("- Intermediate code generation")
    st.markdown("- C arrays and printf translation")
    st.markdown("- Compiler design chatbot")

with footer_col2:
    st.markdown("**Input Rules**")
    st.markdown("- Supports `printf(...)`")
    st.markdown("- Supports arrays, indexing, `if`, `else`, `for`, and `while`")
    st.markdown("- Supports `+ - * / % < > <= >= == != && ||`")

with footer_col3:
    st.markdown("**Status**")
    st.markdown("- Lexer ready")
    st.markdown("- Parser active")
    st.markdown("- Python output enabled")
    st.markdown("- C-style sample included")
    st.markdown("- Chat assistant enabled")
