import asyncio
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ============================================================
# CONFIGURATION
# ============================================================

APP_NAME = "DevResearcher Backend"
APP_VERSION = "2.0.0"

AGENT_ID = "devresearcher"

HOST = "127.0.0.1"
PORT = 8000

DEFAULT_MODEL = "openai/gpt-5.6-luna"

DEFAULT_FALLBACKS = [
    "ollama/qwen3:1.7b",
]

# Models available to the DevResearcher frontend.
#
# These are model IDs known from your current OpenClaw setup.
# OpenClaw remains responsible for authentication and actual
# provider communication.
AVAILABLE_MODELS = [
    {
        "id": "openai/gpt-5.6-luna",
        "name": "GPT-5.6 Luna",
        "provider": "OpenAI",
        "type": "cloud",
    },
    {
        "id": "ollama/qwen3:1.7b",
        "name": "Qwen3 1.7B",
        "provider": "Ollama",
        "type": "local",
    },
    {
        "id": "google/gemini-3.1-pro-preview",
        "name": "Gemini 3.1 Pro",
        "provider": "Google",
        "type": "cloud",
    },
    {
        "id": "anthropic/claude-sonnet-4-6",
        "name": "Claude Sonnet 4.6",
        "provider": "Anthropic",
        "type": "cloud",
    },
    {
        "id": "zai/glm-5",
        "name": "GLM-5",
        "provider": "Z.ai",
        "type": "cloud",
    },
    {
        "id": "zai/glm-5v-turbo",
        "name": "GLM-5V Turbo",
        "provider": "Z.ai",
        "type": "cloud",
    },
    {
        "id": "zai/glm-4.7",
        "name": "GLM-4.7",
        "provider": "Z.ai",
        "type": "cloud",
    },
    {
        "id": "xai/grok-4.3",
        "name": "Grok 4.3",
        "provider": "xAI",
        "type": "cloud",
    },
    {
        "id": "anthropic/claude-sonnet-5",
        "name": "Claude Sonnet 5",
        "provider": "Anthropic",
        "type": "cloud",
    },
]


# ============================================================
# OPENCLAW INSTALLATION
# ============================================================

KNOWN_OPENCLAW_PATHS = [
    r"C:\Users\Pcw\AppData\Roaming\npm\openclaw.cmd",
    r"C:\Users\Pcw\AppData\Roaming\npm\openclaw",
]


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "Backend API for DevResearcher — "
        "multi-model AI research and software engineering agent."
    ),
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class AgentRequest(BaseModel):
    message: str
    project_path: Optional[str] = ""

    # Explicit model.
    #
    # Example:
    # "openai/gpt-5.6-luna"
    # "ollama/qwen3:1.7b"
    model: Optional[str] = None

    # Optional ordered fallback models.
    #
    # Example:
    # [
    #     "ollama/qwen3:1.7b",
    #     "google/gemini-3.1-pro-preview"
    # ]
    fallbacks: Optional[List[str]] = None

    # Optional OpenClaw thinking mode.
    #
    # Depending on your OpenClaw version this can be:
    # low / medium / high
    thinking: Optional[str] = None


class FileRequest(BaseModel):
    path: str


class FolderRequest(BaseModel):
    path: str


# ============================================================
# GLOBAL STATE
# ============================================================

active_processes = set()


# ============================================================
# OPENCLAW DETECTION
# ============================================================

def find_openclaw() -> str:
    """
    Find the OpenClaw executable on Windows.
    """

    # First check PATH.
    for command in [
        "openclaw.cmd",
        "openclaw",
    ]:
        found = shutil.which(command)

        if found:
            return found

    # Then check known installation paths.
    for path in KNOWN_OPENCLAW_PATHS:
        if os.path.isfile(path):
            return path

    raise RuntimeError(
        "OpenClaw was not found.\n\n"
        "Expected something like:\n"
        r"C:\Users\Pcw\AppData\Roaming\npm\openclaw.cmd"
    )


# ============================================================
# OLLAMA DETECTION
# ============================================================

def find_ollama() -> Optional[str]:
    """
    Find Ollama executable if installed.
    """

    for command in [
        "ollama.exe",
        "ollama",
    ]:
        found = shutil.which(command)

        if found:
            return found

    common_paths = [
        r"C:\Users\Pcw\AppData\Local\Programs\Ollama\ollama.exe",
        r"C:\Program Files\Ollama\ollama.exe",
    ]

    for path in common_paths:
        if os.path.isfile(path):
            return path

    return None


# ============================================================
# PROJECT VALIDATION
# ============================================================

def validate_project_path(project_path: str) -> Path:
    """
    Validate and normalize a Windows project directory.
    """

    if not project_path:
        raise ValueError(
            "No project directory was provided."
        )

    path = Path(project_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"Project directory does not exist:\n{path}"
        )

    if not path.is_dir():
        raise NotADirectoryError(
            f"Project path is not a directory:\n{path}"
        )

    return path


# ============================================================
# MODEL VALIDATION
# ============================================================

def normalize_model(model: Optional[str]) -> str:
    """
    Return a valid model ID.

    If no model is provided, use the DevResearcher primary model.
    """

    if not model:
        return DEFAULT_MODEL

    model = str(model).strip()

    if not model:
        return DEFAULT_MODEL

    return model


def normalize_fallbacks(
    fallbacks: Optional[List[str]],
    primary_model: str,
) -> List[str]:
    """
    Normalize fallback list.

    Removes:
    - empty values
    - duplicate models
    - primary model from fallback list
    """

    if not fallbacks:
        return []

    result = []

    for model in fallbacks:

        if not model:
            continue

        model = str(model).strip()

        if not model:
            continue

        if model == primary_model:
            continue

        if model not in result:
            result.append(model)

    return result


# ============================================================
# PROJECT TREE
# ============================================================

IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def build_tree(
    directory: Path,
    root: Optional[Path] = None,
    max_depth: int = 8,
    current_depth: int = 0,
) -> Dict[str, Any]:

    if root is None:
        root = directory

    try:
        entries = list(directory.iterdir())

    except PermissionError:

        return {
            "name": directory.name,
            "path": str(directory),
            "type": "directory",
            "children": [],
            "error": "Permission denied",
        }

    except OSError as exc:

        return {
            "name": directory.name,
            "path": str(directory),
            "type": "directory",
            "children": [],
            "error": str(exc),
        }

    entries.sort(
        key=lambda item: (
            not item.is_dir(),
            item.name.lower(),
        )
    )

    children = []

    for entry in entries:

        # Ignore heavy/system folders.
        if (
            entry.is_dir()
            and entry.name in IGNORED_DIRECTORIES
        ):
            continue

        try:
            relative_path = str(
                entry.relative_to(root)
            )

        except ValueError:
            relative_path = entry.name

        # --------------------------------------------------------
        # DIRECTORY
        # --------------------------------------------------------

        if entry.is_dir():

            if current_depth >= max_depth:

                children.append(
                    {
                        "name": entry.name,
                        "path": str(entry),
                        "relative_path": relative_path,
                        "type": "directory",
                        "children": [],
                        "truncated": True,
                    }
                )

                continue

            children.append(
                build_tree(
                    entry,
                    root=root,
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                )
            )

        # --------------------------------------------------------
        # FILE
        # --------------------------------------------------------

        else:

            try:
                size = entry.stat().st_size

            except OSError:
                size = 0

            children.append(
                {
                    "name": entry.name,
                    "path": str(entry),
                    "relative_path": relative_path,
                    "type": "file",
                    "size": size,
                }
            )

    return {
        "name": directory.name,
        "path": str(directory),
        "relative_path": ".",
        "type": "directory",
        "children": children,
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
async def root():

    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "status": "running",
        "agent": AGENT_ID,
        "primary_model": DEFAULT_MODEL,
        "fallback_models": DEFAULT_FALLBACKS,
    }


@app.get("/api/health")
async def health():

    openclaw_path = None
    openclaw_error = None

    try:
        openclaw_path = find_openclaw()

    except Exception as exc:
        openclaw_error = str(exc)

    ollama_path = find_ollama()

    return {
        "status": "ok",
        "backend": "connected",
        "agent": AGENT_ID,
        "openclaw": openclaw_path,
        "openclaw_error": openclaw_error,
        "ollama": ollama_path,
        "multi_model": True,
        "primary_model": DEFAULT_MODEL,
        "fallback_models": DEFAULT_FALLBACKS,
    }


# ============================================================
# MODELS API
# ============================================================

@app.get("/api/models")
async def get_models():

    return {
        "agent": AGENT_ID,
        "primary": DEFAULT_MODEL,
        "fallbacks": DEFAULT_FALLBACKS,
        "models": AVAILABLE_MODELS,
    }


