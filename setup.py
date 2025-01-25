from cx_Freeze import setup, Executable
import sys
import os

platform_packages = {
    "win32": ["pywin32"],
    "darwin": ["pyobjc-framework-Cocoa", "pyobjc-framework-WebKit"],
    "linux": []
}

build_exe_options = {
    "packages": [
        "os", "flask", "logging", "requests", "configparser",
        "webview"
    ] + platform_packages.get(sys.platform, []),
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
