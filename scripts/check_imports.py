import sys
import os
import importlib

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

modules_to_check = [
    "app.config",
    "app.api.models",
    "app.api.main",
    "app.memory.store",
    "app.orchestrator.agent",
    "app.orchestrator.craving_engine",
    "desktop.tray_app",
    # UI pages are scripts, not always importable as modules, but App.py is the entry
    "app.ui.App", 
]

print("--- Starting Import Integrity Check ---")
failures = []

for mod_name in modules_to_check:
    try:
        print(f"Importing {mod_name}...", end=" ")
        importlib.import_module(mod_name)
        print("OK")
    except ImportError as e:
        print(f"FAILED: {e}")
        failures.append((mod_name, str(e)))
    except Exception as e:
        print(f"ERROR: {e}")
        failures.append((mod_name, str(e)))

print("\n--- Check Complete ---")
if failures:
    print(f"{len(failures)} failures detected.")
    sys.exit(1)
else:
    print("All modules imported successfully.")
    sys.exit(0)