# ============================================================
# MODEL STATUS
# ============================================================

@app.get("/api/models/status")
async def model_status():

    models = []

    openclaw_available = False
    ollama_available = False

    try:
        find_openclaw()
        openclaw_available = True
    except Exception:
        pass

    if find_ollama():
        ollama_available = True

    for model in AVAILABLE_MODELS:

        provider = model["provider"]

        status = "available"

        if provider == "Ollama" and not ollama_available:
            status = "unavailable"

        if provider != "Ollama" and not openclaw_available:
            status = "unavailable"

        models.append(
            {
                **model,
                "status": status,
                "primary": model["id"] == DEFAULT_MODEL,
                "fallback": model["id"] in DEFAULT_FALLBACKS,
            }
        )

    return {
        "agent": AGENT_ID,
        "primary": DEFAULT_MODEL,
        "fallbacks": DEFAULT_FALLBACKS,
        "models": models,
    }


# ============================================================
# PROJECT TREE ENDPOINT
# ============================================================

@app.get("/api/project/tree")
async def project_tree(path: str):

    try:

        project = validate_project_path(path)

        tree = build_tree(project)

        return tree

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except NotADirectoryError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not load project tree: {exc}",
        )


# ============================================================
# READ FILE ENDPOINT
# ============================================================

@app.get("/api/project/file")
async def read_project_file(path: str):

    try:

        file_path = (
            Path(path)
            .expanduser()
            .resolve()
        )

        if not file_path.exists():

            raise HTTPException(
                status_code=404,
                detail=f"File not found: {file_path}",
            )

        if not file_path.is_file():

            raise HTTPException(
                status_code=400,
                detail=f"Not a file: {file_path}",
            )

        # Prevent accidentally loading enormous files.
        max_size = 5 * 1024 * 1024

        if file_path.stat().st_size > max_size:

            raise HTTPException(
                status_code=413,
                detail="File is larger than 5 MB.",
            )

        try:

            content = file_path.read_text(
                encoding="utf-8"
            )

        except UnicodeDecodeError:

            content = file_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

        return {
            "name": file_path.name,
            "path": str(file_path),
            "content": content,
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not read file: {exc}",
        )


# ============================================================
# WINDOWS FOLDER PICKER
# ============================================================

def choose_folder_windows() -> Optional[str]:
    """
    Open the native Windows folder picker.

    This runs on the backend machine, so the backend must be
    running locally on the same Windows computer as the browser.
    """

    if os.name != "nt":
        raise RuntimeError(
            "Windows folder picker is only available on Windows."
        )

    try:

        import tkinter as tk
        from tkinter import filedialog

    except ImportError as exc:

        raise RuntimeError(
            "Tkinter is not available in this Python installation."
        ) from exc

    root = tk.Tk()

    try:

        root.withdraw()
        root.attributes("-topmost", True)

        folder = filedialog.askdirectory(
            title="Select DevResearcher Project Folder"
        )

        return folder or None

    finally:

        root.destroy()


@app.api_route("/api/project/pick-folder", methods=["GET", "POST"])
async def pick_project_folder():

    try:

        folder = await asyncio.to_thread(
            choose_folder_windows
        )

        if not folder:

            return {
                "selected": False,
                "path": None,
            }

        project = validate_project_path(folder)

        return {
            "selected": True,
            "path": str(project),
            "name": project.name,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not select folder: {exc}",
        )


# ============================================================
# BUILD DEVRESEARCHER PROMPT
# ============================================================

def build_agent_prompt(
    message: str,
    project_path: Path,
    model: str,
    fallbacks: List[str],
) -> str:

    fallback_text = (
        "\n".join(
            f"- {item}"
            for item in fallbacks
        )
        if fallbacks
        else "- None specified for this request."
    )

    return f"""
You are DevResearcher, a professional AI engineering,
software development, debugging, code analysis,
research, architecture, and technical-writing agent.

============================================================
CURRENT PROJECT
============================================================

Project directory:

{project_path}

You MUST treat this directory as the current project.

============================================================
MODEL INFORMATION
============================================================

Primary model requested:

{model}

Fallback models requested:

{fallback_text}

The model routing is handled by OpenClaw.

Do not claim to have used a different model than the one
actually executing the request.

============================================================
USER REQUEST
============================================================

{message}

============================================================
PROJECT RULES
============================================================

1. Inspect the actual files in the current project before
   answering questions about the project.

2. Do NOT guess what the project contains.

3. Use the actual files as the source of truth.

4. If the user asks what the project does, inspect the
   project first.

5. If the user asks you to explain code, inspect the
   relevant source files before explaining it.

6. If the user asks you to find a problem, inspect the
   actual implementation and diagnose the real cause.

7. If the user asks you to modify code, inspect the
   existing implementation before changing anything.

8. Do not modify unrelated projects.

9. Preserve the existing project architecture unless
   there is a strong technical reason to change it.

10. Clearly distinguish:

    - what already exists
    - what is broken
    - what is missing
    - what you recommend

11. When possible, verify conclusions using actual
    project files.

12. Do not simply ask the user to repeat a request that
    is already provided above.

13. Give a complete useful answer.

14. For research projects, distinguish existing
    implementation from proposed methodology and
    improvements.

15. When describing files, use their actual names
    and paths.

16. Never fabricate research papers, citations,
    benchmarks, test results, or implementation details.

17. When uncertain, explicitly state what is known,
    what is inferred, and what still needs verification.

18. For coding changes, prefer the smallest safe
    change that solves the actual problem.

19. After modifying code, verify the result whenever
    possible.

20. Protect secrets, credentials, API keys, and
    authentication information.

============================================================
RESEARCH WORKFLOW
============================================================

For research tasks:

1. Understand the research question.
2. Inspect the existing project.
3. Identify the relevant methodology.
4. Use authoritative sources when external research
   is required.
5. Separate facts from assumptions.
6. Avoid fabricated citations.
7. Explain limitations.
8. Provide reproducible recommendations.

============================================================
CODING WORKFLOW
============================================================

Use:

UNDERSTAND
    ↓
INSPECT
    ↓
PLAN
    ↓
MODIFY
    ↓
TEST
    ↓
VERIFY
    ↓
REPORT

For debugging:

ERROR
    ↓
CAUSE
    ↓
FIX
    ↓
TEST
    ↓
RESULT

============================================================
IMPORTANT
============================================================

The user's project is available locally at:

{project_path}

Inspect the actual project before responding.

Now perform the user's request.
""".strip()


# ============================================================
# OPENCLAW OUTPUT CLASSIFICATION
#
# OpenClaw is run WITHOUT --json below (see run_openclaw): the
# --json envelope only returns one summary object after the
# WHOLE turn finishes (see docs.openclaw.ai/cli/agent), not a
# live stream -- and a live, line-by-line feed is the entire
# point of the agent activity panel. So instead this reads
# OpenClaw's normal human-readable stdout and classifies each
# line into the richer event vocabulary the frontend AgentView
# already understands (thinking / plan / tool / file_read /
# file_write / command / diff / success / warning / error),
# instead of dumping every line as flat "output" text.
#
# This is pattern matching on human-readable text, not a
# documented machine protocol, so it is a best-effort heuristic
# -- not a guaranteed parse of whatever your specific OpenClaw
# version/agent prints. Anything that doesn't clearly match a
# pattern below still comes through as a plain "output" event,
# exactly as before, so nothing is ever hidden: the OUTPUT tab
# in the UI always shows the raw, unclassified stream alongside
# the classified DEVRESEARCHER panel. If your setup formats
# lines differently, this is the one place to retune it.
# ============================================================

_RE_FILE_READ = re.compile(
    r"^\s*(?:reading|read|opening|inspecting|viewing)\s+"
    r"(?:file\s+)?[`\"']?([^\s`\"']+\.[A-Za-z0-9]+)[`\"']?",
    re.IGNORECASE,
)

_RE_FILE_WRITE = re.compile(
    r"^\s*(?:writing|wrote|modifying|modified|updating|updated|"
    r"creating|created|editing|edited|saved?)\s+"
    r"(?:file\s+)?[`\"']?([^\s`\"']+\.[A-Za-z0-9]+)[`\"']?",
    re.IGNORECASE,
)

_RE_COMMAND = re.compile(
    r"^\s*(?:\$\s+|>\s+|running(?: command)?:\s*|executing:\s*)(.+)$",
    re.IGNORECASE,
)

_RE_DIFF_START = re.compile(r"^(diff --git|--- |\+\+\+ )")
_RE_DIFF_HUNK = re.compile(r"^@@ .* @@")
_RE_DIFF_LINE = re.compile(r"^[+\- ]")

