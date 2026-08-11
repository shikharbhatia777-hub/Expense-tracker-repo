import asyncio
import json
import os
import threading
import traceback
import webbrowser

import streamlit as st
from dotenv import load_dotenv

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from pydantic import AnyUrl

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)

from mcp.client.auth import (
    OAuthClientProvider,
    TokenStorage,
)

from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

EXPENSE_MCP_URL = (
    "https://essential-white-crayfish.fastmcp.app/mcp"
)

OAUTH_REDIRECT_URI = (
    "http://localhost:8765/callback"
)

OAUTH_CALLBACK_PORT = 8765

OAUTH_TOKEN_FILE = "mcp_oauth_tokens.json"


# ============================================================
# OAUTH TOKEN STORAGE
# ============================================================

class FileTokenStorage(TokenStorage):

    def __init__(
        self,
        filename=OAUTH_TOKEN_FILE,
    ):
        self.filename = filename

        self.tokens = None
        self.client_info = None

        self._load()

    def _load(self):

        if not os.path.exists(self.filename):
            return

        try:

            with open(
                self.filename,
                "r",
                encoding="utf-8",
            ) as f:

                data = json.load(f)

            if data.get("tokens"):

                self.tokens = (
                    OAuthToken.model_validate(
                        data["tokens"]
                    )
                )

            if data.get("client_info"):

                self.client_info = (
                    OAuthClientInformationFull.model_validate(
                        data["client_info"]
                    )
                )

        except Exception as e:

            print(
                "Warning: Could not load "
                f"OAuth token storage: {e}"
            )

    def _save(self):

        data = {

            "tokens": (
                self.tokens.model_dump(
                    mode="json"
                )
                if self.tokens
                else None
            ),

            "client_info": (
                self.client_info.model_dump(
                    mode="json"
                )
                if self.client_info
                else None
            ),
        }

        with open(
            self.filename,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
            )

    async def get_tokens(
        self,
    ):

        return self.tokens

    async def set_tokens(
        self,
        tokens,
    ):

        self.tokens = tokens

        self._save()

    async def get_client_info(
        self,
    ):

        return self.client_info

    async def set_client_info(
        self,
        client_info,
    ):

        self.client_info = client_info

        self._save()


# ============================================================
# OAUTH CALLBACK SERVER
# ============================================================

class OAuthCallbackHandler(
    BaseHTTPRequestHandler
):

    server_version = (
        "MCP-OAuth-Callback/1.0"
    )

    def do_GET(self):

        parsed = urlparse(
            self.path
        )

        if parsed.path != "/callback":

            self.send_response(404)
            self.end_headers()

            return

        query = parse_qs(
            parsed.query
        )

        code = query.get(
            "code",
            [None],
        )[0]

        state = query.get(
            "state",
            [None],
        )[0]

        error = query.get(
            "error",
            [None],
        )[0]

        self.server.oauth_code = code
        self.server.oauth_state = state
        self.server.oauth_error = error

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8",
        )

        self.end_headers()

        if error:

            html = f"""
            <html>
                <body>
                    <h2>MCP OAuth authentication failed</h2>

                    <p>
                        Error:
                        {error}
                    </p>

                    <p>
                        You can close this browser tab.
                    </p>
                </body>
            </html>
            """

        else:

            html = """
            <html>
                <body>
                    <h2>Authentication successful</h2>

                    <p>
                        You can close this browser tab.
                    </p>

                    <p>
                        Return to the Streamlit application.
                    </p>
                </body>
            </html>
            """

        self.wfile.write(
            html.encode("utf-8")
        )

    def log_message(
        self,
        format,
        *args,
    ):

        return


# ============================================================
# CALLBACK SERVER CLASS
# ============================================================

class OAuthCallbackServer:

    def __init__(
        self,
        port=OAUTH_CALLBACK_PORT,
    ):

        self.port = port

        self.server = HTTPServer(
            (
                "127.0.0.1",
                self.port,
            ),
            OAuthCallbackHandler,
        )

        self.server.oauth_code = None
        self.server.oauth_state = None
        self.server.oauth_error = None

        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )

    def start(self):

        self.thread.start()

        print(
            "\nOAuth callback server started:"
        )

        print(
            "http://localhost:"
            f"{self.port}/callback\n"
        )

    def wait_for_callback(
        self,
        timeout=300,
    ):

        import time

        start_time = time.time()

        while (
            time.time() - start_time
            < timeout
        ):

            if self.server.oauth_error:

                raise RuntimeError(
                    "OAuth authorization failed: "
                    + self.server.oauth_error
                )

            if self.server.oauth_code:

                return (
                    self.server.oauth_code,
                    self.server.oauth_state,
                )

            time.sleep(0.25)

        raise TimeoutError(
            "Timed out waiting for OAuth callback."
        )

    def stop(self):

        try:

            self.server.shutdown()

        except Exception:

            pass


# ============================================================
# GLOBAL CALLBACK SERVER
# ============================================================

oauth_callback_server = None


# ============================================================
# OPEN AUTHORIZATION URL
# ============================================================

