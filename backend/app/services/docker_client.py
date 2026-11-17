"""Docker SDK access via the locked-down socket proxy.

This is the ONLY module that talks to Docker. It only ever targets the
configured Bedrock container name.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import docker
from docker.errors import APIError, DockerException, NotFound
from docker.models.containers import Container

from app.core.config import Settings, get_settings
from app.core.errors import AppError, NotFoundError

logger = logging.getLogger(__name__)


class DockerUnavailableError(AppError):
    def __init__(self, message: str = "Docker is unavailable") -> None:
        super().__init__(message, status_code=503)


@dataclass
class ContainerStatus:
    name: str
    exists: bool
    running: bool
    status: str
    started_at: datetime | None
    image: str | None
    exit_code: int | None


@dataclass
class ContainerStatsSample:
    """One-shot Docker stats snapshot for the Bedrock container."""

    cpu_pct: float
    mem_bytes: int
    mem_limit_bytes: int
    net_rx_bytes: int
    net_tx_bytes: int
    running: bool


@dataclass
class ContainerVersionInfo:
    """Bedrock image / VERSION env hints for the Server page."""

    image: str | None
    version_env: str | None
    pinned: bool
    guidance: str


class BedrockDocker(Protocol):
    """Protocol so tests can inject a fake client."""

    def status(self) -> ContainerStatus: ...

    def sample_stats(self) -> ContainerStatsSample: ...

    def version_info(self) -> ContainerVersionInfo: ...

    def start(self) -> None: ...

    def stop(self, timeout: int = 30) -> None: ...

    def restart(self, timeout: int = 30) -> None: ...

    def send_command(self, command: str) -> None: ...

    def follow_logs(
        self, since: datetime | None = None, *, tail: int | None = None
    ) -> Any: ...


def parse_docker_stats(raw: dict[str, Any]) -> ContainerStatsSample:
    """Parse a Docker stats JSON blob into a ContainerStatsSample.

    Raises:
        KeyError / TypeError / ZeroDivisionError are avoided; bad data yields zeros.
    """

    cpu_pct = _cpu_percent(raw)
    mem = raw.get("memory_stats") or {}
    mem_bytes = int(mem.get("usage") or 0)
    mem_limit = int(mem.get("limit") or 0)
    # Prefer usage minus cache when available (cgroup v1 style).
    stats = mem.get("stats") or {}
    cache = int(stats.get("cache") or 0)
    if cache and mem_bytes >= cache:
        mem_bytes = mem_bytes - cache
    net_rx = 0
    net_tx = 0
    networks = raw.get("networks") or {}
    if isinstance(networks, dict):
        for iface in networks.values():
            if not isinstance(iface, dict):
                continue
            net_rx += int(iface.get("rx_bytes") or 0)
            net_tx += int(iface.get("tx_bytes") or 0)
    return ContainerStatsSample(
        cpu_pct=cpu_pct,
        mem_bytes=mem_bytes,
        mem_limit_bytes=mem_limit,
        net_rx_bytes=net_rx,
        net_tx_bytes=net_tx,
        running=True,
    )


def _cpu_percent(raw: dict[str, Any]) -> float:
    cpu = raw.get("cpu_stats") or {}
    precpu = raw.get("precpu_stats") or {}
    usage = (cpu.get("cpu_usage") or {}).get("total_usage")
    pre_usage = (precpu.get("cpu_usage") or {}).get("total_usage")
    system = cpu.get("system_cpu_usage")
    pre_system = precpu.get("system_cpu_usage")
    if usage is None or pre_usage is None or system is None or pre_system is None:
        return 0.0
    cpu_delta = float(usage) - float(pre_usage)
    system_delta = float(system) - float(pre_system)
    if cpu_delta <= 0 or system_delta <= 0:
        return 0.0
    online = cpu.get("online_cpus")
    if not online:
        percpu = (cpu.get("cpu_usage") or {}).get("percpu_usage") or []
        online = len(percpu) or 1
    pct = (cpu_delta / system_delta) * float(online) * 100.0
    return round(max(0.0, min(pct, 100.0 * float(online))), 2)


_client_override: BedrockDocker | None = None


def set_docker_client_override(client: BedrockDocker | None) -> None:
    """Replace the Docker client (tests)."""

    global _client_override
    _client_override = client


def get_docker_client(settings: Settings | None = None) -> BedrockDocker:
    """Return the process Docker client (or test override)."""

    if _client_override is not None:
        return _client_override
    return DockerSdkClient(settings or get_settings())


class DockerSdkClient:
    """Real Docker SDK client scoped to one container name."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._container_name = settings.bedrock_container
        kwargs: dict[str, Any] = {}
        host = settings.resolved_docker_host()
        if host:
            kwargs["base_url"] = host
        try:
            self._client = docker.DockerClient(**kwargs)
        except DockerException as exc:
            raise DockerUnavailableError(str(exc)) from exc

    def _get_container(self) -> Container:
        try:
            return self._client.containers.get(self._container_name)
        except NotFound as exc:
            raise NotFoundError(
                f"Bedrock container '{self._container_name}' not found"
            ) from exc
        except DockerException as exc:
            raise DockerUnavailableError(str(exc)) from exc

    def status(self) -> ContainerStatus:
        """Return status for the configured Bedrock container."""

        try:
            container = self._get_container()
        except NotFoundError:
            return ContainerStatus(
                name=self._container_name,
                exists=False,
                running=False,
                status="missing",
                started_at=None,
                image=None,
                exit_code=None,
            )
        except DockerUnavailableError:
            return ContainerStatus(
                name=self._container_name,
                exists=False,
                running=False,
                status="unavailable",
                started_at=None,
                image=None,
                exit_code=None,
            )

        state = container.attrs.get("State", {})
        started_raw = state.get("StartedAt")
        started_at: datetime | None = None
        if started_raw and started_raw not in {"0001-01-01T00:00:00Z", ""}:
            try:
                started_at = datetime.fromisoformat(started_raw.replace("Z", "+00:00"))
            except ValueError:
                started_at = None
        image = None
        try:
            image = (
                container.image.tags[0] if container.image.tags else container.image.id
            )
        except DockerException:
            image = None
        return ContainerStatus(
            name=self._container_name,
            exists=True,
            running=bool(state.get("Running")),
            status=str(state.get("Status") or container.status),
            started_at=started_at,
            image=image,
            exit_code=state.get("ExitCode"),
        )

    def version_info(self) -> ContainerVersionInfo:
        """Return image tag and VERSION env from the Bedrock container."""

        try:
            container = self._get_container()
        except (NotFoundError, DockerUnavailableError):
            return ContainerVersionInfo(
                image=None,
                version_env=None,
                pinned=False,
                guidance=(
                    "Bedrock container not found. Set BEDROCK_VERSION in deploy/.env "
                    "to a pinned build (not LATEST) so clients stay compatible."
                ),
            )
        try:
            container.reload()
        except DockerException:
            pass
        image = None
        try:
            image = (
                container.image.tags[0] if container.image.tags else container.image.id
            )
        except DockerException:
            image = None
        version_env = None
        try:
            env_list = container.attrs.get("Config", {}).get("Env") or []
            for entry in env_list:
                if isinstance(entry, str) and entry.startswith("VERSION="):
                    version_env = entry.split("=", 1)[1].strip() or None
                    break
        except Exception:
            version_env = None
        pinned = bool(
            version_env
            and version_env.upper() != "LATEST"
            and version_env.upper() != "PREVIEW"
        )
        if pinned:
            guidance = (
                "VERSION is pinned. Clients must match this Bedrock build. "
                "Change BEDROCK_VERSION in deploy/.env and recreate the bedrock service "
                "when you intentionally upgrade."
            )
        else:
            guidance = (
                "VERSION looks like LATEST/PREVIEW or is unset. Pin BEDROCK_VERSION "
                "in deploy/.env to a specific build so a restart does not leave older "
                "phones unable to join."
            )
        return ContainerVersionInfo(
            image=image,
            version_env=version_env,
            pinned=pinned,
            guidance=guidance,
        )

    def sample_stats(self) -> ContainerStatsSample:
        """Take a one-shot Docker stats sample for the Bedrock container.

        Uses stream=False so sampling stays cheap. Returns zeros when the
        container is missing or not running.
        """

        try:
            container = self._get_container()
        except (NotFoundError, DockerUnavailableError):
            return ContainerStatsSample(
                cpu_pct=0.0,
                mem_bytes=0,
                mem_limit_bytes=0,
                net_rx_bytes=0,
                net_tx_bytes=0,
                running=False,
            )
        try:
            container.reload()
        except DockerException:
            pass
        if container.status != "running":
            return ContainerStatsSample(
                cpu_pct=0.0,
                mem_bytes=0,
                mem_limit_bytes=0,
                net_rx_bytes=0,
                net_tx_bytes=0,
                running=False,
            )
        try:
            raw = container.stats(stream=False)
        except (APIError, DockerException) as exc:
            logger.warning("Docker stats failed: %s", exc)
            return ContainerStatsSample(
                cpu_pct=0.0,
                mem_bytes=0,
                mem_limit_bytes=0,
                net_rx_bytes=0,
                net_tx_bytes=0,
                running=True,
            )
        if not isinstance(raw, dict):
            return ContainerStatsSample(
                cpu_pct=0.0,
                mem_bytes=0,
                mem_limit_bytes=0,
                net_rx_bytes=0,
                net_tx_bytes=0,
                running=True,
            )
        sample = parse_docker_stats(raw)
        sample.running = True
        return sample

    def start(self) -> None:
        """Start the Bedrock container.

        Raises:
            NotFoundError / DockerUnavailableError / AppError
        """

        container = self._get_container()
        try:
            container.start()
        except APIError as exc:
            raise AppError(
                f"Failed to start container: {exc}", status_code=502
            ) from exc

    def stop(self, timeout: int = 30) -> None:
        """Stop the Bedrock container."""

        container = self._get_container()
        try:
            container.stop(timeout=timeout)
        except APIError as exc:
            raise AppError(f"Failed to stop container: {exc}", status_code=502) from exc

    def restart(self, timeout: int = 30) -> None:
        """Restart the Bedrock container."""

        container = self._get_container()
        try:
            container.restart(timeout=timeout)
        except APIError as exc:
            raise AppError(
                f"Failed to restart container: {exc}", status_code=502
            ) from exc

    def send_command(self, command: str) -> None:
        """Write a console command to the container stdin via attach.

        Do not use the itzg send-command helper — it fails with custom UIDs.

        Raises:
            AppError: if the container is not running or attach fails.
        """

        cleaned = command.strip()
        if not cleaned:
            raise AppError("Command must not be empty")
        if "\n" in cleaned or "\r" in cleaned:
            raise AppError("Command must be a single line")

        container = self._get_container()
        if container.status != "running":
            raise AppError("Bedrock container is not running", status_code=409)

        payload = (cleaned + "\n").encode("utf-8")
        try:
            socket = container.attach_socket(
                params={"stdin": 1, "stream": 1, "stdout": 0, "stderr": 0}
            )
            try:
                # docker SDK may return a socket wrapper with ._sock
                raw = getattr(socket, "_sock", socket)
                raw.sendall(payload)
            finally:
                close = getattr(socket, "close", None)
                if callable(close):
                    close()
        except (APIError, OSError, DockerException) as exc:
            raise AppError(f"Failed to send command: {exc}", status_code=502) from exc

    def follow_logs(self, since: datetime | None = None, *, tail: int | None = None):
        """Yield complete log lines from the Bedrock container.

        Docker often delivers one byte (or partial UTF-8) per chunk when
        ``stream=True``. Buffer until newlines so the console UI does not
        render a separate row per character.

        Prefer ``tail`` / ``since`` so reconnects do not replay hours of
        history into the console ring buffer (which breaks save-query waits).
        """

        container = self._get_container()
        kwargs: dict[str, Any] = {
            "stream": True,
            "follow": True,
            "timestamps": False,
            "stdout": True,
            "stderr": True,
        }
        if since is not None:
            if since.tzinfo is None:
                since = since.replace(tzinfo=UTC)
            kwargs["since"] = int(since.timestamp())
        elif tail is not None:
            kwargs["tail"] = max(0, int(tail))
        try:
            yield from iter_log_lines(container.logs(**kwargs))
        except (APIError, DockerException) as exc:
            raise DockerUnavailableError(str(exc)) from exc


def iter_log_lines(chunks: Any):
    """Buffer Docker log chunks into newline-delimited text lines."""

    buffer = ""
    for chunk in chunks:
        if isinstance(chunk, bytes):
            buffer += chunk.decode("utf-8", errors="replace")
        else:
            buffer += str(chunk)
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line.strip():
                yield line
    # Flush a trailing partial line if the stream ends cleanly.
    tail = buffer.rstrip("\r")
    if tail.strip():
        yield tail