_RE_PLAN_HEADER = re.compile(
    r"^\s*(plan|my plan|here.s (?:my|the) plan)\s*:?\s*$",
    re.IGNORECASE,
)

_RE_PLAN_ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+\S")

_RE_THINKING = re.compile(
    r"^\s*(thinking|reasoning)\.{0,3}\s*$",
    re.IGNORECASE,
)

_RE_ERROR = re.compile(
    r"^\s*(error:|traceback \(most recent call last\)|exception:|fatal:)",
    re.IGNORECASE,
)

_RE_WARNING = re.compile(
    r"^\s*(warning:|warn:)",
    re.IGNORECASE,
)

_RE_SUCCESS = re.compile(
    r"^\s*(done\.|success:?|all tests passed|task complete)",
    re.IGNORECASE,
)


class OpenClawStreamClassifier:
    """
    Stateful line-by-line classifier for OpenClaw's stdout.

    Buffers multi-line blocks (diffs, plans) so they arrive at
    the frontend as one coherent event instead of one tiny event
    per line. feed() is called once per line and returns zero or
    more fully-formed events; flush() drains anything still
    buffered once the process exits.
    """

    def __init__(self) -> None:
        self._diff_buffer: List[str] = []
        self._diff_path: Optional[str] = None
        self._plan_buffer: List[str] = []

    def _flush_diff(self) -> List[Dict[str, Any]]:

        if not self._diff_buffer:
            return []

        text = "\n".join(self._diff_buffer)
        path = self._diff_path

        self._diff_buffer = []
        self._diff_path = None

        return [
            {
                "type": "diff",
                "text": text,
                "path": path,
                "title": f"Diff: {path}" if path else "Diff",
            }
        ]

    def _flush_plan(self) -> List[Dict[str, Any]]:

        if not self._plan_buffer:
            return []

        text = "\n".join(self._plan_buffer)
        self._plan_buffer = []

        return [{"type": "plan", "text": text}]

    def _note_diff_path(self, line: str) -> None:

        if self._diff_path or not line.startswith(("+++ ", "--- ")):
            return

        candidate = line[4:].strip().split("\t")[0]

        if candidate and candidate not in ("/dev/null",):
            self._diff_path = re.sub(r"^[ab]/", "", candidate)

    def feed(self, line: str) -> List[Dict[str, Any]]:

        events: List[Dict[str, Any]] = []
        stripped = line.strip()

        # --- continuing / ending a diff block --------------------
        if self._diff_buffer:

            if (
                _RE_DIFF_LINE.match(line)
                or _RE_DIFF_HUNK.match(line)
                or _RE_DIFF_START.match(line)
            ):
                self._note_diff_path(line)
                self._diff_buffer.append(line)
                return events

            events.extend(self._flush_diff())
            # fall through -- reclassify this line normally

        # --- starting a new diff block ----------------------------
        if _RE_DIFF_START.match(line):
            events.extend(self._flush_plan())
            self._diff_buffer = [line]
            self._note_diff_path(line)
            return events

        # --- continuing / ending a plan block -----------------------
        if self._plan_buffer:

            if _RE_PLAN_ITEM.match(line) or not stripped:
                if stripped:
                    self._plan_buffer.append(line)
                return events

            events.extend(self._flush_plan())
            # fall through -- reclassify this line normally

        if _RE_PLAN_HEADER.match(line):
            self._plan_buffer = []
            return events

        if _RE_PLAN_ITEM.match(line):
            self._plan_buffer = [line]
            return events

        if not stripped:
            return events

        # --- single-line classifications --------------------------
        match = _RE_FILE_READ.match(stripped)
        if match:
            events.append(
                {"type": "file_read", "text": stripped, "path": match.group(1)}
            )
            return events

        match = _RE_FILE_WRITE.match(stripped)
        if match:
            events.append(
                {"type": "file_write", "text": stripped, "path": match.group(1)}
            )
            return events

        match = _RE_COMMAND.match(stripped)
        if match:
            events.append({"type": "command", "text": match.group(1).strip()})
            return events

        if _RE_ERROR.match(stripped):
            events.append({"type": "error", "text": stripped})
            return events

        if _RE_WARNING.match(stripped):
            events.append({"type": "warning", "text": stripped})
            return events

        if _RE_SUCCESS.match(stripped):
            events.append({"type": "success", "text": stripped})
            return events

        if _RE_THINKING.match(stripped):
            events.append({"type": "thinking", "text": stripped})
            return events

        events.append({"type": "output", "text": line})
        return events

    def flush(self) -> List[Dict[str, Any]]:

        events: List[Dict[str, Any]] = []
        events.extend(self._flush_diff())
        events.extend(self._flush_plan())
        return events


# ============================================================
# OPENCLAW PROCESS RUNNER
# ============================================================

