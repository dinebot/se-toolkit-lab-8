#!/usr/bin/env python3
"""Resolve environment variables into nanobot config and launch the gateway."""

import json
import os
import subprocess
from pathlib import Path


def resolve_config() -> str:
    """Read config.json, inject env vars, write config.resolved.json."""
    config_path = Path("/app/nanobot/config.json")
    resolved_path = Path("/app/nanobot/config.resolved.json")
    workspace = Path("/app/nanobot/workspace")

    with open(config_path, "r") as f:
        config = json.load(f)

    # Resolve LLM provider config from env vars
    if "providers" in config and "custom" in config["providers"]:
        config["providers"]["custom"]["apiKey"] = os.environ.get(
            "LLM_API_KEY", config["providers"]["custom"].get("apiKey", "")
        )
        config["providers"]["custom"]["apiBase"] = os.environ.get(
            "LLM_API_BASE_URL", config["providers"]["custom"].get("apiBase", "")
        )

    # Resolve gateway host/port from env vars
    if "gateway" not in config:
        config["gateway"] = {}
    config["gateway"]["address"] = os.environ.get(
        "NANOBOT_GATEWAY_CONTAINER_ADDRESS", "0.0.0.0"
    )
    config["gateway"]["port"] = int(
        os.environ.get("NANOBOT_GATEWAY_CONTAINER_PORT", "18790")
    )

    # Resolve webchat channel config from env vars
    if "channels" not in config:
        config["channels"] = {}
    if "webchat" not in config["channels"]:
        config["channels"]["webchat"] = {"enabled": True, "allow_from": ["*"]}
    config["channels"]["webchat"]["port"] = int(
        os.environ.get("NANOBOT_WEBCHAT_CONTAINER_PORT", "8765")
    )
    config["channels"]["webchat"]["address"] = os.environ.get(
        "NANOBOT_WEBCHAT_CONTAINER_ADDRESS", "0.0.0.0"
    )
    config["channels"]["webchat"]["access_key"] = os.environ.get(
        "NANOBOT_ACCESS_KEY", ""
    )

    # Resolve MCP server env vars for LMS
    if "tools" not in config:
        config["tools"] = {}
    if "mcpServers" not in config["tools"]:
        config["tools"]["mcpServers"] = {}

    # Update LMS MCP server config if present
    if "lms" in config["tools"]["mcpServers"]:
        lms_config = config["tools"]["mcpServers"]["lms"]
        # Update env vars for the MCP subprocess
        if "env" not in lms_config:
            lms_config["env"] = {}
        lms_config["env"]["NANOBOT_LMS_BACKEND_URL"] = os.environ.get(
            "NANOBOT_LMS_BACKEND_URL", ""
        )
        lms_config["env"]["NANOBOT_LMS_API_KEY"] = os.environ.get(
            "NANOBOT_LMS_API_KEY", ""
        )

    # Write resolved config
    with open(resolved_path, "w") as f:
        json.dump(config, f, indent=2)

    return str(resolved_path)


def main():
    resolved_config = resolve_config()
    workspace = "/app/nanobot/workspace"

    # Install lms-mcp if not already installed (for editable install in container)
    mcp_path = Path("/app/nanobot/mcp")
    if mcp_path.exists():
        try:
            subprocess.run(
                ["uv", "add", str(mcp_path), "--editable"],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            pass  # Might already be installed

    # Launch nanobot gateway
    os.execvp(
        "nanobot",
        [
            "nanobot",
            "gateway",
            "--config",
            resolved_config,
            "--workspace",
            workspace,
        ],
    )


if __name__ == "__main__":
    main()
