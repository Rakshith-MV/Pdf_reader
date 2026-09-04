import subprocess
import sys
import os
import time

def build_executable():
    print("Building ReadEra Desktop Executable using PyInstaller...")

    # Install PyInstaller if missing
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Terminate any running instances of ReadEraDesktop.exe to release DLL handles
    if os.name == "nt":
        subprocess.call(["taskkill", "/F", "/IM", "ReadEraDesktop.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)

    sep = ";" if os.name == "nt" else ":"
    schema_arg = f"src/database/schema.sql{sep}src/database"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        f"--add-data={schema_arg}",
        "--name=ReadEraDesktop",
        "main.py",
    ]

    # Pre-clean dist folder if possible to prevent WinError 5 DLL lock issues
    dist_dir = os.path.join("dist", "ReadEraDesktop")
    if os.path.exists(dist_dir):
        try:
            import shutil
            shutil.rmtree(dist_dir, ignore_errors=True)
        except Exception:
            pass

    print("Running command:", " ".join(cmd))
    subprocess.check_call(cmd)
    print("\nBuild completed successfully! Executable generated in 'dist/ReadEraDesktop'.")

if __name__ == "__main__":
    build_executable()