def run_openclaw(
    message: str,
    project_path: Path,
    output_queue: Optional[queue.Queue] = None,
    model: Optional[str] = None,
    fallbacks: Optional[List[str]] = None,
    thinking: Optional[str] = None,
):
    """
    Run DevResearcher through OpenClaw.

    Supports:

        --model
        --fallback
        --thinking

    The OpenClaw installation handles provider authentication
    and model communication.
    """

    openclaw = find_openclaw()

    primary_model = normalize_model(model)

    fallback_models = normalize_fallbacks(
        fallbacks,
        primary_model,
    )

    prompt = build_agent_prompt(
        message=message,
        project_path=project_path,
        model=primary_model,
        fallbacks=fallback_models,
    )

    temp_prompt_path = None
    process = None

    try:

        # --------------------------------------------------------
        # Create temporary UTF-8 prompt file
        # --------------------------------------------------------

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".txt",
            prefix="devresearcher_",
            delete=False,
        ) as prompt_file:

            prompt_file.write(prompt)

            temp_prompt_path = prompt_file.name

        # --------------------------------------------------------
        # OpenClaw command
        # --------------------------------------------------------

        command = [
            openclaw,
            "agent",
            "--agent",
            AGENT_ID,
            "--message-file",
            temp_prompt_path,
            "--model",
            primary_model,
        ]

        # Add fallback models.
        for fallback in fallback_models:

            command.extend(
                [
                    "--fallback",
                    fallback,
                ]
            )

        # Optional thinking mode.
        if thinking:

            command.extend(
                [
                    "--thinking",
                    str(thinking),
                ]
            )

        print()
        print("=" * 70)
        print("Starting DevResearcher")
        print("=" * 70)
        print("OpenClaw:", openclaw)
        print("Agent:", AGENT_ID)
        print("Project:", project_path)
        print("Primary model:", primary_model)
        print(
            "Fallbacks:",
            fallback_models
            if fallback_models
            else "None",
        )
        print(
            "Thinking:",
            thinking
            if thinking
            else "default",
        )
        print("=" * 70)

        # --------------------------------------------------------
        # Start process
        # --------------------------------------------------------

        process = subprocess.Popen(
            command,
            cwd=str(project_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
        )

        active_processes.add(process)

        # --------------------------------------------------------
        # Stream output
        # --------------------------------------------------------

        classifier = OpenClawStreamClassifier()

        if process.stdout is not None:

            for line in iter(
                process.stdout.readline,
                "",
            ):

                if not line:
                    break

                line = line.rstrip("\r\n")

                print(line)

                if output_queue is not None:

                    for event in classifier.feed(line):
                        output_queue.put(event)

            if output_queue is not None:

                for event in classifier.flush():
                    output_queue.put(event)

        # --------------------------------------------------------
        # Wait
        # --------------------------------------------------------

        exit_code = process.wait()

        print(
            "DevResearcher exit code:",
            exit_code,
        )

        if output_queue is not None:

            output_queue.put(
                {
                    "type": "done",
                    "exit_code": exit_code,
                    "model": primary_model,
                    "fallbacks": fallback_models,
                }
            )

        return exit_code

    except Exception as exc:

        print(
            "DevResearcher execution error:",
            repr(exc),
        )

        if output_queue is not None:

            output_queue.put(
                {
                    "type": "error",
                    "message": str(exc),
                }
            )

            output_queue.put(
                {
                    "type": "done",
                    "exit_code": -1,
                }
            )

        return -1

    finally:

        if process is not None:
            active_processes.discard(process)

        # --------------------------------------------------------
        # Delete temporary prompt
        # --------------------------------------------------------

        if temp_prompt_path:

            try:
                os.remove(temp_prompt_path)

            except OSError:
                pass


# ============================================================
# NORMAL HTTP AGENT ENDPOINT
# ============================================================

@app.post("/api/agent/run")
async def run_agent(
    request: AgentRequest,
):

    message = request.message.strip()

    if not message:

        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty.",
        )

    try:

        project = validate_project_path(
            request.project_path
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    primary_model = normalize_model(
        request.model
    )

    fallback_models = normalize_fallbacks(
        request.fallbacks,
        primary_model,
    )

    result_queue = queue.Queue()

    exit_code = await asyncio.to_thread(
        run_openclaw,
        message,
        project,
        result_queue,
        primary_model,
        fallback_models,
        request.thinking,
    )

    output = []
    structured_events = []

    while not result_queue.empty():

        try:

            event = result_queue.get_nowait()

        except queue.Empty:
            break

        event_type = event.get("type")

        if event_type in ("done",):
            continue

        structured_events.append(event)

        text = event.get("text", "")

        if not text:
            continue

        # Reconstruct a readable plain-text transcript from every
        # classified event type (not just "output"), since the
        # classifier now turns most lines into thinking/plan/
        # tool/file_read/file_write/command/diff/etc. If this
        # only kept "output" events, most of a classified run
        # would silently vanish from the returned transcript.
        if event_type == "command":
            output.append(f"$ {text}")
        elif event_type == "file_read":
            output.append(f"[read] {text}")
        elif event_type == "file_write":
            output.append(f"[write] {text}")
        else:
            output.append(text)

    return {
        "success": exit_code == 0,
        "exit_code": exit_code,
        "agent": AGENT_ID,
        "project_path": str(project),
        "model": primary_model,
        "fallbacks": fallback_models,
        "thinking": request.thinking,
        "output": "\n".join(output),
        "events": structured_events,
    }


# ============================================================
# WEBSOCKET AGENT ENDPOINT
# ============================================================

@app.websocket("/ws/agent")
async def websocket_agent(
    websocket: WebSocket,
):

    await websocket.accept()

    print(
        "WebSocket connected."
    )

    try:

        # --------------------------------------------------------
        # Receive request
        # --------------------------------------------------------

        data = await websocket.receive_json()

        print(
            "WebSocket received:",
            data,
        )

        message = str(
            data.get(
                "message",
                "",
            )
        ).strip()

        project_path = str(
            data.get(
                "project_path",
                "",
            )
        ).strip()

        model = data.get(
            "model"
        )

        thinking = data.get(
            "thinking"
        )

        fallbacks = data.get(
            "fallbacks"
        )

        # --------------------------------------------------------
        # Normalize fallbacks
        # --------------------------------------------------------

        if fallbacks is not None:

            if not isinstance(
                fallbacks,
                list,
            ):

                fallbacks = [
                    str(fallbacks)
                ]

            else:

                fallbacks = [
                    str(item)
                    for item in fallbacks
                    if item
                ]

        # --------------------------------------------------------
        # Validate message
        # --------------------------------------------------------

        if not message:

            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Message cannot be empty.",
                }
            )

            return

        # --------------------------------------------------------
        # Validate project
        # --------------------------------------------------------

        try:

            project = validate_project_path(
                project_path
            )

        except Exception as exc:

            await websocket.send_json(
                {
                    "type": "error",
                    "message": str(exc),
                }
            )

            return

        # --------------------------------------------------------
        # Normalize model configuration
        # --------------------------------------------------------

        primary_model = normalize_model(
            model
        )

        fallback_models = normalize_fallbacks(
            fallbacks,
            primary_model,
        )

        # --------------------------------------------------------
        # Tell frontend agent started
        # --------------------------------------------------------

        await websocket.send_json(
            {
                "type": "start",
                "agent": AGENT_ID,
                "message": (
                    "DevResearcher started."
                ),
                "project_path": str(project),
                "model": primary_model,
                "fallbacks": fallback_models,
                "thinking": thinking,
            }
        )

        # --------------------------------------------------------
        # Queue for subprocess output
        # --------------------------------------------------------

        output_queue = queue.Queue()

        # --------------------------------------------------------
        # Start OpenClaw in background thread
        # --------------------------------------------------------

        worker = threading.Thread(
            target=run_openclaw,
            args=(
                message,
                project,
                output_queue,
                primary_model,
                fallback_models,
                thinking,
            ),
            daemon=True,
        )

        worker.start()

        # --------------------------------------------------------
        # Stream results to frontend
        # --------------------------------------------------------

        # Event types the OpenClawStreamClassifier can emit,
        # beyond the "output"/"error"/"done" control events that
        # run_openclaw() puts on the queue directly. These all
        # carry a "text" (and sometimes "path"/"title") payload
        # that AgentView already knows how to render richly.
        classified_types = (
            "thinking",
            "plan",
            "tool",
            "file_read",
            "file_write",
            "command",
            "diff",
            "success",
            "warning",
            "info",
        )

        async def forward(event: Dict[str, Any]) -> None:

            event_type = event.get("type")

            # ------------------------------------------------
            # OpenClaw output (unclassified passthrough)
            # ------------------------------------------------

            if event_type == "output":

                text = event.get("text", "")

                if text:

                    await websocket.send_json(
                        {
                            "type": "output",
                            "text": text,
                        }
                    )

            # ------------------------------------------------
            # Classified rich events
            # ------------------------------------------------

            elif event_type in classified_types:

                payload: Dict[str, Any] = {
                    "type": event_type,
                }

                for key in ("text", "path", "title"):

                    value = event.get(key)

                    if value:
                        payload[key] = value

                await websocket.send_json(payload)

            # ------------------------------------------------
            # Error
            # ------------------------------------------------

            elif event_type == "error":

                await websocket.send_json(
                    {
                        "type": "error",
                        "message": event.get(
                            "message",
                            "Unknown OpenClaw error.",
                        ),
                    }
                )

            # ------------------------------------------------
            # Process complete
            # ------------------------------------------------

            elif event_type == "done":

                await websocket.send_json(
                    {
                        "type": "done",
                        "exit_code": event.get(
                            "exit_code",
                            -1,
                        ),
                        "model": event.get(
                            "model",
                            primary_model,
                        ),
                        "fallbacks": event.get(
                            "fallbacks",
                            fallback_models,
                        ),
                    }
                )

        while (
            worker.is_alive()
            or not output_queue.empty()
        ):

            try:

                event = output_queue.get_nowait()

                await forward(event)

            except queue.Empty:

                await asyncio.sleep(
                    0.05
                )

        # --------------------------------------------------------
        # Flush anything remaining
        # --------------------------------------------------------

        while not output_queue.empty():

            try:

                event = output_queue.get_nowait()

                await forward(event)

            except queue.Empty:
                break

        print(
            "WebSocket request completed."
        )

    except WebSocketDisconnect:

        print(
            "WebSocket disconnected."
        )

    except Exception as exc:

        print(
            "WebSocket error:",
            repr(exc),
        )

        try:

            await websocket.send_json(
                {
                    "type": "error",
                    "message": str(exc),
                }
            )

        except Exception:
            pass

    finally:

        print(
            "WebSocket connection closed."
        )


# ============================================================
# OPENCLAW STATUS
# ============================================================

@app.get("/api/openclaw/status")
async def openclaw_status():

    try:

        openclaw = find_openclaw()

    except Exception as exc:

        return {
            "available": False,
            "error": str(exc),
        }

    return {
        "available": True,
        "path": openclaw,
        "agent": AGENT_ID,
        "primary_model": DEFAULT_MODEL,
        "fallbacks": DEFAULT_FALLBACKS,
    }


# ============================================================
# AGENT EXEC APPROVALS
#
# OpenClaw has its own exec-approval system for commands the
# agent wants to run under an "ask" policy (see `openclaw
# approvals` / `openclaw exec-policy`). A pending approval just
# sits there until something resolves it -- this backend does
# not implement approval logic itself, it is a thin, honest
# proxy onto the real `openclaw approvals` CLI so the GUI can
# show pending requests and let the user allow/deny them instead
# of the DevResearcher turn silently hanging.
# ============================================================

