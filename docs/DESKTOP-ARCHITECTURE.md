# SRK Desktop Architecture

SRK is an application **built on the reusable Salix RAD architecture extracted from the Salix application family**. It does not maintain its own competing GUI runtime or engine. The reusable Salix layers own application lifecycle contracts, presentation capabilities, semantic components, responsive layout, documentation primitives, and Dear PyGui adapters; SRK contributes the retro-disc, Saturn, SAROO, localization, and reverse-engineering domain.

## Dependency direction

```text
SRK product views / application commands
                |
                v
        Salix framework/runtime
 components | docs | layout | lifecycle
                |
                v
           Salix engine
 Dear PyGui hosts / renderers / adapters
                |
                v
            Dear PyGui

SRK application/domain services
                |
                v
core / formats / hardware
```

The boundaries are deliberate:

- `salix.framework` and `salix.runtime` are backend-neutral and must not import SRK product code or Dear PyGui.
- `salix.engine` owns concrete Dear PyGui adapters.
- `rikai_kotoba.core` and `rikai_kotoba.application` must not import Dear PyGui.
- SRK does **not** have a parallel `rikai_kotoba.runtime` or `rikai_kotoba.engine` package.
- Product views may compose concrete presentation, but domain behavior remains below the presentation boundary.

## Package responsibilities

```text
src/
├── salix/
│   ├── runtime/
│   │   ├── application.py
│   │   ├── lifecycle.py
│   │   ├── presentation.py
│   │   ├── scenes.py
│   │   ├── diagnostics.py
│   │   └── paths.py
│   ├── framework/
│   │   ├── property_cascade.py
│   │   ├── geometry.py
│   │   ├── responsive.py
│   │   ├── interactions.py
│   │   ├── command_menu.py
│   │   ├── components/
│   │   └── documentation/
│   └── engine/
│       ├── application_hosts/
│       ├── component_renderers/
│       ├── layout_hosts/
│       ├── scene_hosts/
│       ├── command_menu_hosts/
│       ├── presentation_backends/
│       ├── documentation/
│       ├── responsive_layout.py
│       └── ui_typography.py
│
└── rikai_kotoba/
    ├── core/          optical-disc and ISO-9660 primitives
    ├── formats/       platform-specific format knowledge
    ├── hardware/      original-hardware integrations such as Saturn/SAROO
    ├── application/   SRK use-cases, controllers, workers, paths, Help content
    ├── views/         SRK Dear PyGui product views
    ├── tools/         standalone tools such as Mjölnir
    ├── cli.py         headless command-line surface
    └── desktop.py     SRK composition root / desktop entry point
```

## Application host and lifecycle

`salix.runtime.ApplicationRuntime` owns an ordered `ServiceRegistry`. Services implement three explicit operations:

- `start()`
- `update(delta_seconds)`
- `stop()`

Startup failure rolls already-started services back in reverse order. Normal shutdown also occurs in reverse order.

`salix.engine.application_hosts.DearPyGuiApplicationHost` owns the Dear PyGui context, viewport, primary root window, frame loop, concrete presentation backend, responsive layout coordinator, and scene registry. It drives `ApplicationRuntime.update()` once per rendered frame. It does **not** own SRK disc logic, SAROO logic, or worker jobs.

SRK's `desktop.py` is the composition root. It creates the Salix runtime, registers SRK's worker service, creates application controllers, creates the Salix Dear PyGui host, composes product views, registers the active-view update service, and starts the host.

## Thread ownership rule

**Only the Dear PyGui owner/main thread may touch Dear PyGui state.**

`rikai_kotoba.application.workers.BackgroundWorkerService` is an SRK application service supervised by the Salix runtime. A worker executes domain/application work and publishes an immutable `WorkerEvent` into a thread-safe queue. `ApplicationRuntime.update()` calls the worker service on the Dear PyGui owner thread; that service drains its queue and invokes subscribers there.

```text
UI action (Dear PyGui owner thread)
        |
        v
SRK controller.submit(...)
        |
        v
BackgroundWorkerService
        |
        +---- worker thread ----> application/core/hardware work
        |                              |
        |                              v
        |                         WorkerEvent
        |                              |
        +-------- thread-safe queue <--+
                       |
                       v
        Salix ApplicationRuntime.update()
               (owner thread)
                       |
                       v
        controller/view subscribers
                       |
                       v
              Dear PyGui updates
```

