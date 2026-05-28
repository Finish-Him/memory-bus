"""Main entry point for Memory Bus API."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8400, reload=True)
