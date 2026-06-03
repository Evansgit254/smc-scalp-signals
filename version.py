# Pure Quant Research Terminal Versioning Central
# Updated: 2026-05-29

VERSION_MAJOR = 5
VERSION_MINOR = 3
VERSION_PATCH = 0

# Status can be 'stable', 'beta', 'rc' (Release Candidate)
VERSION_STATUS = "stable"

RELEASE_NAME = "Live-Ready Mathematical Update 63"
RELEASE_NOTES = [
    "Active strategy scope narrowed to CRT and Advanced Pattern.",
    "Run 61 & 63 retained as historical CRT baseline evidence.",
    "Alpha Combiner suppression decoupled from structural mechanics.",
    "ExecutionGate perfectly isolated against cross-run DB pollution.",
]

def get_version():
    """Returns the full semantic version string."""
    version = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
    if VERSION_STATUS != "stable":
        version += f"-{VERSION_STATUS}"
    return version

def get_system_banner():
    """Returns a visual banner for logs/CLIs."""
    return f"""
    ╔════════════════════════════════════════════════╗
    ║         PURE QUANT RESEARCH TERMINAL           ║
    ║                Version {get_version():<15} ║
    ║        {RELEASE_NAME:<34}║
    ╚════════════════════════════════════════════════╝
    """

if __name__ == "__main__":
    print(get_system_banner())