async def handle_redirect(
    authorization_url: str,
):

    print("\n")
    print("=" * 70)
    print(
        "MCP OAUTH AUTHORIZATION REQUIRED"
    )
    print("=" * 70)

    print(
        "Opening Horizon authentication "
        "in your browser..."
    )

    print("=" * 70)

    print("\nAuthorization URL:")

    print(
        authorization_url
    )

    print("\n")

    webbrowser.open(
        authorization_url
    )


# ============================================================
# HANDLE OAUTH CALLBACK
# ============================================================

async def handle_callback():

    global oauth_callback_server

    if oauth_callback_server is None:

        raise RuntimeError(
            "OAuth callback server is not running."
        )

    print(
        "Waiting for OAuth callback..."
    )

    code, state = await asyncio.to_thread(
        oauth_callback_server.wait_for_callback,
        300,
    )

    return code, state


# ============================================================
# CREATE OAUTH PROVIDER
# ============================================================

def create_oauth_provider():

    global oauth_callback_server

    # --------------------------------------------------------
    # Start local callback server
    # --------------------------------------------------------

    if oauth_callback_server is None:

        oauth_callback_server = (
            OAuthCallbackServer(
                OAUTH_CALLBACK_PORT
            )
        )

        oauth_callback_server.start()

    # --------------------------------------------------------
    # OAuth client metadata
    # --------------------------------------------------------

    client_metadata = OAuthClientMetadata(

        client_name=(
            "Streamlit MCP Expense Client"
        ),

        redirect_uris=[
            AnyUrl(
                OAUTH_REDIRECT_URI
            )
        ],

        grant_types=[
            "authorization_code",
            "refresh_token",
        ],

        response_types=[
            "code"
        ],

        token_endpoint_auth_method=(
            "none"
        ),
    )

    # --------------------------------------------------------
    # Persistent token storage
    # --------------------------------------------------------

    token_storage = FileTokenStorage()

    # --------------------------------------------------------
    # OAuth provider
    # --------------------------------------------------------

    oauth_provider = OAuthClientProvider(

        server_url=EXPENSE_MCP_URL,

        client_metadata=client_metadata,

        storage=token_storage,

        redirect_handler=handle_redirect,

        callback_handler=handle_callback,
    )

    return oauth_provider


# ============================================================
# MCP SERVER CONFIGURATION
# ============================================================

def create_servers():

    oauth_provider = (
        create_oauth_provider()
    )

    return {

        # ====================================================
        # LOCAL MATH MCP SERVER
        # ====================================================

        "math": {

            "transport": "stdio",

            "command": "uv",

            "args": [

                "run",

                "fastmcp",

                "run",

                "C:/Users/ShikharBhatia/Downloads/maths_tool/main.py",
            ],
        },

        # ====================================================
        # REMOTE EXPENSE MCP SERVER
        # ====================================================

        "expense": {

            "transport": "streamable_http",

            "url": EXPENSE_MCP_URL,

            "auth": oauth_provider,
        },
    }


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """

You are a helpful assistant with access to MCP tools.

Use the available tools whenever they are required
to answer the user's question.

Do not narrate tool execution or internal steps.

After using a tool, provide only a concise and
helpful final answer.

"""


# ============================================================
# STREAMLIT CONFIGURATION
# ============================================================

st.set_page_config(

    page_title="MCP Chat",

    page_icon="🧰",

    layout="centered",
)

st.title("🧰 MCP Chat")


# ============================================================
# SESSION STATE
# ============================================================

if "history" not in st.session_state:

    st.session_state.history = [

        SystemMessage(
            content=SYSTEM_PROMPT
        )

    ]


# ============================================================
# PROCESS USER MESSAGE
# ============================================================

