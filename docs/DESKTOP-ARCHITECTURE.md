# SRK Desktop Architecture

The SRK desktop application follows the same architectural rules proven in the Salix application family: application/runtime contracts remain independent of a concrete GUI toolkit, presentation is isolated behind Dear PyGui-facing modules, and long-running work never manipulates the live widget tree from a worker thread.

## Dependency direction

```text
Dear PyGui views
      |
      v
application controllers
      |
      v
application services
      |
      v
SRK core / platform / hardware domains
```

Runtime infrastructure sits beside those layers and supervises lifecycle, workers, diagnostics, and scenes. Domain/core modules never import Dear PyGui.

## Package responsibilities

```text
rikai_kotoba/
├── core/          optical-disc and ISO-9660 primitives
├── formats/       platform-specific file/format knowledge
├── hardware/      original-hardware integrations such as Saturn/SAROO
├── application/   use-case services and presentation-neutral controllers
├── runtime/       lifecycle, workers, diagnostics, scene contracts
├── engine/        Dear PyGui application host/adapters
├── views/         Dear PyGui scene composition only
├── tools/         standalone research utilities such as Mjolnir
├── cli.py         headless command-line surface
└── desktop.py     desktop composition/entry point
```

The application layer may depend on `core`, `formats`, `hardware`, and `runtime`. The reusable core/application/runtime layers must not import Dear PyGui. `engine`, `views`, and `desktop` are the presentation boundary.

## Thread ownership rule

**Only the Dear PyGui owner/main thread may touch Dear PyGui state.**

`BackgroundWorkerService` owns a bounded-size thread pool. A worker executes domain/application work and publishes an immutable `WorkerEvent` into a thread-safe queue. `ApplicationRuntime.update()` runs on the Dear PyGui render thread, drains that queue, and dispatches subscribers there.

```text
UI callback (main thread)
      |
      v
controller.submit(...)
      |
      v
BackgroundWorkerService
      |
      +---- worker thread ----> application/core work
      |                              |
      |                              v
      |                         WorkerEvent
      |                              |
      +-------- thread-safe queue <--+
                     |
                     v
ApplicationRuntime.update() (main thread)
                     |
                     v
controller/view event handlers
                     |
                     v
Dear PyGui widget updates
```

Dear PyGui 2.2+ manual callback management is enabled by `GuiEngine`, so Dear PyGui callbacks are also explicitly serialized onto the main render thread before runtime services update.

## Runtime lifecycle

`ApplicationRuntime` owns an ordered `ServiceRegistry`. Services implement three explicit operations:

- `start()`
- `update(delta_seconds)`
- `stop()`

Startup failure rolls already-started services back in reverse order. Normal shutdown also occurs in reverse order. The GUI engine owns only the viewport/render loop; it does not own domain worker logic.

## Disc workspace

`DiscWorkspaceService` owns the active logical disc and ISO reader. `DiscWorkspaceController` submits source opening/indexing to the worker service. `DiscWorkspaceView` receives controller events on the main thread and renders the result.

The service retains SRK's global source-safety rule: source media is opened through the existing read-only `DiscImage` / `CueDisc` abstractions.

## SAROO boundary

The initial SAROO scene is deliberately a presentation shell. Upcoming transport/capture/correlation logic belongs below the GUI in `hardware/saturn/saroo/` and application services. Title-specific addresses, offsets, signatures, and experiments remain outside the reusable public repository.

The intended path is:

```text
SAROO transport/capture
        |
        v
hardware/saturn/saroo
        |
        v
application capture/correlation services
        |
        v
worker event bridge
        |
        v
SAROO Dear PyGui view
```

## Diagnostics

`ExceptionReporter` provides rate-limited exception reporting and an append-only per-user UI error log. The Diagnostics scene exposes runtime and worker state without reaching into worker threads or domain internals.

## Persistence

The first desktop tranche deliberately does not introduce a database. Workspace preferences and project/session persistence will be added behind explicit interfaces when required. SalixORM can then provide a backend without making the GUI or domain layers depend directly on database implementation details.