@app.get("/api/agent/approvals")
async def list_pending_approvals():

    try:
        openclaw = find_openclaw()
    except Exception as exc:
        return {
            "available": False,
            "approvals": [],
            "error": str(exc),
        }

    try:

        result = subprocess.run(
            [openclaw, "approvals", "pending", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
        )

    except subprocess.TimeoutExpired:

        return {
            "available": True,
            "approvals": [],
            "error": "Timed out listing approvals.",
        }

    except Exception as exc:

        return {
            "available": True,
            "approvals": [],
            "error": str(exc),
        }

    if result.returncode != 0:

        return {
            "available": True,
            "approvals": [],
            "error": (
                result.stderr or result.stdout or "Could not list approvals."
            ).strip(),
        }

    try:
        data = json.loads(result.stdout)
    except Exception:
        return {
            "available": True,
            "approvals": [],
            "error": "Could not parse the approvals response.",
        }

    approvals = (
        data.get("approvals", [])
        if isinstance(data, dict)
        else (data if isinstance(data, list) else [])
    )

    return {
        "available": True,
        "approvals": approvals,
        "error": None,
    }


class ApprovalResolveRequest(BaseModel):
    approval_id: str
    decision: str
    reason: Optional[str] = None


@app.post("/api/agent/approvals/resolve")
async def resolve_approval(request: ApprovalResolveRequest):

    if request.decision not in (
        "allow-once",
        "allow-always",
        "deny",
    ):
        raise HTTPException(
            status_code=400,
            detail="Decision must be allow-once, allow-always, or deny.",
        )

    try:
        openclaw = find_openclaw()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    command = [
        openclaw,
        "approvals",
        "resolve",
        request.approval_id,
        request.decision,
    ]

    if request.reason:
        command.extend(["--reason", request.reason])

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
        )

    except subprocess.TimeoutExpired:

        raise HTTPException(
            status_code=504,
            detail="Timed out resolving the approval.",
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    return {
        "success": result.returncode == 0,
        "output": (result.stdout + result.stderr).strip(),
    }


# ============================================================
# OLLAMA STATUS
# ============================================================

@app.get("/api/ollama/status")
async def ollama_status():

    ollama = find_ollama()

    if not ollama:

        return {
            "available": False,
            "path": None,
            "models": [],
        }

    models = []

    try:

        result = subprocess.run(
            [
                ollama,
                "list",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
        )

        lines = result.stdout.splitlines()

        # Skip header.
        for line in lines[1:]:

            line = line.strip()

            if not line:
                continue

            parts = line.split()

            if parts:
                models.append(
                    parts[0]
                )

    except Exception as exc:

        return {
            "available": True,
            "path": ollama,
            "models": [],
            "error": str(exc),
        }

    return {
        "available": True,
        "path": ollama,
        "models": models,
    }


# ============================================================
# ACTIVE PROCESS STATUS
# ============================================================

@app.get("/api/agent/processes")
async def active_processes_status():

    processes = []

    for process in list(
        active_processes
    ):

        try:

            running = (
                process.poll()
                is None
            )

        except Exception:

            running = False

        processes.append(
            {
                "pid": process.pid,
                "running": running,
            }
        )

    return {
        "count": len(processes),
        "processes": processes,
    }


# ============================================================
# STOP ACTIVE PROCESSES
# ============================================================

@app.post("/api/agent/stop")
async def stop_agents():

    stopped = []

    for process in list(
        active_processes
    ):

        try:

            if process.poll() is None:

                process.terminate()

                stopped.append(
                    process.pid
                )

        except Exception:
            pass

    return {
        "success": True,
        "stopped": stopped,
    }


# ============================================================
# PROJECT FILE OPERATIONS (save / create / delete / rename /
# folder / run)
# ============================================================

class WriteFileRequest(BaseModel):
    path: str
    content: str


class CreateFileRequest(BaseModel):
    project_path: str
    name: str
    content: str = ""


class CreateFolderRequest(BaseModel):
    project_path: str
    name: str


class RenameRequest(BaseModel):
    old_path: str
    new_name: str


class RunFileRequest(BaseModel):
    path: str


@app.put("/api/project/file")
async def write_project_file(request: WriteFileRequest):

    file_path = (
        Path(request.path)
        .expanduser()
        .resolve()
    )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    try:

        file_path.write_text(
            request.content,
            encoding="utf-8",
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not save file: {exc}",
        )

    return {
        "success": True,
        "path": str(file_path),
    }


def _is_safe_child(child: Path, parent: Path) -> bool:
    """
    Reject names that would escape the project directory.
    """
    return str(child.resolve()).startswith(
        str(parent.resolve())
    )
@app.post("/api/project/file")
async def create_project_file(request: CreateFileRequest):

    project = validate_project_path(
        request.project_path
    )

    name = (request.name or "").strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="File name cannot be empty.",
        )

    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(
            status_code=400,
            detail="Invalid file name.",
        )

    file_path = (project / name).resolve()

    if not _is_safe_child(file_path, project):
        raise HTTPException(
            status_code=400,
            detail="Invalid file path.",
        )

    if file_path.exists():
        raise HTTPException(
            status_code=400,
            detail="A file or folder with this name already exists.",
        )

    try:

        file_path.write_text(
            request.content or "",
            encoding="utf-8",
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not create file: {exc}",
        )

    return {
        "success": True,
        "path": str(file_path),
        "name": name,
    }


@app.delete("/api/project/file")
async def delete_project_file(path: str):

    file_path = (
        Path(path)
        .expanduser()
        .resolve()
    )

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    if file_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Use the folder endpoint for directories.",
        )

    try:

        file_path.unlink()

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not delete file: {exc}",
        )

    return {
        "success": True,
        "path": str(file_path),
    }


@app.post("/api/project/folder")
async def create_project_folder(request: CreateFolderRequest):

    project = validate_project_path(
        request.project_path
    )

    name = (request.name or "").strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Folder name cannot be empty.",
        )

    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(
            status_code=400,
            detail="Invalid folder name.",
        )

    folder_path = (project / name).resolve()

    if not _is_safe_child(folder_path, project):
        raise HTTPException(
            status_code=400,
            detail="Invalid folder path.",
        )

    if folder_path.exists():
        raise HTTPException(
            status_code=400,
            detail="A file or folder with this name already exists.",
        )

    try:

        folder_path.mkdir(
            parents=True,
            exist_ok=False,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not create folder: {exc}",
        )

    return {
        "success": True,
        "path": str(folder_path),
    }
@app.post("/api/project/rename")
async def rename_project_file(request: RenameRequest):

    old_path = (
        Path(request.old_path)
        .expanduser()
        .resolve()
    )

    new_name = (request.new_name or "").strip()

    if not new_name:
        raise HTTPException(
            status_code=400,
            detail="New name cannot be empty.",
        )

    if "/" in new_name or "\\" in new_name or ".." in new_name:
        raise HTTPException(
            status_code=400,
            detail="Invalid new name.",
        )

    if not old_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    new_path = old_path.parent / new_name

    if new_path.exists():
        raise HTTPException(
            status_code=400,
            detail="A file or folder with this name already exists.",
        )

    try:

        old_path.rename(new_path)

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not rename: {exc}",
        )

    return {
        "success": True,
        "path": str(new_path),
        "new_path": str(new_path),
    }


# ============================================================
# DELETE FOLDER
#
# The existing DELETE /api/project/file endpoint intentionally
# refuses directories. Folder deletion is recursive and
# therefore more dangerous, so it lives in its own endpoint and
# requires an explicit confirm=true query parameter in addition
# to whatever confirmation the frontend already shows the user.
# ============================================================

@app.delete("/api/project/folder")
async def delete_project_folder(
    path: str,
    confirm: bool = False,
):

    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Folder deletion requires confirm=true.",
        )

    folder_path = (
        Path(path)
        .expanduser()
        .resolve()
    )

    if not folder_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Folder not found.",
        )

    if not folder_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Use the file endpoint for files.",
        )

    try:

        shutil.rmtree(folder_path)

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not delete folder: {exc}",
        )

    return {
        "success": True,
        "path": str(folder_path),
    }


# ============================================================
# MOVE FILE OR FOLDER
#
# Rename (above) only supports renaming in place. This endpoint
# additionally supports moving a file/folder into a different
# directory, optionally combined with a rename, and is used for
# both the "Move to..." context-menu action and drag-and-drop
# in the Explorer. The source and destination must both resolve
# inside the workspace root.
# ============================================================

class MoveRequest(BaseModel):
    project_path: str
    source_path: str
    destination_dir: str
    new_name: Optional[str] = None


@app.post("/api/project/move")
async def move_project_entry(request: MoveRequest):

    project = validate_project_path(
        request.project_path
    )

    source = (
        Path(request.source_path)
        .expanduser()
        .resolve()
    )

    destination_dir = (
        Path(request.destination_dir)
        .expanduser()
        .resolve()
    )

    if not source.exists():
        raise HTTPException(
            status_code=404,
            detail="Source not found.",
        )

    if not _is_safe_child(source, project):
        raise HTTPException(
            status_code=400,
            detail="Source is outside the workspace.",
        )

    if not destination_dir.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Destination is not a directory.",
        )

    if not _is_safe_child(destination_dir, project):
        raise HTTPException(
            status_code=400,
            detail="Destination is outside the workspace.",
        )

    new_name = (
        request.new_name or source.name
    ).strip()

    if (
        not new_name
        or "/" in new_name
        or "\\" in new_name
        or new_name in ("..", ".")
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid destination name.",
        )

    target = destination_dir / new_name

    if _is_safe_child(target, source) and target != source:
        # Moving a folder into its own descendant would be
        # destructive/impossible -- reject explicitly instead of
        # letting shutil.move fail with a confusing error.
        raise HTTPException(
            status_code=400,
            detail="Cannot move a folder into itself.",
        )

    if target.exists():
        raise HTTPException(
            status_code=400,
            detail="A file or folder with this name already exists there.",
        )

    if target == source:
        return {
            "success": True,
            "path": str(target),
        }

    try:

        shutil.move(str(source), str(target))

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not move: {exc}",
        )

    return {
        "success": True,
        "path": str(target),
    }


