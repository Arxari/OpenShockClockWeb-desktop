from cx_Freeze import setup, Executable
import sys

build_exe_options = {
    "packages": ["os", "flask", "webview", "requests", "configparser", "logging"],
    "excludes": ["tkinter", "PyQt5", "matplotlib", "scipy", "numpy"],
    "include_files": [
        ("singleuser/static", "static"),
        ("singleuser/templates", "templates"),
        ("singleuser/config.txt", "config.txt"),
        ("singleuser/static/favicon.ico", "favicon.ico")
    ],
}

base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="OpenShockClock",
    version="0.1",
    description="OpenShockClock Application",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "singleuser/app.py",
            base=base,
            icon="singleuser/static/favicon.ico",
            target_name="OpenShockClock"
        )
    ]
)