The worker service is intentionally an **SRK application service**, not a second application runtime. Salix owns lifecycle supervision; SRK owns the jobs that its product needs.

## Salix component and presentation boundary

The Salix component model keeps reusable controls independent of Dear PyGui. Components express semantic state and layout through contracts such as:

- `Component` / `ValueComponent`
- semantic component events
- `ControlLayout` with `AUTO` / `FILL`
- component layout profiles
- explicit value bindings and component state groups
- renderer contracts

`salix.engine.component_renderers.DearPyGuiRenderer` translates those contracts to Dear PyGui widgets. The presentation backend bundles the component renderer, layout host, scene host, and command-menu host so the application composition root receives one explicit adapter set.

SRK product views should prefer those framework components where a suitable semantic component exists. Product-specific presentation that has not yet been generalized may remain in `rikai_kotoba.views`; it must not leak into application/domain services.

## Responsive layout

Geometry configuration follows Salix's deterministic cascade:

```text
framework default -> active theme -> explicit instance override
```

Responsive constraints are applied separately from configured values. This allows a valid wide layout to contract in a narrow window and expand again later without losing its configuration.

`LayoutCoordinator` owns callback registration and low-churn geometry updates; `DearPyGuiLayoutHost` owns toolkit resize hooks and item configuration.

## Offline Help and Glossary

Help is a first-class offline subsystem, not a web link or an afterthought.

`salix.framework.documentation` contains the semantic document model, layout policy, typography roles, scalable documentation settings, callouts, media descriptions, links, and page/section/block primitives. `salix.engine.documentation.DocumentationRenderer` renders those semantic documents through Dear PyGui and reflows them responsively.

SRK-specific wording lives in `rikai_kotoba.application.help_content`. This keeps the reusable Salix documentation framework free of Saturn/game terminology while letting the same glossary definitions power manual pages, search, and contextual help.

The SRK Help scene provides:

- an offline manual;
- searchable manual and glossary content;
- Contents navigation;
- Glossary A-Z navigation;
- scalable documentation text;
- cross-links between topics;
- novice-oriented explanations of terms such as CUE, BIN, sector, LBA, ISO-9660, IP.BIN, SAROO, RAM dump, correlation, and provenance.

The design target is a user who may have no Internet connection and little prior reverse-engineering knowledge.

## Disc workspace

`DiscWorkspaceService` owns the active logical disc and ISO reader. `DiscWorkspaceController` submits source opening/indexing to the SRK worker service. Worker completion is delivered through the Salix runtime update path before the view updates Dear PyGui.

The service retains SRK's global source-safety rule: source media is opened through the existing read-only `DiscImage` / `CueDisc` abstractions.

## SAROO boundary

The initial SAROO view is deliberately a presentation shell. Upcoming transport/capture/correlation logic belongs below the GUI in `hardware/saturn/saroo/` and application services. Title-specific addresses, offsets, signatures, and experiments remain outside the reusable public repository.

The intended path is:

```text
SAROO transport/capture
        |
        v
hardware/saturn/saroo
        |
        v
SRK capture/correlation services
        |
        v
SRK background worker service
        |
        v
Salix runtime update boundary
        |
        v
SAROO presentation
```

## Diagnostics

`salix.runtime.diagnostics.ExceptionReporter` provides rate-limited exception reporting and an append-only per-user UI error log. The Diagnostics scene exposes Salix runtime and SRK worker state without reaching into worker threads or domain internals.

## Persistence

The desktop deliberately does not introduce a database yet. Workspace preferences and structured project/session persistence should be added behind explicit interfaces when the product needs them. SalixORM can then provide a backend without making the GUI or domain layers depend directly on database implementation details.

## Architectural tests

The committed tests guard these boundaries so later features cannot quietly reverse them. In particular they verify that:

- SRK core/application code does not import Dear PyGui;
- SRK core does not depend on `salix.engine`;
- Salix framework/runtime code does not depend on SRK product code;
- Salix framework/runtime code does not import Dear PyGui;
- SRK does not reintroduce parallel `runtime` or `engine` packages;
- concrete Dear PyGui adapters exist under `salix.engine`.