# ============================================================
# SYSTEM INTEGRATION
#
# Reveal a file/folder in the OS file manager, or open a file
# with whatever application the OS has associated with it.
# Windows is primary (per the project's target platform); macOS
# and Linux fall back to their usual equivalents so the backend
# does not hard-crash if it is ever run elsewhere (e.g. by the
# maintainer during development).
# ============================================================

class SystemPathRequest(BaseModel):
    path: str


def _open_in_file_manager(target: Path) -> None:

    if os.name == "nt":

        if target.is_dir():
            subprocess.Popen(["explorer", str(target)])
        else:
            # NOTE: no space after the comma -- this is the
            # documented Windows Explorer syntax for selecting a
            # specific file, and it only works as one argv token.
            subprocess.Popen(["explorer", f"/select,{target}"])

    elif sys.platform == "darwin":

        subprocess.Popen(["open", "-R", str(target)])

    else:

        subprocess.Popen(
            ["xdg-open", str(target if target.is_dir() else target.parent)]
        )


def _open_externally(target: Path) -> None:

    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])


@app.post("/api/system/reveal")
async def reveal_in_file_manager(request: SystemPathRequest):

    target = (
        Path(request.path)
        .expanduser()
        .resolve()
    )

    if not target.exists():
        raise HTTPException(
            status_code=404,
            detail="Path not found.",
        )

    try:

        _open_in_file_manager(target)

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not open file manager: {exc}",
        )

    return {"success": True}


@app.post("/api/system/open")
async def open_externally(request: SystemPathRequest):

    target = (
        Path(request.path)
        .expanduser()
        .resolve()
    )

    if not target.exists() or not target.is_file():
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    try:

        _open_externally(target)

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not open file externally: {exc}",
        )

    return {"success": True}


def _interpreter_command(
    file_path: Path,
) -> List[str]:
    """
    Build a run command for file types that are directly
    interpretable/runnable as a single file, with no
    project-wide build step required.

    Returns [] if the extension is not in this category --
    callers should fall back to COMPILED_LANGUAGE_HINTS or
    report the type as unsupported.
    """

    ext = file_path.suffix.lower()

    if ext == ".py":
        return [sys.executable, "-u", str(file_path)]

    if ext in (".js", ".mjs", ".cjs"):
        return ["node", str(file_path)]

    if ext in (".ts", ".tsx"):
        # tsx (https://github.com/privatenumber/tsx) runs
        # TypeScript directly via `npx` without a separate
        # project-wide build step, which matches the "run this
        # one file" semantics of the button. If the user's
        # project needs its own tsconfig/bundler behavior,
        # the integrated Terminal is the right place for that.
        return ["npx", "--yes", "tsx", str(file_path)]

    if ext == ".sh":
        return ["bash", str(file_path)]

    if ext == ".ps1":
        shell = (
            "pwsh"
            if shutil.which("pwsh")
            else "powershell"
        )
        return [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(file_path),
        ]

    if ext in (".bat", ".cmd"):
        return [str(file_path)]

    if ext == ".php":
        return ["php", str(file_path)]

    if ext == ".rb":
        return ["ruby", str(file_path)]

    if ext == ".go":
        # `go run` compiles and runs in one step, so it still
        # behaves like a single-file "Run" action.
        return ["go", "run", str(file_path)]

    if ext == ".pl":
        return ["perl", str(file_path)]

    if ext == ".lua":
        return ["lua", str(file_path)]

    return []


# Languages that genuinely need a project-aware build step
# (classpath, linked libraries, package structure, project
# file) before anything can run. A generic single-file "Run"
# button cannot infer that correctly, so rather than faking a
# build, this tells the user the real command for the
# integrated Terminal, which *does* have full shell semantics.
COMPILED_LANGUAGE_HINTS = {
    ".java": "Java needs a classpath/package-aware build. In the Terminal: javac {name} && java {stem}",
    ".c": "C needs an explicit compiler invocation. In the Terminal: gcc {name} -o {stem} && ./{stem}",
    ".cpp": "C++ needs an explicit compiler invocation. In the Terminal: g++ {name} -o {stem} && ./{stem}",
    ".cc": "C++ needs an explicit compiler invocation. In the Terminal: g++ {name} -o {stem} && ./{stem}",
    ".cs": "C# projects are normally built with dotnet. In the Terminal: dotnet run",
    ".rs": "Rust files are normally part of a Cargo project. In the Terminal: cargo run",
    ".kt": "Kotlin needs a compile step. In the Terminal: kotlinc {name} -include-runtime -d {stem}.jar && java -jar {stem}.jar",
    ".swift": "Swift needs a compile step. In the Terminal: swiftc {name} -o {stem} && ./{stem}",
}


@app.post("/api/project/run")
async def run_project_file(request: RunFileRequest):

    file_path = (
        Path(request.path)
        .expanduser()
        .resolve()
    )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    ext = file_path.suffix.lower()

    if ext in COMPILED_LANGUAGE_HINTS:

        hint = COMPILED_LANGUAGE_HINTS[ext].format(
            name=file_path.name,
            stem=file_path.stem,
        )

        return {
            "output": "",
            "stderr": (
                f"{file_path.suffix} files need a real build step "
                f"that a single-file Run button can't safely guess "
                f"(classpath, linked libraries, project layout). "
                f"Use the integrated Terminal instead:\n{hint}"
            ),
            "exit_code": -1,
            "needs_terminal": True,
        }

    command = _interpreter_command(file_path)

    if not command:

        return {
            "output": "",
            "stderr": (
                f"'{file_path.suffix or file_path.name}' has no direct "
                f"run mapping. Use the integrated Terminal to run it "
                f"with whatever tool the project expects."
            ),
            "exit_code": -1,
            "needs_terminal": True,
        }

    # For commands that go through an interpreter binary (as
    # opposed to directly executing a .bat/.cmd/.ps1 file),
    # confirm the interpreter is actually on PATH first so the
    # error is a clear message instead of a raw WinError/OSError.
    interpreter = command[0]

    if interpreter not in (str(file_path),) and not (
        os.path.isabs(interpreter) and os.path.isfile(interpreter)
    ):

        if shutil.which(interpreter) is None:

            return {
                "output": "",
                "stderr": (
                    f"'{interpreter}' was not found on PATH. "
                    f"Install it, or run this file yourself from "
                    f"the integrated Terminal once it's available."
                ),
                "exit_code": -1,
                "needs_terminal": True,
            }

    try:

        result = subprocess.run(
            command,
            cwd=str(file_path.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
        )

    except subprocess.TimeoutExpired:

        return {
            "output": "",
            "stderr": "Execution timed out.",
            "exit_code": -1,
        }

    except Exception as exc:

        return {
            "output": "",
            "stderr": f"Could not run file: {exc}",
            "exit_code": -1,
        }

    return {
        "output": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
    }
# ============================================================
# GIT / VERSION CONTROL
# ============================================================

class GitBaseRequest(BaseModel):
    path: str


class GitFilesRequest(BaseModel):
    path: str
    files: Optional[List[str]] = None


class GitCommitRequest(BaseModel):
    path: str
    message: str


def _git_available() -> bool:
    return shutil.which("git") is not None


def _run_git(
    command: List[str],
    cwd,
    timeout: int = 60,
):
    if not _git_available():
        raise RuntimeError(
            "Git is not installed or unavailable."
        )

    try:

        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
        )

        return (
            result.returncode,
            result.stdout,
            result.stderr,
        )

    except subprocess.TimeoutExpired:
        raise RuntimeError("Git command timed out.")

    except OSError as exc:
        raise RuntimeError(f"Could not run Git: {exc}")


def _git_is_repo(project) -> bool:
    try:
        code, out, _err = _run_git(
            ["git", "rev-parse", "--is-inside-work-tree"],
            str(project),
        )
        return code == 0 and out.strip() == "true"
    except RuntimeError:
        return False


def _git_branch(project) -> str:
    try:
        code, out, _err = _run_git(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            str(project),
        )
        if code == 0:
            branch = out.strip()
            if branch and branch != "HEAD":
                return branch
        return "detached"
    except RuntimeError:
        return "No Git"


