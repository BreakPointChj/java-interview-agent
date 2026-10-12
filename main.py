"""项目启动入口：默认启动 CLI，传入 ``api`` 时启动 HTTP 服务。"""

from __future__ import annotations

import sys

from interview_agent.cli import run_cli


def main() -> None:
    """根据命令行参数选择运行方式。"""

    if len(sys.argv) > 1 and sys.argv[1].lower() == "api":
        import uvicorn

        from interview_agent.config import get_settings

        settings = get_settings()
        uvicorn.run(
            "interview_agent.api:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=False,
        )
        return
    run_cli()


if __name__ == "__main__":
    main()
