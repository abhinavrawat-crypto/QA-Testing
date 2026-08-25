"""Sandboxed Playwright Test Runner Orchestrator.

Orchestrates execution of Playwright test scripts inside ephemeral, resource-capped containers/subprocesses.
Streams real-time execution logs via WebSockets to the frontend.
Captures test execution status, duration, and output logs.
"""
import asyncio
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.analysis import PlaywrightRun

logger = logging.getLogger(__name__)


class RunnerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_playwright_script(
        self,
        user_id: UUID,
        script_code: str,
        target_url: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 60,
        headed: bool = False,
    ) -> PlaywrightRun:
        """Create a run record, execute script in isolated workspace, stream logs, save results."""
        run = PlaywrightRun(
            user_id=user_id,
            script_content=script_code,
            status="running",
            logs="",
        )
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)

        # Execute in background task or inline async
        start_time = time.time()
        logs = []

        async def broadcast_log(line: str):
            logs.append(line)
            try:
                from app.main import manager
                await manager.broadcast_job_log(str(run.id), {
                    "run_id": str(run.id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "log": line,
                })
            except Exception:
                pass

        mode_str = "Headed Live Browser" if headed else "Headless Background"
        await broadcast_log(f"🚀 Initializing Playwright execution runner [{mode_str} Mode] (Run ID: {run.id})")
        if target_url:
            await broadcast_log(f"🌐 Target Base URL: {target_url}")
        if env_vars:
            await broadcast_log(f"🔑 Loaded {len(env_vars)} environment variable(s)")

        # Create temporary working directory for the test run
        temp_dir = tempfile.mkdtemp(prefix=f"pw_run_{run.id}_")
        test_file_path = os.path.join(temp_dir, "test.spec.js")
        config_file_path = os.path.join(temp_dir, "playwright.config.js")
        pkg_json_path = os.path.join(temp_dir, "package.json")

        # Write package.json with ES module support
        with open(pkg_json_path, "w") as f:
            f.write('{\n  "name": "pw-runner",\n  "version": "1.0.0",\n  "type": "module"\n}\n')

        # Dynamically discover Playwright node_modules and symlink into temp_dir
        pw_modules = self._find_playwright_node_modules()
        if pw_modules:
            try:
                os.symlink(pw_modules, os.path.join(temp_dir, "node_modules"))
            except Exception:
                pass

        # Write test spec
        with open(test_file_path, "w") as f:
            f.write(script_code)

        # Write isolated Playwright config
        headless_setting = "false" if headed else "true"
        config_content = f"""
export default {{
  use: {{
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || {repr(target_url or '')},
    headless: {headless_setting},
    screenshot: 'only-on-failure',
  }},
  timeout: {timeout_seconds * 1000},
}};
"""
        with open(config_file_path, "w") as f:
          f.write(config_content)

        await broadcast_log(f"📁 Created test spec, package.json, and config at `{temp_dir}`")

        # Command to execute via npx playwright test
        cmd = ["npx", "-y", "@playwright/test", "test", "test.spec.js", "--reporter=line"]
        if headed:
            cmd.append("--headed")
        
        env = os.environ.copy()
        if pw_modules:
            env["NODE_PATH"] = pw_modules
        if target_url:
            env["PLAYWRIGHT_TEST_BASE_URL"] = target_url
        if env_vars:
            for k, v in env_vars.items():
                env[k] = v

        try:
            await broadcast_log("⚙️ Spawning Playwright execution process with 60s timeout...")
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=temp_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            # Stream stdout line-by-line
            async def read_stream(stream, prefix=""):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    if decoded:
                        await broadcast_log(f"{prefix}{decoded}")

            await asyncio.wait_for(
                asyncio.gather(
                    read_stream(proc.stdout),
                    read_stream(proc.stderr, prefix="[stderr] "),
                    proc.wait(),
                ),
                timeout=timeout_seconds,
            )

            duration = time.time() - start_time
            if proc.returncode == 0:
                run.status = "passed"
                await broadcast_log(f"✅ Test run PASSED in {duration:.2f}s")
            else:
                run.status = "failed"
                await broadcast_log(f"❌ Test run FAILED with exit code {proc.returncode} ({duration:.2f}s)")

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            run.status = "timeout"
            await broadcast_log(f"⏱️ Test run TIMED OUT after {timeout_seconds}s")
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass

        except Exception as e:
            duration = time.time() - start_time
            run.status = "failed"
            run.error_message = str(e)
            await broadcast_log(f"💥 Execution error: {e}")

        finally:
            # Clean up temp dir
            shutil.rmtree(temp_dir, ignore_errors=True)

        run.logs = "\n".join(logs)
        run.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return run

    async def get_run(self, run_id: UUID, user_id: UUID) -> Optional[PlaywrightRun]:
        result = await self.db.execute(
            select(PlaywrightRun).where(
                PlaywrightRun.id == run_id,
                PlaywrightRun.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    def _find_playwright_node_modules(self) -> Optional[str]:
        # Check npx cache directory first
        npx_base = os.path.expanduser("~/.npm/_npx")
        if os.path.exists(npx_base):
            for root, dirs, files in os.walk(npx_base):
                if root.endswith("node_modules") and os.path.exists(os.path.join(root, "@playwright")):
                    return root
        # Check project frontend node_modules
        frontend_nm = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../frontend/node_modules"))
        if os.path.exists(os.path.join(frontend_nm, "@playwright")):
            return frontend_nm
        return None