def _resolve_git_files(project, files: Optional[List[str]]):
    if not files:
        return []
    resolved = []
    for item in files:
        if not item:
            continue
        p = Path(item)
        if p.is_absolute():
            resolved.append(str(p))
        else:
            resolved.append(str((project / item).resolve()))
    return resolved


@app.get("/api/git/status")
async def git_status(path: str):

    if not _git_available():
        return {
            "available": False,
            "is_repo": False,
            "branch": "No Git",
            "changes": [],
            "error": "Git is not installed or unavailable.",
        }

    try:
        project = validate_project_path(path)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    if not _git_is_repo(project):
        return {
            "available": True,
            "is_repo": False,
            "branch": "No Git",
            "changes": [],
            "error": "This project is not a Git repository.",
        }

    branch = _git_branch(project)

    try:
        _code, out, _err = _run_git(
            ["git", "status", "--porcelain=v1", "-z"],
            str(project),
        )
    except RuntimeError as exc:
        return {
            "available": True,
            "is_repo": True,
            "branch": branch,
            "changes": [],
            "error": str(exc),
        }

    changes = []
    parts = out.split("\x00")
    idx = 0

    while idx < len(parts):
        raw = parts[idx]
        idx += 1
        if not raw:
            continue
        if len(raw) < 4:
            continue

        xy = raw[:2]
        index_status = xy[0]
        worktree_status = xy[1]
        entry_path = raw[3:]
        from_path = None

        if (
            index_status in "RC"
            or worktree_status in "RC"
        ):
            if idx < len(parts):
                from_path = entry_path
                entry_path = parts[idx]
                idx += 1

        untracked = xy == "??"
        rel_path = entry_path.replace("\\", "/")

        changes.append(
            {
                "path": rel_path,
                "from_path": (
                    from_path.replace("\\", "/")
                    if from_path
                    else None
                ),
                "status": (
                    index_status
                    if index_status not in " ?"
                    else worktree_status
                ) or "?",
                "staged": (
                    index_status
                    if index_status not in " ?"
                    else None
                ),
                "unstaged": (
                    worktree_status
                    if worktree_status not in " ?"
                    else None
                ),
                "untracked": untracked,
            }
        )

    return {
        "available": True,
        "is_repo": True,
        "branch": branch,
        "changes": changes,
        "error": None,
    }


# ============================================================
@app.get("/api/git/branch")
async def git_branch(path: str):

    if not _git_available():
        return {
            "available": False,
            "branch": "No Git",
            "is_repo": False,
        }

    try:
        project = validate_project_path(path)
    except Exception:
        return {
            "available": True,
            "is_repo": False,
            "branch": "No Git",
        }

    if not _git_is_repo(project):
        return {
            "available": True,
            "is_repo": False,
            "branch": "No Git",
        }

    return {
        "available": True,
        "is_repo": True,
        "branch": _git_branch(project),
    }


@app.get("/api/git/diff")
async def git_diff(path: str, file: str):

    project = validate_project_path(path)

    if not _git_is_repo(project):
        raise HTTPException(
            status_code=400,
            detail="This project is not a Git repository.",
        )

    target = (
        (project / file).resolve()
        if file
        else project
    )

    try:
        _code, out, _err = _run_git(
            ["git", "diff", "HEAD", "--", str(target)],
            str(project),
        )
        content = out
        if not content.strip():
            _code2, out2, _err2 = _run_git(
                ["git", "diff", "--", str(target)],
                str(project),
            )
            content = out2
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    return {
        "path": file,
        "content": content,
    }


@app.post("/api/git/stage")
async def git_stage(request: GitFilesRequest):

    project = validate_project_path(request.path)

    if not _git_is_repo(project):
        raise HTTPException(
            status_code=400,
            detail="This project is not a Git repository.",
        )

    files = _resolve_git_files(project, request.files)
    command = (
        ["git", "add", "-A"]
        if not files
        else ["git", "add", "--", *files]
    )

    try:
        code, out, err = _run_git(command, str(project))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    return {
        "success": code == 0,
        "output": (out + err).strip(),
    }


@app.post("/api/git/unstage")
async def git_unstage(request: GitFilesRequest):

    project = validate_project_path(request.path)

    if not _git_is_repo(project):
        raise HTTPException(
            status_code=400,
            detail="This project is not a Git repository.",
        )

    files = _resolve_git_files(project, request.files)
    command = (
        ["git", "reset"]
        if not files
        else ["git", "restore", "--staged", "--", *files]
    )

    try:
        code, out, err = _run_git(command, str(project))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    return {
        "success": code == 0,
        "output": (out + err).strip(),
    }


@app.post("/api/git/discard")
async def git_discard(request: GitFilesRequest):

    project = validate_project_path(request.path)

    if not _git_is_repo(project):
        raise HTTPException(
            status_code=400,
            detail="This project is not a Git repository.",
        )

    files = _resolve_git_files(project, request.files)
    command = (
        ["git", "checkout", "--", *files]
        if files
        else ["git", "checkout", "--", "."]
    )

    try:
        code, out, err = _run_git(command, str(project))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    return {
        "success": code == 0,
        "output": (out + err).strip(),
    }


