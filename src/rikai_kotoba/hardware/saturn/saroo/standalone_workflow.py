"""One-command guarded standalone Saturn build/deploy orchestration.

This module composes SRK's existing preserve-first primitives without weakening
any of their individual contracts.  Project generation and build remain off-card,
the deployment plan is read-only, a fresh whole-card inventory is captured
immediately before the one permitted card-write operation, and the resulting
card is verified against that exact pre-write baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Callable

from rikai_kotoba.hardware.saturn.standalone_build import (
    SaturnStandaloneBuildResult,
    build_saturn_standalone_project,
)
from rikai_kotoba.hardware.saturn.standalone_project import (
    SaturnStandaloneProjectResult,
    prepare_saturn_standalone_project,
)
from .card_guard import (
    SarooCardInventoryResult,
    SarooCardInventoryVerification,
    create_saroo_card_inventory,
    verify_saroo_card_inventory,
)
from .standalone_image_deployment import (
    CONFIRMATION_TOKEN,
    DEFAULT_DESTINATION_NAME,
    SarooStandaloneImageDeploymentPlan,
    SarooStandaloneImageDeploymentResult,
    apply_saroo_standalone_image_deployment,
    plan_saroo_standalone_image_deployment,
)


class SaturnStandaloneSarooWorkflowError(RuntimeError):
    """Raised when the composed standalone-to-SAROO workflow cannot continue safely."""


@dataclass(frozen=True)
class SaturnStandaloneSarooWorkflowResult:
    project: SaturnStandaloneProjectResult
    build: SaturnStandaloneBuildResult
    plan: SarooStandaloneImageDeploymentPlan
    guard: SarooCardInventoryResult | None
    deployment: SarooStandaloneImageDeploymentResult | None
    verification: SarooCardInventoryVerification | None

    @property
    def applied(self) -> bool:
        return self.deployment is not None

    @property
    def card_verified(self) -> bool:
        return self.verification is not None and self.verification.valid


def _allowed_deployment_paths(
    plan: SarooStandaloneImageDeploymentPlan,
) -> tuple[str, str, str]:
    try:
        destination = plan.destination_directory.relative_to(plan.card_root).as_posix()
    except ValueError as exc:
        raise SaturnStandaloneSarooWorkflowError(
            "planned SAROO destination is outside the mounted card root"
        ) from exc
    return (
        destination,
        f"{destination}/{plan.source_bin.name}",
        f"{destination}/{plan.source_cue.name}",
    )


def run_saturn_standalone_saroo_workflow(
    saturn_root: os.PathLike[str] | str,
    template_directory: os.PathLike[str] | str,
    ip_bin_source: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    release_date: str | None = None,
    destination_name: str = DEFAULT_DESTINATION_NAME,
    category: str | None = None,
    apply: bool = False,
    confirmation: str = "",
    _prepare: Callable[..., SaturnStandaloneProjectResult] = prepare_saturn_standalone_project,
    _build: Callable[..., SaturnStandaloneBuildResult] = build_saturn_standalone_project,
    _snapshot: Callable[..., SarooCardInventoryResult] = create_saroo_card_inventory,
    _plan: Callable[..., SarooStandaloneImageDeploymentPlan] = plan_saroo_standalone_image_deployment,
    _apply: Callable[..., SarooStandaloneImageDeploymentResult] = apply_saroo_standalone_image_deployment,
    _verify: Callable[..., SarooCardInventoryVerification] = verify_saroo_card_inventory,
) -> SaturnStandaloneSarooWorkflowResult:
    """Prepare, build, validate and optionally deploy one fresh Saturn image.

    ``apply=False`` performs no SAROO write and does not create a guard manifest;
    it prepares/builds the fresh project and returns the read-only deployment
    plan.  ``apply=True`` requires the same exact confirmation token as the
    lower-level deployer, captures a fresh off-card whole-card baseline, performs
    exactly one guarded deployment, then requires a post-write whole-card MATCH
    allowing only the newly-created destination directory and its BIN/CUE files.

    A failed post-deploy verification is never rolled back automatically because
    preserving the observed card state is safer than deleting evidence after a
    write has already occurred.
    """

    if apply and confirmation != CONFIRMATION_TOKEN:
        raise SaturnStandaloneSarooWorkflowError(
            f"confirmation token must be exactly {CONFIRMATION_TOKEN}"
        )

    project = _prepare(
        saturn_root,
        template_directory,
        ip_bin_source,
        output_directory,
        release_date=release_date,
    )
    build = _build(project.output_root)
    if not build.successful:
        raise SaturnStandaloneSarooWorkflowError(
            "standalone build failed; generated project tree was preserved for diagnosis"
        )

    plan = _plan(
        card_root,
        project.output_root,
        destination_name=destination_name,
        category=category,
    )

    if not apply:
        return SaturnStandaloneSarooWorkflowResult(
            project=project,
            build=build,
            plan=plan,
            guard=None,
            deployment=None,
            verification=None,
        )

    guard = _snapshot(card_root, guard_manifest)

    deployment = _apply(
        card_root,
        project.output_root,
        destination_name=destination_name,
        category=category,
        confirmation=CONFIRMATION_TOKEN,
    )

    allowed_paths = _allowed_deployment_paths(deployment.plan)
    verification = _verify(
        card_root,
        guard.manifest_path,
        allowed_changed_paths=allowed_paths,
    )
    if not verification.valid:
        details = "; ".join(verification.differences[:5])
        if len(verification.differences) > 5:
            details += f"; ... {len(verification.differences) - 5} more"
        raise SaturnStandaloneSarooWorkflowError(
            "deployment completed, but post-deploy whole-card verification failed; "
            "do not delete, retry, or modify the card until the difference is reviewed: "
            + details
        )

    return SaturnStandaloneSarooWorkflowResult(
        project=project,
        build=build,
        plan=deployment.plan,
        guard=guard,
        deployment=deployment,
        verification=verification,
    )
