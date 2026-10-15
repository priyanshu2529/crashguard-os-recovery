import sys
import uvicorn
from backend.config import PORT

if __name__ == "__main__":
    print(f"============================================================")
    print(f"  CRASHGUARD CONSOLE LAUNCHING")
    print(f"  Local URL : http://127.0.0.1:{PORT}")
    print(f"  API Docs  : http://127.0.0.1:{PORT}/docs")
    print(f"============================================================")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORT, reload=True)