@app.post("/api/git/commit")
async def git_commit(request: GitCommitRequest):

    message = (request.message or "").strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Commit message cannot be empty.",
        )

    project = validate_project_path(request.path)

    if not _git_is_repo(project):
        raise HTTPException(
            status_code=400,
            detail="This project is not a Git repository.",
        )

    try:
        code, out, err = _run_git(
            ["git", "commit", "-m", message],
            str(project),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    result = (out + err).strip()

    return {
        "success": code == 0,
        "output": result,
        "error": None if code == 0 else (
            result or "Commit failed."
        ),
    }
# CONTINUED GIT (branch / diff / stage / unstage / discard /
# commit)
# ============================================================
# ============================================================
# ============================================================
# SEARCH
# ============================================================

@app.get("/api/search")
async def search(
    path: str,
    query: str,
):

    query = (query or "").strip()

    if not query:
        return {
            "items": [],
            "error": None,
        }

    try:
        project = validate_project_path(path)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    results = []
    q = query.lower()
    content_hit = 0
    filename_hit = 0

    for root, dirs, files in os.walk(project):

        dirs[:] = [
            d
            for d in dirs
            if d not in IGNORED_DIRECTORIES
        ]

        try:
            rel_root = Path(root).relative_to(project)
        except ValueError:
            rel_root = Path(".")

        for fname in files:

            full = Path(root) / fname
            rel_path = str(
                rel_root / fname
            ).replace("\\", "/")

            if filename_hit < 200 and q in fname.lower():

                filename_hit += 1
                results.append(
                    {
                        "type": "file",
                        "kind": "filename",
                        "name": fname,
                        "path": str(full),
                        "relative_path": rel_path,
                        "line": None,
                        "line_text": None,
                    }
                )

            if content_hit >= 200:
                continue

            try:

                with open(full, "rb") as fh:
                    data = fh.read(1024 * 512)

                if b"\x00" in data[:2048]:
                    continue

                text = data.decode(
                    "utf-8",
                    errors="replace",
                )

            except Exception:
                continue

            lines = text.splitlines()

            for ln, line in enumerate(lines, 1):
                if q in line.lower():

                    content_hit += 1
                    results.append(
                        {
                            "type": "file",
                            "kind": "content",
                            "name": fname,
                            "path": str(full),
                            "relative_path": rel_path,
                            "line": ln,
                            "line_text": line.strip()[:200],
                        }
                    )
                    break

    return {
        "items": results,
        "error": None,
    }


# ============================================================
# INTEGRATED TERMINAL
#
# A real, persistent shell process per connection, started in
# the current workspace directory. This intentionally does NOT
# use a pseudo-terminal (no ConPTY / no pywinpty dependency), so
# it is honest about two limits:
#
#   1. There is no line-editing/history inside the shell itself
#      -- the frontend terminal widget handles backspace/typing
#      locally and only sends a completed line on Enter.
#   2. Ctrl+C cannot deliver a real SIGINT to whatever the shell
#      is currently running (that requires a real console/TTY
#      driver). "Stop" instead force-kills the whole process
#      tree and starts a fresh shell, which is the honest
#      equivalent given this architecture.
#
# Everything else -- npm install, git, python, pip, node,
# cargo, arbitrary commands, colored output via ANSI codes
# rendered by xterm.js on the frontend -- works because it's a
# real OS process with real stdin/stdout, not a simulation.
# ============================================================

def _default_shell() -> List[str]:

    if os.name == "nt":
        return ["cmd.exe"]

    return [os.environ.get("SHELL") or "/bin/bash"]


def _resolve_shell(shell_override: Optional[str]) -> List[str]:

    if not shell_override:
        return _default_shell()

    presets = {
        "cmd": ["cmd.exe"],
        "powershell": ["powershell.exe", "-NoLogo"],
        "pwsh": ["pwsh", "-NoLogo"],
        "bash": ["bash"],
        "wsl": ["wsl.exe"],
        "zsh": ["zsh"],
    }

    candidate = presets.get(
        shell_override.lower(),
        [shell_override],
    )

    binary = candidate[0]

    if shutil.which(binary) or os.path.isfile(binary):
        return candidate

    # Unknown/unavailable override -- fall back rather than
    # failing the whole terminal session over a bad setting.
    return _default_shell()


class TerminalSession:

    def __init__(
        self,
        session_id: str,
        cwd: str,
        shell_override: Optional[str] = None,
    ):

        self.id = session_id
        self.cwd = cwd
        self.shell_command = _resolve_shell(shell_override)
        self.output_queue: "queue.Queue" = queue.Queue()
        self.alive = True

        self.process = subprocess.Popen(
            self.shell_command,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
        )

        self.reader_thread = threading.Thread(
            target=self._pump_output,
            daemon=True,
        )

        self.reader_thread.start()

    def _pump_output(self) -> None:

        fd = self.process.stdout.fileno()

        while True:

            try:
                chunk = os.read(fd, 4096)
            except (OSError, ValueError):
                break

            if not chunk:
                break

            self.output_queue.put(
                {
                    "type": "data",
                    "data": chunk.decode(
                        "utf-8",
                        errors="replace",
                    ),
                }
            )

        try:
            exit_code = self.process.wait(timeout=2)
        except Exception:
            exit_code = None

        self.alive = False

        self.output_queue.put(
            {
                "type": "exit",
                "code": exit_code,
            }
        )

    def write(self, data: str) -> None:

        if (
            not self.process.stdin
            or self.process.poll() is not None
        ):
            return

        try:
            self.process.stdin.write(
                data.encode("utf-8", errors="replace")
            )
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def kill(self) -> None:

        self.alive = False

        try:

            if os.name == "nt":

                subprocess.run(
                    [
                        "taskkill",
                        "/F",
                        "/T",
                        "/PID",
                        str(self.process.pid),
                    ],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

            else:

                self.process.terminate()

        except Exception:
            pass


terminal_sessions: Dict[str, TerminalSession] = {}


@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):

    await websocket.accept()

    send_lock = asyncio.Lock()
    session: Optional[TerminalSession] = None
    pump_task: Optional[asyncio.Task] = None

    async def safe_send(payload: Dict[str, Any]) -> bool:

        async with send_lock:

            try:
                await websocket.send_json(payload)
                return True
            except Exception:
                return False

    async def pump_output(active: TerminalSession) -> None:

        loop = asyncio.get_event_loop()

        while True:

            event = await loop.run_in_executor(
                None,
                active.output_queue.get,
            )

            delivered = await safe_send(event)

            if not delivered or event.get("type") == "exit":
                return

    def start_session(
        cwd: str,
        shell_override: Optional[str],
    ) -> TerminalSession:

        new_session = TerminalSession(
            str(uuid.uuid4()),
            cwd,
            shell_override,
        )

        terminal_sessions[new_session.id] = new_session

        return new_session

    try:

        init = await websocket.receive_json()

        cwd_request = str(
            init.get("cwd", "")
        ).strip()

        shell_override = init.get("shell") or None

        try:
            cwd_path = validate_project_path(cwd_request)
        except Exception as exc:
            await safe_send({"type": "error", "data": str(exc)})
            return

        session = start_session(
            str(cwd_path),
            shell_override,
        )

        await safe_send(
            {
                "type": "ready",
                "session_id": session.id,
                "cwd": str(cwd_path),
                "shell": " ".join(session.shell_command),
            }
        )

        pump_task = asyncio.create_task(
            pump_output(session)
        )

        while True:

            message = await websocket.receive_json()
            action = message.get("type")

            if action == "input":

                session.write(
                    str(message.get("data", ""))
                )

            elif action == "kill":

                session.kill()

            elif action == "restart":

                session.kill()

                terminal_sessions.pop(
                    session.id,
                    None,
                )

                if pump_task:
                    pump_task.cancel()

                session = start_session(
                    str(cwd_path),
                    shell_override,
                )

                await safe_send(
                    {
                        "type": "ready",
                        "session_id": session.id,
                        "cwd": str(cwd_path),
                        "shell": " ".join(
                            session.shell_command
                        ),
                    }
                )

                pump_task = asyncio.create_task(
                    pump_output(session)
                )

    except WebSocketDisconnect:
        pass

    except Exception as exc:

        await safe_send(
            {
                "type": "error",
                "data": str(exc),
            }
        )

    finally:

        if pump_task:
            pump_task.cancel()

        if session is not None:
            session.kill()
            terminal_sessions.pop(session.id, None)


@app.get("/api/terminal/sessions")
async def list_terminal_sessions():

    return {
        "count": len(terminal_sessions),
        "sessions": [
            {
                "id": s.id,
                "cwd": s.cwd,
                "shell": " ".join(s.shell_command),
                "alive": s.alive,
            }
            for s in terminal_sessions.values()
        ],
    }


# ============================================================
# SEARCH AND REPLACE
#
# If `files` (relative paths) is provided, the replacement is
# scoped to exactly those files -- this is how the Explorer
# search panel does a safe "replace only what I already
# previewed". If `files` is omitted, every non-binary file in
# the workspace (outside IGNORED_DIRECTORIES) is scanned, same
# as GET /api/search, and any file containing a match is
# rewritten. Either way this performs real writes -- the
# frontend confirms with the user before calling it.
# ============================================================

class ReplaceRequest(BaseModel):
    path: str
    query: str
    replacement: str = ""
    files: Optional[List[str]] = None
    case_sensitive: bool = True


@app.post("/api/search/replace")
async def search_replace(request: ReplaceRequest):

    query = request.query

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty.",
        )

    project = validate_project_path(request.path)

    candidates: List[Path] = []

    if request.files:

        for rel in request.files:

            candidate = (project / rel).resolve()

            if (
                _is_safe_child(candidate, project)
                and candidate.is_file()
            ):
                candidates.append(candidate)

    else:

        for root, dirs, files in os.walk(project):

            dirs[:] = [
                d
                for d in dirs
                if d not in IGNORED_DIRECTORIES
            ]

            for fname in files:
                candidates.append(Path(root) / fname)

    changed_files = []
    total_replacements = 0

    matcher = re.compile(
        re.escape(query),
        0 if request.case_sensitive else re.IGNORECASE,
    )

    for file_path in candidates:

        try:

            with open(file_path, "rb") as fh:
                raw = fh.read(2 * 1024 * 1024)

            if b"\x00" in raw[:2048]:
                continue

            text = raw.decode(
                "utf-8",
                errors="replace",
            )

        except Exception:
            continue

        count = len(matcher.findall(text))

        if count == 0:
            continue

        new_text = matcher.sub(
            lambda _m: request.replacement,
            text,
        )

        try:

            file_path.write_text(
                new_text,
                encoding="utf-8",
            )

        except Exception:
            continue

        try:
            rel_path = str(
                file_path.relative_to(project)
            ).replace("\\", "/")
        except ValueError:
            rel_path = str(file_path)

        changed_files.append(
            {
                "path": rel_path,
                "replacements": count,
            }
        )

        total_replacements += count

    return {
        "success": True,
        "files_changed": len(changed_files),
        "total_replacements": total_replacements,
        "files": changed_files,
    }


# ============================================================
# STARTUP
# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    print()
    print("=" * 70)
    print("DEVRESEARCHER BACKEND")
    print("=" * 70)

    try:

        openclaw = find_openclaw()

        print(
            "OpenClaw detected:",
            openclaw,
        )

    except Exception as exc:

        print(
            "WARNING: OpenClaw not detected:"
        )

        print(exc)

    ollama = find_ollama()

    if ollama:

        print(
            "Ollama detected:",
            ollama,
        )

    else:

        print(
            "Ollama: not detected"
        )

    print(
        "Agent:",
        AGENT_ID,
    )

    print(
        "Primary model:",
        DEFAULT_MODEL,
    )

    print(
        "Default fallback:",
        DEFAULT_FALLBACKS,
    )

    print(
        "API:",
        f"http://{HOST}:{PORT}",
    )

    print(
        "WebSocket:",
        f"ws://{HOST}:{PORT}/ws/agent",
    )

    print("=" * 70)
    print()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        reload=False,
    )