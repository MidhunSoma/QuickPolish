"""
Automated PyInstaller Packaging Script for QuickPolish.
Builds a standalone, zero-dependency portable executable (.exe on Windows, binary on macOS/Linux).
"""

import os
import sys
import shutil
import subprocess

def run_build():
    print("=" * 60)
    print("   QuickPolish - Standalone Executable Build System")
    print("=" * 60)

    # 1. Project directories
    root_dir = os.path.dirname(os.path.abspath(__file__))
    client_dir = os.path.join(root_dir, "client")
    assets_dir = os.path.join(client_dir, "assets")
    entry_point = os.path.join(client_dir, "app.py")

    # 2. Ensure Icon Assets are generated
    print("\n[1/4] Checking and generating icon assets...")
    try:
        sys.path.insert(0, client_dir)
        from assets.generate_icon import ensure_icons
        png_path, ico_path = ensure_icons(assets_dir)
        print(f" -> Icon assets ready: {ico_path}")
    except Exception as e:
        print(f"Warning: Could not auto-generate icons: {e}")
        ico_path = os.path.join(assets_dir, "icon.ico")
        png_path = os.path.join(assets_dir, "icon.png")

    # 3. Check for PyInstaller
    print("\n[2/4] Verifying PyInstaller installation...")
    try:
        import PyInstaller
        print(f" -> Found PyInstaller version {PyInstaller.__version__}")
    except ImportError:
        print(" -> PyInstaller not found. Installing now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 4. Prepare PyInstaller command arguments
    print("\n[3/4] Assembling PyInstaller build options...")

    # Separator for --add-data: ';' on Windows, ':' on macOS/Linux
    path_sep = ";" if sys.platform == "win32" else ":"
    data_arg = f"{assets_dir}{path_sep}assets"

    pyinstaller_args = [
        sys.executable, "-m", "PyInstaller",
        "--name=QuickPolish",
        "--onefile",
        "--noconsole",
        "--clean",
        f"--add-data={data_arg}",
        # Essential hidden imports for dynamic imports in pynput and pystray
        "--hidden-import=pynput",
        "--hidden-import=pynput.keyboard",
        "--hidden-import=pynput.mouse",
        "--hidden-import=pystray",
        "--hidden-import=pystray._win32" if sys.platform == "win32" else "--hidden-import=pystray._darwin",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=pyperclip",
        "--hidden-import=requests",
        "--hidden-import=tkinter",
        f"--paths={client_dir}",
    ]

    # Add icon option
    if sys.platform == "win32" and os.path.exists(ico_path):
        pyinstaller_args.append(f"--icon={ico_path}")
    elif sys.platform == "darwin" and os.path.exists(png_path):
        pyinstaller_args.append(f"--icon={png_path}")

    pyinstaller_args.append(entry_point)

    print(f" -> Running PyInstaller command for {sys.platform}...")

    # 5. Execute Build
    print("\n[4/4] Compiling standalone package (this may take 30-60 seconds)...")
    res = subprocess.run(pyinstaller_args, cwd=root_dir)

    if res.returncode != 0:
        print("\n[BUILD FAILED] PyInstaller encountered errors during packaging.")
        sys.exit(res.returncode)

    # 6. Verify output
    dist_dir = os.path.join(root_dir, "dist")
    exe_name = "QuickPolish.exe" if sys.platform == "win32" else "QuickPolish"
    final_binary = os.path.join(dist_dir, exe_name)

    if os.path.exists(final_binary):
        size_mb = os.path.getsize(final_binary) / (1024 * 1024)
        print("\n" + "=" * 60)
        print("  BUILD SUCCESSFUL!")
        print(f"  Target Executable: {final_binary}")
        print(f"  File Size:         {size_mb:.2f} MB")
        print("=" * 60)
        print("\nYou can now distribute this standalone file to any PC.")
        print("Users can double-click it and start polishing text with Ctrl+Alt+R.")
    else:
        print(f"\nWarning: Expected output file at {final_binary} was not found.")

if __name__ == "__main__":
    run_build()
