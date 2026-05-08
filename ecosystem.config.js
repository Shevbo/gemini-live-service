module.exports = {
  apps: [
    {
      name: "gemini-live-service",
      script: "python3",
      args: "-m uvicorn src.main:app --host 127.0.0.1 --port 8080",
      cwd: "/home/shectory/workspaces/gemini-live-service",
      interpreter: "none",
      env: {
        PYTHONPATH: "/home/shectory/workspaces/gemini-live-service",
      },
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "/home/shectory/logs/gemini-live-error.log",
      out_file: "/home/shectory/logs/gemini-live-out.log",
      merge_logs: true,
      restart_delay: 3000,
      max_restarts: 10,
    },
  ],
};