async def process_message(
    history,
):

    # --------------------------------------------------------
    # OpenAI LLM
    # --------------------------------------------------------

    llm = ChatOpenAI(
        model="gpt-5",
    )

    # --------------------------------------------------------
    # MCP servers
    # --------------------------------------------------------

    servers = create_servers()

    client = MultiServerMCPClient(
        servers
    )

    # --------------------------------------------------------
    # Load MCP tools
    # --------------------------------------------------------

    try:

        print("\n")
        print("=" * 70)
        print(
            "LOADING MCP TOOLS"
        )
        print("=" * 70)

        tools = await client.get_tools()

        print(
            "\nAVAILABLE MCP TOOLS:"
        )

        for tool in tools:

            print(
                f"  ✓ {tool.name}"
            )

        print(
            "=" * 70
        )

        print()

    except Exception as e:

        print("\n")
        print("=" * 70)
        print(
            "MCP TOOL LOADING FAILED"
        )
        print("=" * 70)

        print(
            "Error Type:",
            type(e).__name__,
        )

        print(
            "Error:",
            str(e),
        )

        print(
            "=" * 70
        )

        traceback.print_exc()

        raise

    # --------------------------------------------------------
    # Map tools
    # --------------------------------------------------------

    tool_by_name = {

        tool.name: tool

        for tool in tools

    }

    # --------------------------------------------------------
    # Bind tools to LLM
    # --------------------------------------------------------

    llm_with_tools = (
        llm.bind_tools(
            tools
        )
    )

    # --------------------------------------------------------
    # First LLM response
    # --------------------------------------------------------

    first_response = (
        await llm_with_tools.ainvoke(
            history
        )
    )

    tool_calls = getattr(
        first_response,
        "tool_calls",
        None,
    )

    # --------------------------------------------------------
    # No tool required
    # --------------------------------------------------------

    if not tool_calls:

        return (
            first_response,
            [],
        )

    # --------------------------------------------------------
    # Execute tools
    # --------------------------------------------------------

    tool_messages = []

    for tool_call in tool_calls:

        tool_name = (
            tool_call["name"]
        )

        tool_args = (
            tool_call.get("args")
            or {}
        )

        # ----------------------------------------------------
        # Convert JSON string arguments
        # ----------------------------------------------------

        if isinstance(
            tool_args,
            str,
        ):

            try:

                tool_args = json.loads(
                    tool_args
                )

            except json.JSONDecodeError:

                pass

        # ----------------------------------------------------
        # Tool not found
        # ----------------------------------------------------

        if tool_name not in tool_by_name:

            tool_messages.append(

                ToolMessage(

                    tool_call_id=(
                        tool_call["id"]
                    ),

                    content=(
                        f"Tool '{tool_name}' "
                        "was not found."
                    ),
                )

            )

            continue

        tool = tool_by_name[
            tool_name
        ]

        # ----------------------------------------------------
        # Execute MCP tool
        # ----------------------------------------------------

        try:

            print(
                f"Calling MCP tool: "
                f"{tool_name}"
            )

            print(
                f"Arguments: "
                f"{tool_args}"
            )

            result = await tool.ainvoke(
                tool_args
            )

            if isinstance(
                result,
                str,
            ):

                content = result

            else:

                content = json.dumps(

                    result,

                    ensure_ascii=False,

                    default=str,
                )

        except Exception as e:

            print(
                f"Tool '{tool_name}' failed."
            )

            traceback.print_exc()

            content = (

                "Tool execution failed: "

                f"{type(e).__name__}: "

                f"{str(e)}"
            )

        # ----------------------------------------------------
        # Add tool message
        # ----------------------------------------------------

        tool_messages.append(

            ToolMessage(

                tool_call_id=(
                    tool_call["id"]
                ),

                content=content,
            )

        )

    # --------------------------------------------------------
    # Final LLM call
    # --------------------------------------------------------

    final_history = (

        history

        + [
            first_response
        ]

        + tool_messages
    )

    final_response = (

        await llm.ainvoke(
            final_history
        )

    )

    return (

        final_response,

        [
            first_response,
            *tool_messages,
        ],
    )


# ============================================================
# DISPLAY CHAT HISTORY
# ============================================================

for message in (
    st.session_state.history
):

    if isinstance(
        message,
        HumanMessage,
    ):

        with st.chat_message(
            "user"
        ):

            st.markdown(
                message.content
            )

    elif isinstance(
        message,
        AIMessage,
    ):

        if getattr(
            message,
            "tool_calls",
            None,
        ):

            continue

        with st.chat_message(
            "assistant"
        ):

            st.markdown(
                message.content or ""
            )


# ============================================================
# CHAT INPUT
# ============================================================

user_text = st.chat_input(
    "Type your message..."
)


if user_text:

    # --------------------------------------------------------
    # Display user message
    # --------------------------------------------------------

    with st.chat_message(
        "user"
    ):

        st.markdown(
            user_text
        )

    # --------------------------------------------------------
    # Add user message to history
    # --------------------------------------------------------

    st.session_state.history.append(

        HumanMessage(
            content=user_text
        )

    )

    # --------------------------------------------------------
    # Process request
    # --------------------------------------------------------

    try:

        (
            final_response,
            intermediate_messages,
        ) = asyncio.run(

            process_message(

                st.session_state.history

            )

        )

        # ----------------------------------------------------
        # Display assistant response
        # ----------------------------------------------------

        with st.chat_message(
            "assistant"
        ):

            st.markdown(
                final_response.content
                or ""
            )

        # ----------------------------------------------------
        # Save intermediate messages
        # ----------------------------------------------------

        st.session_state.history.extend(

            intermediate_messages

        )

        # ----------------------------------------------------
        # Save final response
        # ----------------------------------------------------

        st.session_state.history.append(

            AIMessage(

                content=(
                    final_response.content
                    or ""
                )

            )

        )

    except Exception as e:

        # ----------------------------------------------------
        # Display error
        # ----------------------------------------------------

        st.error(

            f"{type(e).__name__}: "
            f"{str(e)}"

        )

        # ----------------------------------------------------
        # Print full error
        # ----------------------------------------------------

        print("\n")
        print("=" * 70)

        print(
            "STREAMLIT MCP ERROR"
        )

        print("=" * 70)

        traceback.print_exc()

        print("=" * 70)